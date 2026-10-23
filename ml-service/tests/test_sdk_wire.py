"""Runs the real Anthropic SDK against a stubbed HTTP transport.

This proves our request is accepted by the SDK (parameter names, tool schema) and that
a Messages-API-shaped response is parsed correctly, without needing a key or network.
"""
import json

import anthropic
import httpx2 as httpx

from app.llm_extract import TOOL_NAME, llm_extract

TEXT = "We need Python and Docker experience. Kubernetes is a plus."


def test_real_sdk_roundtrip_with_stubbed_transport():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("authorization", "")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": seen["body"]["model"],
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_test",
                        "name": TOOL_NAME,
                        "input": {
                            "skills": [
                                {"name": "Python", "importance": "required", "quote": "Python and Docker experience"},
                                {"name": "Kubernetes", "importance": "preferred", "quote": "Kubernetes is a plus"},
                            ]
                        },
                    }
                ],
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "usage": {"input_tokens": 80, "output_tokens": 30},
            },
        )

    client = anthropic.Anthropic(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0
    )
    out = llm_extract(TEXT, "job_description", client, model="claude-haiku-5-5")

    assert seen["path"].endswith("/v1/messages") and "test-key" in seen["key"]
    assert seen["body"]["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert seen["body"]["tools"][0]["name"] == TOOL_NAME
    assert seen["body"]["messages"][0]["content"].startswith("<document>")
    assert out.skills == ["Kubernetes", "Python"]
    assert out.usage == {"input_tokens": 80, "output_tokens": 30}


def test_real_sdk_http_error_becomes_llm_unavailable():
    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "boom"}}))),
        max_retries=0,
    )
    try:
        llm_extract(TEXT, "job_description", client)
    except Exception as err:
        assert type(err).__name__ == "LLMUnavailable"
    else:
        raise AssertionError("expected LLMUnavailable")
