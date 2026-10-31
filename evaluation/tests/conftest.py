import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import evalkit  # noqa: F401  (adds ml-service to sys.path)
from app.matchers import llm as llm_matcher

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "example"


class FakeLLM:
    """Stands in for the provider client: answers from the numbered resume lines it is given, and counts calls."""

    def __init__(self, fn=None, error=None):
        self.calls, self.error = 0, error
        self.fn = fn or self.default
        self.messages = SimpleNamespace(create=self._create)

    @staticmethod
    def default(lines, call_no):
        def find(word):
            return [n for n, t in lines.items() if word in t.lower()]
        return [
            {"requirement": "Python", "importance": "required", "supported": bool(find("python")), "evidence_lines": find("python")[:1], "note": ""},
            {"requirement": "Docker", "importance": "required", "supported": bool(find("docker")), "evidence_lines": find("docker")[:1], "note": ""},
        ]

    def _create(self, **kw):
        self.calls += 1
        if self.error:
            raise self.error
        lines = {int(n): t for n, t in re.findall(r"^L(\d+): (.*)$", kw["messages"][0]["content"], re.M)}
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name=llm_matcher.TOOL_NAME, input={"requirements": self.fn(lines, self.calls)})],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


@pytest.fixture
def example():
    from evalkit.schema import load_dataset

    return load_dataset(EXAMPLE)


@pytest.fixture
def fake_llm():
    return FakeLLM
