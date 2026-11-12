"""Name-swap audit.

Take a resume, change ONLY the name on its first line, and see whether the matcher's decisions or score change.

Because AI answers vary between runs, a decision that flips when the name changes may just be noise. So the audit also
measures the same resume run twice with the SAME name (the noise baseline). Only flips beyond that baseline point at the name.
Keyword and TF-IDF are deterministic, so their baseline is 0; for TF-IDF a name still shifts the word statistics slightly,
which is exactly the kind of side effect this audit is meant to expose.
"""
import json
from pathlib import Path

from . import _paths  # noqa: F401
from .matching import map_to_gold
from .runner import Cache, MatcherConfig, call_with_cache
from .schema import Dataset, Pair


def replace_name(resume_text: str, name: str) -> str:
    """Replaces the first non-blank line (the candidate name) and nothing else, so line numbers stay identical."""
    lines = resume_text.split("\n")
    for i, line in enumerate(lines):
        if line.strip():
            lines[i] = name
            break
    return "\n".join(lines)


def load_names(path: Path) -> dict[str, list[str]]:
    groups = json.loads(Path(path).read_text(encoding="utf-8"))["groups"]
    return {g: list(names) for g, names in groups.items()}


def select_pairs(dataset: Dataset, split: str, max_pairs: int) -> list[Pair]:
    pairs = sorted(dataset.pairs_in(split), key=lambda p: (p.posting, p.resume))
    return [p for p in pairs if dataset.postings[p.posting].requirements][:max_pairs]


def planned_calls(n_pairs: int, names: dict[str, list[str]], names_per_group: int, repeats: int) -> int:
    return n_pairs * (repeats + sum(min(names_per_group, len(v)) for v in names.values()))


def _decisions(dataset: Dataset, pair: Pair, output: dict) -> dict[str, bool]:
    mapped = map_to_gold(dataset.postings[pair.posting].requirements, output.get("requirements", []))
    return {d.gold_id: d.predicted for d in mapped}


def _flip_rate(a: dict[str, bool], b: dict[str, bool]) -> float:
    return sum(a[k] != b[k] for k in a) / len(a) if a else 0.0


def audit(dataset: Dataset, cfg: MatcherConfig, names: dict[str, list[str]], pairs: list[Pair], cache: Cache, client,
          names_per_group: int = 3, repeats: int = 2, sleep: float = 0.0, log=print) -> dict:
    group_scores: dict[str, dict[tuple[str, str], list[float]]] = {g: {} for g in names}
    noise, flips, flip_cases, errors = [], [], 0, 0
    examples = []

    def call(text, run, pair):
        out, err, _ = call_with_cache(MatcherConfig(cfg.name, cfg.threshold, cfg.model, run), text,
                                      dataset.postings[pair.posting].text, cache, client, sleep)
        return out, err

    for pair in pairs:
        original = dataset.resumes[pair.resume].text
        base, err = call(original, 1, pair)
        if err or base is None:
            errors += 1
            log(f"  ! {cfg.label} {pair.posting} x {pair.resume}: {err}")
            continue
        base_dec = _decisions(dataset, pair, base)
        if repeats >= 2:
            again, err = call(original, 2, pair)
            if again is not None:
                noise.append(_flip_rate(base_dec, _decisions(dataset, pair, again)))
        for group, group_names in names.items():
            for name in group_names[:names_per_group]:
                out, err = call(replace_name(original, name), 1, pair)
                if out is None:
                    errors += 1
                    continue
                rate = _flip_rate(base_dec, _decisions(dataset, pair, out))
                flips.append(rate)
                if rate > 0:
                    flip_cases += 1
                    if len(examples) < 10:
                        changed = [k for k, v in _decisions(dataset, pair, out).items() if v != base_dec[k]]
                        examples.append({"posting": pair.posting, "resume": pair.resume, "name": name, "group": group, "changed_requirements": changed})
                group_scores[group].setdefault((pair.posting, pair.resume), []).append(out["score"])

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    group_means = {g: mean([s for v in d.values() for s in v]) for g, d in group_scores.items()}
    gaps = []
    groups = list(names)
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            diffs = [mean(group_scores[a][k]) - mean(group_scores[b][k]) for k in group_scores[a] if k in group_scores[b]]
            if diffs:
                gaps.append({"a": a, "b": b, "mean_gap": mean(diffs), "max_abs_gap": max(abs(d) for d in diffs), "n_pairs": len(diffs)})
    noise_rate, name_rate = mean(noise), mean(flips)
    return {
        "matcher": cfg.label, "n_pairs": len(pairs), "names_per_group": names_per_group, "repeats": repeats, "errors": errors,
        "noise_flip_rate": noise_rate, "name_flip_rate": name_rate,
        "excess_flip_rate": None if name_rate is None else max(0.0, name_rate - (noise_rate or 0.0)),
        "variants_with_any_flip": flip_cases, "n_variants": len(flips),
        "group_mean_scores": group_means, "group_gaps": gaps, "examples": examples,
    }


