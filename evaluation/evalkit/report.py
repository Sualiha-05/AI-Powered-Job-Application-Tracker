import datetime


def _pct(v, digits=0):
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


def _num(v, digits=2):
    return "n/a" if v is None else f"{v:.{digits}f}"


def _pm(ms, pct=False):
    if ms is None:
        return "n/a"
    m, s = ms
    return f"{m * 100:.0f}% ± {s * 100:.0f}" if pct else f"{m:.2f} ± {s:.2f}"


def _tag_cell(t: dict) -> str:
    if t["f1"] is not None:
        return f"{t['f1']:.2f} (n={t['n']})"
    return f"F1 undefined, accuracy {_num(t['accuracy'])} (n={t['n']})"  # no positives to find or none predicted


def _sweep_note(det: list[dict]) -> list[str]:
    tf = [r for r in det if r["matcher"] == "tfidf"]
    same = len(tf) > 1 and len({(r["tp"], r["fp"], r["fn"], r["tn"]) for r in tf}) == 1
    return ["> **The TF-IDF threshold sweep did not separate the thresholds:** every value gave identical decisions on this split, so this data cannot justify choosing one. "
            "Say that the threshold is a default, not a tuned value.", ""] if same else []


def to_markdown(result: dict, title: str = "Matcher evaluation") -> str:
    lines = [f"# {title}", "", f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}.", ""]
    lines += [
        "| | |", "|---|---|",
        f"| Dataset | `{result['dataset']}` (labels fingerprint `{result['labels_hash']}`) |",
        f"| Split | **{result['split']}** |",
        f"| Size | {result['n_pairs']} resume/posting pairs, {result['n_postings']} postings, {result['n_resumes']} resumes, {result['n_gold_requirements']} gold requirement decisions |",
        f"| TF-IDF thresholds | {', '.join(str(t) for t in result['tfidf_thresholds'])} |",
    ]
    if result.get("llm_runs"):
        lines.append(f"| AI matcher | {result['llm_model']}, {result['llm_runs']} repeat(s) |")
    lines.append("")

    det = [r for r in result["runs"] if r["matcher"] != "llm"]
    llm_agg = result.get("llm_aggregate")
    lines += ["## Requirement-level agreement with your labels", "",
              "Positive class = \"the resume supports this requirement\". *Coverage* is how many gold requirements the matcher produced a "
              "matching requirement for at all; uncovered ones count as \"not supported\".", "",
              "| Matcher | Coverage | Precision | Recall | F1 | F1 95% interval | Accuracy | TP | FP | FN | TN |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in det:
        ci = "n/a" if not r["f1_ci"] else f"{r['f1_ci'][0]:.2f} to {r['f1_ci'][1]:.2f}"
        lines.append(f"| {r['label']} | {_pct(r['coverage'])} | {_num(r['precision'])} | {_num(r['recall'])} | {_num(r['f1'])} | {ci} | {_num(r['accuracy'])} | {r['tp']} | {r['fp']} | {r['fn']} | {r['tn']} |")
    if llm_agg:
        lines.append(f"| {llm_agg['label']} (mean ± sd of {llm_agg['runs']} runs) | {_pm(llm_agg['coverage'], True)}% | {_pm(llm_agg['precision'])} | {_pm(llm_agg['recall'])} | {_pm(llm_agg['f1'])} | n/a | {_pm(llm_agg['accuracy'])} | | | | |")
    lines.append("")
    lines += _sweep_note(det)
    if llm_agg:
        lines += ["> For the AI matcher, **± is the spread between repeats of the same data** (the model's own randomness). It is not a confidence interval: "
                  "it says nothing about how far the result would move on other postings or resumes.", ""]

    lines += ["## Ranking: does a higher score mean a better-supported resume?", "",
              "Spearman correlation between the matcher's score and the share of requirements you labeled as supported (1 = same order, 0 = unrelated).", "",
              "| Matcher | All pairs | Within each posting (mean) | Postings with enough resumes |", "|---|---|---|---|"]
    for r in det:
        lines.append(f"| {r['label']} | {_num(r['spearman_overall'])} | {_num(r['spearman_per_posting_mean'])} | {r['n_postings_ranked']} |")
    if llm_agg:
        lines.append(f"| {llm_agg['label']} (mean ± sd) | {_pm(llm_agg['spearman_overall'])} | {_pm(llm_agg['spearman_per_posting_mean'])} | |")
    lines.append("")

    tags = sorted({t for r in result["runs"] for t in r["per_tag"]})
    if tags:
        lines += ["## F1 by resume type", "", "Shows where each matcher fails (tags come from your labels.json).", "",
                  "| Resume tag | " + " | ".join(r["label"] + (f" #{r['run']}" if r["matcher"] == "llm" else "") for r in result["runs"]) + " |",
                  "|---|" + "---|" * len(result["runs"])]
        for t in tags:
            cells = [_tag_cell(r["per_tag"][t]) if t in r["per_tag"] else "n/a" for r in result["runs"]]
            lines.append(f"| {t} | " + " | ".join(cells) + " |")
        lines.append("")

    ev = [r for r in result["runs"] if r["evidence_n"]]
    if ev:
        lines += ["## Evidence lines", "", "For requirements both you and the matcher call supported: how often the matcher cited at least one line you marked as evidence.", ""]
        lines += [f"- {r['label']}{' #' + str(r['run']) if r['matcher'] == 'llm' else ''}: {_pct(r['evidence_hit_rate'])} ({r['evidence_n']} cases)" for r in ev] + [""]

    if llm_agg:
        lines += ["## AI matcher stability and cost", "",
                  f"- Repeats completed: {llm_agg['runs']} of {llm_agg['runs_requested']}",
                  f"- Decisions identical in every repeat: {_pct(llm_agg['decision_agreement'])}",
                  f"- Claims removed because the cited line did not exist (average per run): {llm_agg['ungrounded_mean']:.1f}",
                  f"- Tokens used: {llm_agg['tokens_in']:,} in, {llm_agg['tokens_out']:,} out", ""]
    incomplete = [r for r in result["runs"] if r["incomplete"]]
    if incomplete:
        lines += ["## Incomplete runs", "", "These runs stopped early (for example a quota error). Re-run later: finished AI calls are cached.", ""]
        lines += [f"- {r['label']}: {r['n_pairs']} done, {r['n_pairs_failed']} failed" for r in incomplete] + [""]

    first = det[0] if det else (result["runs"][0] if result["runs"] else None)
    if first and first["mismatches"]:
        lines += [f"## Disagreements for {first['label']} (first 15)", "", "| Posting | Resume | Requirement | You | Matcher |", "|---|---|---|---|---|"]
        for m in first["mismatches"][:15]:
            lines.append(f"| {m['posting']} | {m['resume']} | {m['requirement']} | {'supported' if m['gold'] else 'not supported'} | {'supported' if m['predicted'] else 'not supported' if m['covered'] else 'not found'} |")
        lines += ["", "The JSON file contains the full list for every matcher.", ""]

    lines += ["## How to read these numbers", "",
              "- Labels come from one person and the sample is small. Treat the intervals as the honest size of the uncertainty, and do not claim a ranking between matchers whose intervals overlap.",
              "- Report the split you used. Tune on `dev`, then report `test` once, with the threshold you chose.",
              "- Do not change labels after seeing results. The fingerprint above changes if you do."]
    return "\n".join(lines) + "\n"
