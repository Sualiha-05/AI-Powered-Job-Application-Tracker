from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.llm_extract import TOOL_NAME, get_llm_client
from app.main import app

JD = """Backend Engineer
Requirements: 3+ years of Python and ReactJS experience. You must know PostgreSQL.
Nice to have: Kubernetes."""


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create(...) and records the call."""

    def __init__(self, items=None, error: Exception | None = None, no_tool=False):
        self.items, self.error, self.no_tool, self.calls = items or [], error, no_tool, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = [] if self.no_tool else [SimpleNamespace(type="tool_use", name=TOOL_NAME, input={"skills": self.items})]
        return SimpleNamespace(content=content, usage=SimpleNamespace(input_tokens=120, output_tokens=40))


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(fake):
    app.dependency_overrides[get_llm_client] = lambda: fake


def post(client, **extra):
    return client.post("/extract", json={"text": JD, "method": "llm", **extra})


def test_default_method_is_still_keyword(client):
    r = client.post("/extract", json={"text": JD})
    assert r.status_code == 200 and r.json()["extractor"] == "keyword-baseline"


def test_llm_extracts_grounded_skills_and_canonicalizes(client):
    use(FakeClient([
        {"name": "Python", "importance": "required", "quote": "3+ years of Python"},
        {"name": "ReactJS", "importance": "required", "quote": "ReactJS experience"},
        {"name": "Kubernetes", "importance": "preferred", "quote": "Nice to have: Kubernetes"},
    ]))
    body = post(client).json()
    assert body["skills"] == ["Kubernetes", "Python", "React"]  # ReactJS -> React
    assert body["extractor"].startswith("llm:")
    assert {d["name"]: d["importance"] for d in body["details"]}["Kubernetes"] == "preferred"
    assert body["usage"] == {"input_tokens": 120, "output_tokens": 40}


def test_hallucinated_skills_are_dropped(client):
    use(FakeClient([
        {"name": "Python", "importance": "required", "quote": "3+ years of Python"},
        {"name": "Rust", "importance": "required", "quote": "5 years of Rust in production"},  # not in the text
        {"name": "Go", "importance": "required", "quote": ""},
        {"name": 123, "quote": "x"},
    ]))
    body = post(client).json()
    assert body["skills"] == ["Python"]
    assert body["dropped"] == 3


def test_quote_matching_ignores_case_and_whitespace(client):
    use(FakeClient([{"name": "PostgreSQL", "importance": "required", "quote": "you MUST   know\nPostgreSQL"}]))
    assert post(client).json()["skills"] == ["PostgreSQL"]


def test_duplicate_skill_keeps_required_over_preferred(client):
    use(FakeClient([
        {"name": "Python", "importance": "preferred", "quote": "Python"},
        {"name": "python", "importance": "required", "quote": "3+ years of Python"},
    ]))
    details = post(client).json()["details"]
    assert len(details) == 1 and details[0]["importance"] == "required"


def test_request_is_forced_tool_call_with_untrusted_text_wrapped(client):
    fake = FakeClient([])
    use(fake)
    post(client)
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert call["messages"][0]["content"].startswith("<document>") and JD in call["messages"][0]["content"]
    assert "untrusted" in call["system"]


def test_resume_kind_uses_resume_prompt(client):
    fake = FakeClient([])
    use(fake)
    post(client, kind="resume")
    assert "resume" in fake.calls[0]["system"].lower()


def test_missing_api_key_is_503_not_silent_fallback(client):
    use(None)
    r = post(client)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_provider_error_is_502_and_does_not_leak_details(client):
    use(FakeClient(error=RuntimeError("secret sk-ant-123 failed")))
    r = post(client)
    assert r.status_code == 502 and "sk-ant" not in r.text


def test_model_without_tool_output_is_502(client):
    use(FakeClient(no_tool=True))
    assert post(client).status_code == 502


def test_oversized_text_rejected(client):
    r = client.post("/extract", json={"text": "x" * 30_001, "method": "llm"})
    assert r.status_code == 422


def test_client_timeout_and_retries_are_configurable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "8")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    get_llm_client.cache_clear()
    try:
        c = get_llm_client()
        assert c.max_retries == 0 and float(c.timeout) == 8.0
    finally:
        get_llm_client.cache_clear()
