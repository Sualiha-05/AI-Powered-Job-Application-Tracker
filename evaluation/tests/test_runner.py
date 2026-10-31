import pytest

from evalkit.runner import (Cache, MatcherConfig, PairResult, aggregate_llm, cache_key, count_uncached_llm_calls, evaluate, run_config, score_run)
from conftest import FakeLLM


def oracle_results(ds, pairs, *, invert=False, say_nothing=False):
    """A pretend matcher that copies the gold labels exactly (or inverts them, or never says 'supported')."""
    out = []
    for p in pairs:
        reqs = []
        for g in ds.postings[p.posting].requirements:
            gold = g.id in p.supported
            supported = (not gold if invert else gold) and not say_nothing
            ev = [{"line": "x", "line_number": n} for n in p.evidence.get(g.id, [])] if supported and not invert else []
            reqs.append({"requirement": g.label, "supported": supported, "evidence": ev})
        score = sum(r["supported"] for r in reqs) / len(reqs) if reqs else 0.0
        out.append(PairResult(p, {"requirements": reqs, "score": score, "missing": []}))
    return out


def test_a_matcher_that_copies_the_labels_scores_perfectly(example):
    s = score_run(MatcherConfig("keyword"), oracle_results(example, example.pairs), example)
    assert (s["precision"], s["recall"], s["f1"], s["accuracy"], s["coverage"]) == (1, 1, 1, 1, 1)
    assert s["spearman_overall"] == pytest.approx(1.0) and s["evidence_hit_rate"] == 1 and s["mismatches"] == []
    assert s["n_requirements"] == sum(len(example.postings[p.posting].requirements) for p in example.pairs)


def test_a_matcher_that_never_says_supported_has_zero_recall(example):
    s = score_run(MatcherConfig("keyword"), oracle_results(example, example.pairs, say_nothing=True), example)
    assert s["recall"] == 0 and s["precision"] is None and s["tp"] == 0 and s["fn"] == 24
    assert s["spearman_overall"] is None          # every score is 0: ranking is undefined, not "0"


def test_an_inverted_matcher_is_wrong_everywhere(example):
    s = score_run(MatcherConfig("keyword"), oracle_results(example, example.pairs, invert=True), example)
    assert s["accuracy"] == 0 and s["spearman_overall"] < 0 and len(s["mismatches"]) == s["n_requirements"]


def test_tags_split_the_scores_by_resume_type(example):
    s = score_run(MatcherConfig("keyword"), oracle_results(example, example.pairs), example)
    assert set(s["per_tag"]) == {"strong", "weak", "synonyms", "aspiration"}
    assert sum(t["n"] for t in s["per_tag"].values()) == s["n_requirements"]


def test_real_deterministic_matchers_on_the_example(example):
    r = evaluate(example, "all", tfidf_thresholds=(0.4, 0.6))
    assert [x["label"] for x in r["runs"]] == ["keyword", "tfidf@0.4", "tfidf@0.6"]
    for x in r["runs"]:
        assert x["n_pairs"] == 12 and not x["incomplete"]
        assert 0 <= x["accuracy"] <= 1 and x["tp"] + x["fp"] + x["fn"] + x["tn"] == x["n_requirements"]
    assert r == evaluate(example, "all", tfidf_thresholds=(0.4, 0.6))     # deterministic
    assert r["n_pairs"] == 12 and r["labels_hash"]


def test_split_selects_only_that_splits_pairs(example):
    assert evaluate(example, "dev")["n_pairs"] == 4 and evaluate(example, "test")["n_pairs"] == 8


# ---------------- AI matcher: caching, failures, stability ----------------
def test_ai_results_are_cached_so_a_second_run_makes_no_calls(example, tmp_path):
    client, cache = FakeLLM(), Cache(tmp_path)
    kw = dict(use_keyword=False, tfidf_thresholds=(), llm_runs=2, llm_model="m", cache=cache, client=client, log=lambda *_: None)
    first = evaluate(example, "all", **kw)
    assert client.calls == 24                                                  # 12 pairs x 2 repeats
    assert evaluate(example, "all", **kw)["llm_aggregate"]["f1"] == first["llm_aggregate"]["f1"] and client.calls == 24
    assert len(list(tmp_path.glob("*.json"))) == 24


def test_changing_a_resume_or_the_repeat_number_invalidates_the_cache():
    a = MatcherConfig("llm", model="m", run=1)
    assert cache_key(a, "jd", "resume") == cache_key(a, "jd", "resume")
    assert cache_key(a, "jd", "resume") != cache_key(a, "jd", "resume edited")
    assert cache_key(a, "jd", "resume") != cache_key(MatcherConfig("llm", model="m", run=2), "jd", "resume")
    assert cache_key(a, "jd", "resume") != cache_key(MatcherConfig("llm", model="other", run=1), "jd", "resume")


def test_uncached_call_estimate(example, tmp_path):
    cache, client = Cache(tmp_path), FakeLLM()
    cfgs = [MatcherConfig("llm", model="m", run=i) for i in (1, 2)]
    assert count_uncached_llm_calls(example, example.pairs, cfgs, cache) == 24
    run_config(cfgs[0], example, example.pairs, cache, client, log=lambda *_: None)
    assert count_uncached_llm_calls(example, example.pairs, cfgs, cache) == 12


def test_repeated_failures_stop_the_run_early_and_flag_it_incomplete(example, tmp_path):
    from app.llm_extract import LLMUnavailable
    client = FakeLLM(error=RuntimeError("quota"))        # provider errors become LLMUnavailable inside the matcher
    msgs = []
    r = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=1, llm_model="m", cache=Cache(tmp_path), client=client, log=msgs.append)
    run = r["runs"][0]
    assert client.calls == 3 and run["incomplete"] and run["n_pairs"] == 0 and run["n_pairs_failed"] == 3
    assert r["llm_aggregate"] is None and any("stopping" in m for m in msgs)


def test_a_missing_key_is_reported_per_pair_not_as_a_crash(example, tmp_path):
    r = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=1, llm_model="m", cache=Cache(tmp_path), client=None, log=lambda *_: None)
    assert r["runs"][0]["incomplete"]


def test_stability_measures_agreement_between_repeats(example, tmp_path):
    def flaky(lines, call_no):                            # repeat 1 and 2 disagree about Docker
        base = FakeLLM.default(lines, call_no)
        if call_no > 12:
            base[1]["supported"], base[1]["evidence_lines"] = False, []
        return base
    steady = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=2, llm_model="m", cache=Cache(tmp_path / "a"), client=FakeLLM(), log=lambda *_: None)
    unsteady = evaluate(example, "all", use_keyword=False, tfidf_thresholds=(), llm_runs=2, llm_model="m", cache=Cache(tmp_path / "b"), client=FakeLLM(flaky), log=lambda *_: None)
    assert steady["llm_aggregate"]["decision_agreement"] == 1.0
    assert unsteady["llm_aggregate"]["decision_agreement"] < 1.0
    assert unsteady["llm_aggregate"]["f1"][1] > 0       # nonzero spread between repeats
    assert unsteady["llm_aggregate"]["tokens_in"] == 240


def test_aggregate_ignores_incomplete_runs():
    assert aggregate_llm([{"incomplete": True, "n_pairs": 0}]) is None
