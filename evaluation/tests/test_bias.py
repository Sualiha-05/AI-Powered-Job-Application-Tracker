from evalkit.bias import audit, load_names, planned_calls, replace_name, select_pairs, to_markdown
from evalkit.runner import Cache, MatcherConfig
from app.matchers.common import numbered_lines
from conftest import EXAMPLE, FakeLLM

NAMES = load_names(EXAMPLE.parent / "names.json")
CFG = MatcherConfig("llm", model="m")


def test_only_the_first_line_changes_and_line_numbers_are_preserved(example):
    for resume in example.resumes.values():
        swapped = replace_name(resume.text, "Emily Walsh")
        before, after = resume.text.split("\n"), swapped.split("\n")
        assert after[0] == "Emily Walsh" and after[1:] == before[1:] and len(before) == len(after)
        assert list(numbered_lines(swapped)) == list(numbered_lines(resume.text))


def test_name_replacement_skips_leading_blank_lines():
    assert replace_name("\n\nJane Doe\nBuilt things", "Emily Walsh") == "\n\nEmily Walsh\nBuilt things"


def test_names_file_has_groups_with_enough_names():
    assert len(NAMES) == 4 and all(len(v) >= 3 for v in NAMES.values())


def test_deterministic_matchers_ignore_names_on_the_example(example):
    pairs = select_pairs(example, "all", 12)
    for cfg in (MatcherConfig("keyword"), MatcherConfig("tfidf", threshold=0.6)):
        r = audit(example, cfg, NAMES, pairs, Cache(None), None, names_per_group=2, repeats=2, log=lambda *_: None)
        assert r["n_variants"] == 12 * 8 and r["name_flip_rate"] == 0 and r["noise_flip_rate"] == 0 and r["excess_flip_rate"] == 0


def test_a_biased_ai_is_caught_and_noise_is_kept_separate(example, tmp_path):
    black = {n for g in ("black_female", "black_male") for n in NAMES[g]}

    def biased(lines, call_no):
        base = FakeLLM.default(lines, call_no)
        if lines.get(1) in black:                       # an unfair matcher: drops "Docker" support for some names
            base[1]["supported"], base[1]["evidence_lines"] = False, []
        return base

    pairs = [p for p in select_pairs(example, "all", 12) if p.resume == "strong-backend"]
    r = audit(example, CFG, NAMES, pairs, Cache(tmp_path), FakeLLM(biased), names_per_group=3, repeats=2, log=lambda *_: None)
    assert r["noise_flip_rate"] == 0                    # same name twice: identical, so flips below are caused by the name
    assert r["excess_flip_rate"] > 0 and r["variants_with_any_flip"] > 0 and r["examples"]
    assert all(e["group"].startswith("black") for e in r["examples"])
    gap = next(g for g in r["group_gaps"] if (g["a"], g["b"]) == ("white_female", "black_female"))
    assert gap["mean_gap"] > 0 and gap["max_abs_gap"] > 0


def test_random_noise_is_not_blamed_on_names(example, tmp_path):
    def noisy(lines, call_no):                          # answer depends only on the call counter, never on the name
        base = FakeLLM.default(lines, call_no)
        if call_no % 2 == 0:
            base[1]["supported"], base[1]["evidence_lines"] = False, []
        return base
    pairs = [p for p in select_pairs(example, "all", 12) if p.resume == "strong-backend"]
    r = audit(example, CFG, NAMES, pairs, Cache(tmp_path), FakeLLM(noisy), names_per_group=2, repeats=2, log=lambda *_: None)
    assert r["noise_flip_rate"] > 0 and r["name_flip_rate"] > 0     # flips exist...
    assert r["excess_flip_rate"] <= r["name_flip_rate"]             # ...and the report separates them from the noise baseline


def test_audit_results_are_cached_and_the_call_plan_is_accurate(example, tmp_path):
    pairs = select_pairs(example, "all", 3)
    client, cache = FakeLLM(), Cache(tmp_path)
    audit(example, CFG, NAMES, pairs, cache, client, names_per_group=2, repeats=2, log=lambda *_: None)
    assert client.calls == planned_calls(3, NAMES, 2, 2) == 3 * (2 + 8)
    audit(example, CFG, NAMES, pairs, cache, client, names_per_group=2, repeats=2, log=lambda *_: None)
    assert client.calls == 30


def test_audit_survives_provider_failures(example):
    r = audit(example, CFG, NAMES, select_pairs(example, "all", 2), Cache(None), FakeLLM(error=RuntimeError("quota")), log=lambda *_: None)
    assert r["errors"] == 2 and r["n_variants"] == 0 and r["name_flip_rate"] is None
    assert "n/a" in to_markdown([r], NAMES)


def test_markdown_report_explains_its_limits(example):
    r = audit(example, MatcherConfig("keyword"), NAMES, select_pairs(example, "all", 2), Cache(None), None, names_per_group=1, log=lambda *_: None)
    md = to_markdown([r], NAMES)
    assert "illustrative" in md and "small sample cannot show the absence of bias" in md and "None" not in md
