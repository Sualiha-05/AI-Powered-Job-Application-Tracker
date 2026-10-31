"""Runs the matchers on a dataset and scores them against the gold labels.

Only AI (LLM) results are cached on disk, because they cost quota and vary between runs. Keyword and TF-IDF are cheap and
deterministic, so they are recomputed every time and can never be served stale after a code change.
"""
import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import _paths  # noqa: F401
from app.llm_extract import LLMNotConfigured, LLMUnavailable
from app.matchers import keyword, tfidf
from app.matchers import llm as llm_matcher

from .matching import map_to_gold
from .metrics import bootstrap_ci, confusion, mean_std, prf, spearman
from .schema import Dataset, Pair

MAX_MISMATCHES = 200


@dataclass(frozen=True)
class MatcherConfig:
    name: str  # "keyword" | "tfidf" | "llm"
    threshold: float | None = None  # tfidf only
    model: str | None = None  # llm only
    run: int = 1  # llm only: repeat number

    @property
    def label(self) -> str:
        if self.name == "tfidf":
            return f"tfidf@{self.threshold:g}"
        if self.name == "llm":
            return f"llm:{self.model}"
        return self.name

    @property
    def is_llm(self) -> bool:
        return self.name == "llm"


@dataclass
class PairResult:
    pair: Pair
    output: dict | None
    error: str | None = None
    cached: bool = False


