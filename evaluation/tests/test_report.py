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


def test_tag_table_shows_accuracy_when_f1_is_undefined(example):
    r = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(0.6,))
    r["runs"][0]["per_tag"]["weak"].update(f1=None, accuracy=1.0)
    assert "F1 undefined, accuracy 1.00" in to_markdown(r)


def test_a_threshold_sweep_that_changes_nothing_is_called_out(example):
    sweep = evaluate(example.__class__(example.root, {k: v for k, v in example.postings.items() if k == "qa-automation"},
                                       example.resumes, [p for p in example.pairs if p.posting == "qa-automation"]),
                     "all", use_keyword=False, tfidf_thresholds=(0.5, 0.55))
    assert len({(r["tp"], r["fp"], r["fn"], r["tn"]) for r in sweep["runs"]}) == 1      # identical on this tiny slice
    assert "did not separate the thresholds" in to_markdown(sweep)
    assert "did not separate" not in to_markdown(evaluate(example, "all", use_keyword=False, tfidf_thresholds=(0.3, 0.9)))


def test_each_ai_repeat_is_labeled_in_the_evidence_list_and_pm_is_explained(example, tmp_path):
    r = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=2, llm_model="m", cache=Cache(tmp_path), client=FakeLLM(), log=lambda *_: None)
    md = to_markdown(r)
    assert "- llm:m #1:" in md and "- llm:m #2:" in md
    assert "± is the spread between repeats" in md and "not a confidence interval" in md
