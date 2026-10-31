from evalkit.report import to_markdown
from evalkit.runner import Cache, evaluate
from conftest import FakeLLM


def test_report_has_every_section_and_no_leaked_python_values(example, tmp_path):
    r = evaluate(example, "test", tfidf_thresholds=(0.5, 0.6), llm_runs=2, llm_model="fake-model", cache=Cache(tmp_path), client=FakeLLM(), log=lambda *_: None)
    md = to_markdown(r)
    for heading in ("Requirement-level agreement", "Ranking", "F1 by resume type", "AI matcher stability and cost", "How to read these numbers"):
        assert heading in md
    assert "**test**" in md and r["labels_hash"] in md and "tfidf@0.5" in md and "fake-model" in md
    assert "None" not in md and "nan" not in md.lower().replace("finance", "")


def test_report_still_works_when_nothing_could_be_scored(example):
    r = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=1, llm_model="m", client=None, log=lambda *_: None)
    md = to_markdown(r)
    assert "Incomplete runs" in md