class Cache:
    def __init__(self, directory: Path | None):
        self.directory = Path(directory) if directory else None
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)

    def _file(self, key: str) -> Path:
        return self.directory / (hashlib.sha1(key.encode()).hexdigest() + ".json")

    def get(self, key: str) -> dict | None:
        if not self.directory or not self._file(key).exists():
            return None
        try:
            return json.loads(self._file(key).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def put(self, key: str, value: dict) -> None:
        if self.directory:
            self._file(key).write_text(json.dumps(value), encoding="utf-8")


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def cache_key(cfg: MatcherConfig, jd_text: str, resume_text: str) -> str:
    # The prompt and schema are part of the key: editing them must not reuse answers produced by the old ones.
    prompt = _sha(llm_matcher.SYSTEM_PROMPT + json.dumps(llm_matcher.TOOL, sort_keys=True))
    return json.dumps([cfg.name, cfg.model, cfg.run, _sha(jd_text), _sha(resume_text), prompt])


@contextlib.contextmanager
def _env(name: str, value: str):
    old = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def call_matcher(cfg: MatcherConfig, resume_text: str, jd_text: str, client: Any) -> dict:
    if cfg.name == "keyword":
        out = keyword.match(resume_text, jd_text)
    elif cfg.name == "tfidf":
        with _env("TFIDF_THRESHOLD", str(cfg.threshold)):
            out = tfidf.match(resume_text, jd_text)
    elif cfg.name == "llm":
        out = llm_matcher.match(resume_text, jd_text, client, model=cfg.model)
    else:
        raise ValueError(f"unknown matcher {cfg.name!r}")
    return out.model_dump(exclude_none=True)


def call_with_cache(cfg: MatcherConfig, resume_text: str, jd_text: str, cache: Cache, client: Any, sleep: float = 0.0):
    """Returns (output or None, error or None, was_cached)."""
    key = cache_key(cfg, jd_text, resume_text) if cfg.is_llm else None
    if key and (hit := cache.get(key)) is not None:
        return hit, None, True
    try:
        out = call_matcher(cfg, resume_text, jd_text, client)
    except (LLMNotConfigured, LLMUnavailable) as err:
        return None, str(err), False
    if key:
        cache.put(key, out)
        if sleep:
            time.sleep(sleep)  # stay under free-tier requests-per-minute limits
    return out, None, False


def run_config(cfg, dataset: Dataset, pairs: list[Pair], cache: Cache, client, sleep=0.0, max_consecutive_failures=3, log=print):
    results: list[PairResult] = []
    failures = 0
    for pair in pairs:
        posting, resume = dataset.postings[pair.posting], dataset.resumes[pair.resume]
        out, err, cached = call_with_cache(cfg, resume.text, posting.text, cache, client, sleep)
        results.append(PairResult(pair, out, err, cached))
        failures = failures + 1 if err else 0
        if err:
            log(f"  ! {cfg.label} {pair.posting} x {pair.resume}: {err}")
        if failures >= max_consecutive_failures:
            log(f"  ! stopping {cfg.label} after {failures} failures in a row (progress is cached; run again later)")
            break
    return results


def count_uncached_llm_calls(dataset: Dataset, pairs: list[Pair], cfgs: list[MatcherConfig], cache: Cache) -> int:
    return sum(
        1
        for cfg in cfgs
        for p in pairs
        if cache.get(cache_key(cfg, dataset.postings[p.posting].text, dataset.resumes[p.resume].text)) is None
    )


def score_run(cfg: MatcherConfig, results: list[PairResult], dataset: Dataset) -> dict:
    done = [r for r in results if r.output is not None]
    pair_decisions: dict[tuple[str, str], list[tuple[bool, bool]]] = {}
    decisions_flat: list[tuple[bool, bool]] = []
    per_tag: dict[str, list[tuple[bool, bool]]] = {}
    decision_map: dict[str, bool] = {}
    mismatches: list[dict] = []
    covered = total = ev_hits = ev_n = 0
    scores, fits, by_posting = [], [], {}

    for r in done:
        posting, resume = dataset.postings[r.pair.posting], dataset.resumes[r.pair.resume]
        mapped = {d.gold_id: d for d in map_to_gold(posting.requirements, r.output.get("requirements", []))}
        decisions = []
        for g in posting.requirements:
            d, gold = mapped[g.id], g.id in r.pair.supported
            decisions.append((gold, d.predicted))
            decision_map[f"{posting.id}|{resume.id}|{g.id}"] = d.predicted
            total += 1
            covered += d.covered
            for tag in resume.tags:
                per_tag.setdefault(tag, []).append((gold, d.predicted))
            if gold and d.predicted and r.pair.evidence.get(g.id):
                ev_n += 1
                ev_hits += bool(d.evidence_lines & set(r.pair.evidence[g.id]))
            if gold != d.predicted and len(mismatches) < MAX_MISMATCHES:
                mismatches.append(
                    {"posting": posting.id, "resume": resume.id, "requirement": g.label, "gold": gold,
                     "predicted": d.predicted, "covered": d.covered, "matcher_labels": d.matched_labels}
                )
        pair_decisions[(posting.id, resume.id)] = decisions
        decisions_flat += decisions
        if posting.requirements:
            fit = len(r.pair.supported & {g.id for g in posting.requirements}) / len(posting.requirements)
            scores.append(r.output.get("score", 0.0))
            fits.append(fit)
            by_posting.setdefault(posting.id, ([], []))
            by_posting[posting.id][0].append(r.output.get("score", 0.0))
            by_posting[posting.id][1].append(fit)

    c = confusion(decisions_flat)
    per_posting = [s for s in (spearman(a, b) for a, b in by_posting.values()) if s is not None]
    ci = bootstrap_ci(list(pair_decisions.values()), lambda sample: prf(confusion([d for p in sample for d in p]))["f1"])
    usage = [r.output.get("usage") or {} for r in done]
    return {
        "label": cfg.label, "matcher": cfg.name, "run": cfg.run,
        "n_pairs": len(done), "n_pairs_failed": len(results) - len(done), "incomplete": len(done) < len(results),
        "n_requirements": total, "coverage": covered / total if total else None,
        **c, **prf(c), "f1_ci": list(ci) if ci else None,
        "spearman_overall": spearman(scores, fits), "spearman_per_posting_mean": (sum(per_posting) / len(per_posting)) if per_posting else None,
        "n_postings_ranked": len(per_posting),
        "evidence_hit_rate": ev_hits / ev_n if ev_n else None, "evidence_n": ev_n,
        "per_tag": {t: {"n": len(d), **prf(confusion(d))} for t, d in sorted(per_tag.items())},
        "ungrounded": sum(r.output.get("ungrounded") or 0 for r in done),
        "tokens_in": sum(u.get("input_tokens", 0) for u in usage), "tokens_out": sum(u.get("output_tokens", 0) for u in usage),
        "mismatches": mismatches, "decision_map": decision_map,
    }


def aggregate_llm(runs: list[dict]) -> dict | None:
    """Several repeats of the AI matcher: mean and spread of each metric, and how often repeats agree."""
    complete = [r for r in runs if not r["incomplete"] and r["n_pairs"]]
    if not complete:
        return None
    out: dict[str, Any] = {"label": complete[0]["label"], "runs": len(complete), "runs_requested": len(runs)}
    for m in ("precision", "recall", "f1", "accuracy", "spearman_overall", "spearman_per_posting_mean", "coverage"):
        out[m] = mean_std([r[m] for r in complete])
    keys = set(complete[0]["decision_map"])
    agree = sum(len({r["decision_map"][k] for r in complete}) == 1 for k in keys)
    out["decision_agreement"] = agree / len(keys) if keys else None
    out["ungrounded_mean"] = sum(r["ungrounded"] for r in complete) / len(complete)
    out["tokens_in"], out["tokens_out"] = sum(r["tokens_in"] for r in runs), sum(r["tokens_out"] for r in runs)
    return out


def labels_hash(dataset: Dataset) -> str:
    return _sha((dataset.root / "labels.json").read_text(encoding="utf-8"))[:12]


def evaluate(dataset: Dataset, split: str, *, use_keyword=True, tfidf_thresholds=(0.6,), llm_runs=0, llm_model=None,
             cache: Cache | None = None, client=None, sleep=0.0, log=print) -> dict:
    pairs = dataset.pairs_in(split)
    cache = cache or Cache(None)
    cfgs = ([MatcherConfig("keyword")] if use_keyword else []) + [MatcherConfig("tfidf", threshold=t) for t in tfidf_thresholds]
    llm_cfgs = [MatcherConfig("llm", model=llm_model, run=i) for i in range(1, llm_runs + 1)]

    scored = []
    for cfg in cfgs + llm_cfgs:
        log(f"running {cfg.label}" + (f" (repeat {cfg.run})" if cfg.is_llm else "") + f" on {len(pairs)} pairs")
        results = run_config(cfg, dataset, pairs, cache, client, sleep, log=log)
        scored.append(score_run(cfg, results, dataset))
    llm_scored = [s for s in scored if s["matcher"] == "llm"]
    return {
        "split": split, "n_postings": len({p.posting for p in pairs}), "n_resumes": len({p.resume for p in pairs}), "n_pairs": len(pairs),
        "n_gold_requirements": sum(len(dataset.postings[p.posting].requirements) for p in pairs),
        "labels_hash": labels_hash(dataset), "dataset": str(dataset.root), "tfidf_thresholds": list(tfidf_thresholds),
        "llm_model": llm_model, "llm_runs": llm_runs,
        "runs": scored, "llm_aggregate": aggregate_llm(llm_scored) if llm_scored else None,
    }
