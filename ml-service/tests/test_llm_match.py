import json
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.llm_extract import get_llm_client
from app.main import app
from app.matchers.llm import TOOL_NAME, match, numbered_lines

RESUME = "Jane Doe\n\nBuilt REST services in Python with FastAPI\nDeployed with Docker and GitHub Actions\nCurious about Kubernetes"
#   L1 Jane Doe | L2 blank | L3 REST/Python/FastAPI | L4 Docker/Actions | L5 Kubernetes (only curious)
JD = "Requirements: backend API development, Python, Docker. Nice to have: Kubernetes."


class FakeClient:
    def __init__(self, requirements=None, error=None, no_tool=False):
        self.requirements, self.error, self.no_tool, self.calls = requirements or [], error, no_tool, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        content = [] if self.no_tool else [SimpleNamespace(type="tool_use", name=TOOL_NAME, input={"requirements": self.requirements})]
        return SimpleNamespace(content=content, usage=SimpleNamespace(input_tokens=300, output_tokens=120))


def req(name, supported, lines, importance="required", note="because"):
    return {"requirement": name, "importance": importance, "supported": supported, "evidence_lines": lines, "note": note}


def test_numbering_matches_the_keyword_matcher():
    assert numbered_lines(RESUME) == {
        1: "Jane Doe",
        3: "Built REST services in Python with FastAPI",
        4: "Deployed with Docker and GitHub Actions",
        5: "Curious about Kubernetes",
    }


def test_evidence_text_comes_from_the_resume_not_the_model():
    fake = FakeClient([req("Python", True, [3]), req("Kubernetes", False, [], "preferred")])
    out = match(RESUME, JD, fake, model="m")
    python = out.requirements[0]
    assert python.supported and python.evidence[0].line_number == 3
    assert python.evidence[0].line == "Built REST services in Python with FastAPI"  # looked up, not model-written
    assert out.missing == ["Kubernetes"] and out.score == 0.5 and out.matcher == "llm:m"
    assert out.usage == {"input_tokens": 300, "output_tokens": 120} and out.ungrounded == 0


def test_supported_claim_without_a_real_line_is_downgraded_and_counted():
    fake = FakeClient([req("Docker", True, [99]), req("Python", True, []), req("Go", True, ["x", True, 2.5])])
    out = match(RESUME, JD, fake)
    assert [r.supported for r in out.requirements] == [False, False, False]
    assert out.ungrounded == 3 and out.score == 0.0


def test_evidence_on_an_unsupported_requirement_is_discarded():
    out = match(RESUME, JD, FakeClient([req("Kubernetes", False, [5])]))
    assert out.requirements[0].supported is False and out.requirements[0].evidence == []


def test_evidence_lines_are_deduplicated_and_capped_at_three():
    out = match(RESUME, JD, FakeClient([req("Python", True, [3, 3, 4, 1, 5])]))
    assert [e.line_number for e in out.requirements[0].evidence] == [3, 4, 1]


def test_duplicate_blank_and_malformed_requirements_are_skipped():
    out = match(RESUME, JD, FakeClient([req("Python", True, [3]), req("python", True, [3]), req("  ", True, [3]), "junk", {"supported": True}]))
    assert [r.requirement for r in out.requirements] == ["Python"]


def test_requirement_count_is_capped():
    many = [req(f"Skill{i}", False, []) for i in range(40)]
    assert len(match(RESUME, JD, FakeClient(many)).requirements) == 25


def test_unknown_importance_defaults_to_required_and_notes_are_trimmed():
    out = match(RESUME, JD, FakeClient([req("Python", True, [3], importance="critical", note="x" * 500)]))
    assert out.requirements[0].importance == "required" and len(out.requirements[0].note) == 160


def test_no_requirements_gives_zero_score():
    out = match(RESUME, JD, FakeClient([]))
    assert out.score == 0.0 and out.requirements == [] and out.missing == []


def test_request_shape_untrusted_wrappers_numbered_lines_forced_tool():
    fake = FakeClient([])
    match(RESUME, JD, fake)
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    content = call["messages"][0]["content"]
    assert "<job_description>" in content and "<resume>" in content and "L3: Built REST services" in content
    assert "L2:" not in content and "untrusted" in call["system"]


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(fake):
    app.dependency_overrides[get_llm_client] = lambda: fake


BODY = {"resume_text": RESUME, "job_description": JD, "matcher": "llm"}


def test_endpoint_llm_ok_and_omits_null_fields_for_keyword(client):
    use(FakeClient([req("Python", True, [3])]))
    assert client.post("/match", json=BODY).json()["matcher"].startswith("llm:")
    kw = client.post("/match", json={**BODY, "matcher": "keyword"}).json()
    assert kw["matcher"] == "keyword-baseline" and "usage" not in kw and "importance" not in kw["requirements"][0]


def test_endpoint_default_matcher_is_keyword(client):
    body = {k: v for k, v in BODY.items() if k != "matcher"}
    assert client.post("/match", json=body).json()["matcher"] == "keyword-baseline"


def test_endpoint_missing_key_is_503(client):
    use(None)
    r = client.post("/match", json=BODY)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_endpoint_provider_error_is_502_without_leaking(client):
    use(FakeClient(error=RuntimeError("secret sk-ant-123")))
    r = client.post("/match", json=BODY)
    assert r.status_code == 502 and "sk-ant" not in r.text


def test_endpoint_no_tool_output_is_502(client):
    use(FakeClient(no_tool=True))
    assert client.post("/match", json=BODY).status_code == 502


def test_endpoint_rejects_oversized_text_only_for_llm(client):
    use(FakeClient([]))
    huge = "Python " * 6000
    assert client.post("/match", json={**BODY, "resume_text": huge}).status_code == 422
    assert client.post("/match", json={**BODY, "resume_text": huge, "matcher": "keyword"}).status_code == 200


def test_real_sdk_roundtrip_with_stubbed_transport():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "m", "type": "message", "role": "assistant", "model": seen["body"]["model"], "stop_reason": "tool_use", "stop_sequence": None,
            "content": [{"type": "tool_use", "id": "t", "name": TOOL_NAME, "input": {"requirements": [req("Docker", True, [4])]}}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    sdk = anthropic.Anthropic(api_key="k", http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0)
    out = match(RESUME, JD, sdk, model="claude-haiku-5-5")
    assert seen["body"]["tool_choice"]["name"] == TOOL_NAME and seen["body"]["tools"][0]["name"] == TOOL_NAME
    assert out.requirements[0].evidence[0].line == "Deployed with Docker and GitHub Actions"
