import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from app import llm_extract
from app.gemini_adapter import MIN_OUTPUT_TOKENS, GeminiClient
from app.llm_extract import LLMUnavailable, default_model, describe_error, get_llm_client, llm_extract as extract
from app.matchers import llm as llm_matcher

PROVIDER_ENV = ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_MODEL", "GEMINI_BASE_URL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


# ---------------- provider selection ----------------
def test_nothing_configured_means_no_client():
    assert get_llm_client() is None


def test_lone_gemini_key_selects_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert isinstance(get_llm_client(), GeminiClient)
    assert default_model() == "gemini-3.5-flash-lite"


def test_google_api_key_name_is_also_accepted(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    assert isinstance(get_llm_client(), GeminiClient)


def test_anthropic_key_selects_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert type(get_llm_client()).__module__.startswith("anthropic")
    assert default_model() == "claude-haiku-5-5"


def test_explicit_provider_beats_guessing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert isinstance(get_llm_client(), GeminiClient)
    get_llm_client.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert type(get_llm_client()).__module__.startswith("anthropic")


def test_chosen_provider_without_its_key_is_not_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")  # wrong provider's key must not be used
    assert get_llm_client() is None


def test_google_key_in_the_anthropic_variable_is_used_for_gemini_not_sent_to_anthropic(monkeypatch, caplog):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "AIzaSyExampleGoogleKey")
    with caplog.at_level("WARNING"):
        client = get_llm_client()
    assert isinstance(client, GeminiClient) and default_model() == "gemini-3.5-flash-lite"
    assert "Rename the variable to GEMINI_API_KEY" in caplog.text and "AIzaSyExample" not in caplog.text


def test_google_key_is_never_sent_to_anthropic_even_when_anthropic_is_forced(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "AIzaSyExampleGoogleKey")
    assert get_llm_client() is None


def test_a_real_anthropic_key_still_wins_over_the_guess(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaOther")
    assert type(get_llm_client()).__module__.startswith("anthropic")


def test_model_env_overrides_the_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.8-flash")
    assert default_model() == "gemini-3.8-flash"


def test_describe_error_includes_status_but_never_the_message():
    class E(Exception):
        code = 429

    assert describe_error(E("secret key AIza123")) == "E 429"
    assert describe_error(ValueError("secret")) == "ValueError"


# ---------------- adapter logic with a fake google client ----------------
SCHEMA_TEXT = "We need Python and Docker experience. Kubernetes is a plus."


class FakeGenai:
    def __init__(self, text=None, usage=(7, 3), error=None):
        self.calls, self._text, self._usage, self._error = [], text, usage, error
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kw):
        self.calls.append(kw)
        if self._error:
            raise self._error
        return SimpleNamespace(text=self._text, usage_metadata=SimpleNamespace(prompt_token_count=self._usage[0], candidates_token_count=self._usage[1]))


def adapter_with(fake):
    client = GeminiClient("k", 5, 0)
    client.messages._client = fake
    return client


GOOD = json.dumps({"skills": [{"name": "Python", "importance": "required", "quote": "Python and Docker"}]})


def test_extraction_through_the_adapter_uses_structured_output():
    fake = FakeGenai(GOOD)
    out = extract(SCHEMA_TEXT, "job_description", adapter_with(fake), model="gemini-3.5-flash-lite")
    assert out.skills == ["Python"] and out.extractor == "llm:gemini-3.5-flash-lite"
    assert out.usage == {"input_tokens": 7, "output_tokens": 3}
    call = fake.calls[0]
    cfg = call["config"]
    assert call["model"] == "gemini-3.5-flash-lite" and call["contents"].startswith("<document>")
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_json_schema == llm_extract.TOOL["input_schema"]  # the same schema the Anthropic tool uses
    assert "untrusted" in cfg.system_instruction and cfg.max_output_tokens >= MIN_OUTPUT_TOKENS


