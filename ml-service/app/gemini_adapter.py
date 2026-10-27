"""Makes the Google Gemini API look like the Anthropic client the rest of the code was written for.

The extractor and the LLM matcher call `client.messages.create(model=..., system=..., tools=[...], tool_choice=...,
messages=[...])` and read a `tool_use` block from the reply. This adapter accepts exactly that call, asks Gemini for
JSON that follows the forced tool's input schema (structured output), and returns a reply in the same shape. That keeps
both features, and all their tests, independent of which provider is configured.

Differences worth knowing:
  * Gemini returns JSON text, not a tool call. If the text is not valid JSON (for example it was cut off), the call
    fails and the caller reports a clean 502.
  * Usage numbers come from Gemini's usage metadata.
"""
import json
from types import SimpleNamespace
from typing import Any

# Leave room for the model's own reasoning tokens, which may count against the output limit on some models.
MIN_OUTPUT_TOKENS = 8192


class _Messages:
    def __init__(self, client: Any):
        self._client = client

    def create(self, *, model: str, max_tokens: int, system: str, tools: list[dict], tool_choice: dict, messages: list[dict], **_: Any):
        from google.genai import types

        tool = next(t for t in tools if t["name"] == tool_choice["name"])
        response = self._client.models.generate_content(
            model=model,
            contents=messages[0]["content"],
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max(max_tokens, MIN_OUTPUT_TOKENS),
                response_mime_type="application/json",
                response_json_schema=tool["input_schema"],
            ),
        )
        text = response.text
        if not text:
            raise ValueError("empty response (possibly blocked)")
        usage = response.usage_metadata
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name=tool["name"], input=json.loads(text))],
            usage=SimpleNamespace(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            ),
        )


class GeminiClient:
    """Drop-in for the small part of the Anthropic client this project uses."""

    provider = "gemini"

    def __init__(self, api_key: str, timeout_seconds: float, max_retries: int, base_url: str | None = None):
        from google import genai
        from google.genai import types

        self._genai = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=max_retries + 1),
                **({"base_url": base_url} if base_url else {}),
            ),
        )
        self.messages = _Messages(self._genai)