def to_markdown(results: list[dict], names: dict[str, list[str]], title: str = "Name-swap bias audit", meta: dict | None = None) -> str:
    pct = lambda v: "n/a" if v is None else f"{v * 100:.1f}%"
    lines = [f"# {title}", ""]
    if meta:
        lines += ["| | |", "|---|---|",
                  f"| Dataset | `{meta['dataset']}` (labels fingerprint `{meta['labels_hash']}`) |",
                  f"| Pairs audited | {meta['n_pairs']} (split: {meta['split']}, first {meta['max_pairs']} in alphabetical order) |",
                  f"| Names | {meta['names_per_group']} per group, {len(names)} groups; list: `{meta['names_file']}` |",
                  f"| Noise baseline | each resume run {meta['repeats']} times with the same name |",
                  f"| TF-IDF threshold | {meta['tfidf_threshold']} |",
                  f"| Generated | {meta['generated']} |", ""]
    lines += [
             "Only the name on the first line of each resume was changed. *Noise* is the flip rate when the same resume is run twice with the same name.", "",
             "| Matcher | Pairs | Name variants | Decisions flipped by a name change | Flipped with no change (noise) | Beyond noise | Variants with any flip |", "|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['matcher']} | {r['n_pairs']} | {r['n_variants']} | {pct(r['name_flip_rate'])} | {pct(r['noise_flip_rate'])} | {pct(r['excess_flip_rate'])} | {r['variants_with_any_flip']} |")
    lines += ["", "## Mean score by name group", "", "| Matcher | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for r in results:
        lines.append(f"| {r['matcher']} | " + " | ".join(pct(r["group_mean_scores"].get(g)) for g in names) + " |")
    lines += ["", "## Largest paired score gaps between groups", "", "Gap = score with group A's names minus group B's, for the same resume and posting, averaged over pairs.", "",
              "| Matcher | A | B | Mean gap | Largest single gap | Pairs |", "|---|---|---|---|---|---|"]
    for r in results:
        for g in sorted(r["group_gaps"], key=lambda g: -abs(g["mean_gap"]))[:6]:
            lines.append(f"| {r['matcher']} | {g['a']} | {g['b']} | {g['mean_gap'] * 100:+.1f} points | {g['max_abs_gap'] * 100:.1f} points | {g['n_pairs']} |")
    flipped = [(r["matcher"], e) for r in results for e in r["examples"]]
    if flipped:
        lines += ["", "## Examples of changed decisions", ""] + [f"- {m}: {e['posting']} x {e['resume']} with name \"{e['name']}\" ({e['group']}) changed: {', '.join(e['changed_requirements'])}" for m, e in flipped[:15]]
    lines += ["", "## How to read this", "",
              "- Names are the only thing that changed, so any consistent score gap between groups is name-related. A small sample cannot show the absence of bias.",
              "- The name list is illustrative. For a published claim use a validated list from the literature and many more names and resumes.",
              "- Group labels describe how a name is commonly perceived in audit studies; they are not facts about any person.",
              "- Flips within the noise rate are not evidence of anything. Only the excess is."]
    return "\n".join(lines) + "\n"