def test_grounding_still_drops_invented_quotes_with_gemini():
    bad = json.dumps({"skills": [{"name": "Rust", "importance": "required", "quote": "ten years of Rust"}] + json.loads(GOOD)["skills"]})
    out = extract(SCHEMA_TEXT, "job_description", adapter_with(FakeGenai(bad)))
    assert out.skills == ["Python"] and out.dropped == 1


def test_matcher_through_the_adapter_returns_resume_lines_not_model_text():
    reply = json.dumps({"requirements": [
        {"requirement": "Docker", "importance": "required", "supported": True, "evidence_lines": [2], "note": "named"},
        {"requirement": "Terraform", "importance": "preferred", "supported": True, "evidence_lines": [99], "note": "made up"},
    ]})
    out = llm_matcher.match("Jane\nDeployed with Docker", "Docker, Terraform", adapter_with(FakeGenai(reply)), model="m")
    assert out.requirements[0].evidence[0].line == "Deployed with Docker"
    assert out.requirements[1].supported is False and out.ungrounded == 1


@pytest.mark.parametrize("text", [None, "", "{not json", '{"skills": [1,'])
def test_empty_or_broken_output_becomes_a_clean_llm_error(text):
    with pytest.raises(LLMUnavailable) as err:
        extract(SCHEMA_TEXT, "job_description", adapter_with(FakeGenai(text)))
    assert "LLM request failed" in str(err.value)


def test_provider_errors_are_reported_with_status_but_without_details():
    class Quota(Exception):
        code = 429

    with pytest.raises(LLMUnavailable) as err:
        extract(SCHEMA_TEXT, "job_description", adapter_with(FakeGenai(error=Quota("key AIza-secret exhausted"))))
    assert str(err.value) == "LLM request failed (Quota 429)" and "AIza" not in str(err.value)


# ---------------- the real Google SDK against a local stand-in server ----------------
class _Server:
    def __init__(self, status=200):
        outer = self
        self.requests, self.status = [], status

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                outer.requests.append({"path": self.path, "key": self.headers.get("x-goog-api-key"), "body": body})
                if outer.status != 200:
                    payload = {"error": {"code": outer.status, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
                else:
                    payload = {
                        "candidates": [{"content": {"role": "model", "parts": [{"text": GOOD}]}, "finishReason": "STOP"}],
                        "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 9, "totalTokenCount": 30},
                    }
                data = json.dumps(payload).encode()
                self.send_response(outer.status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    s = _Server()
    yield s
    s.close()


def test_real_sdk_request_and_response(server, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_BASE_URL", server.url)
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    out = extract(SCHEMA_TEXT, "job_description", get_llm_client())

    assert out.skills == ["Python"] and out.usage == {"input_tokens": 21, "output_tokens": 9}
    req = server.requests[0]
    assert req["path"] == "/v1beta/models/gemini-3.5-flash-lite:generateContent" and req["key"] == "test-key"
    assert sorted(req["body"]) == ["contents", "generationConfig", "systemInstruction"]
    gen = req["body"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and gen["responseJsonSchema"]["required"] == ["skills"]
    assert "importance" in json.dumps(gen["responseJsonSchema"])


def test_real_sdk_quota_error_maps_to_502_detail_with_code(monkeypatch):
    s = _Server(status=429)
    try:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_BASE_URL", s.url)
        monkeypatch.setenv("LLM_MAX_RETRIES", "0")
        with pytest.raises(LLMUnavailable) as err:
            extract(SCHEMA_TEXT, "job_description", get_llm_client())
        assert str(err.value) == "LLM request failed (ClientError 429)"
    finally:
        s.close()


def test_endpoints_work_end_to_end_with_gemini(server, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_BASE_URL", server.url)
    c = TestClient(app)
    r = c.post("/extract", json={"text": SCHEMA_TEXT, "method": "llm"})
    assert r.status_code == 200 and r.json()["extractor"] == "llm:gemini-3.5-flash-lite"
