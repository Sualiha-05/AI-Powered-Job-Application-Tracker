import argparse
from pathlib import Path

from . import _paths  # noqa: F401
from .cli import RESULTS, confirm_llm, llm_setup, stamp, write_outputs
from .report import to_markdown
from .runner import Cache, MatcherConfig, count_uncached_llm_calls, evaluate
from .schema import DatasetError, load_dataset, validate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score the matchers against your labels.")
    ap.add_argument("--data", required=True, help="dataset folder, e.g. evaluation/data/mine (or evaluation/data/example to try the tools)")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="test", help="tune on dev, report test (default)")
    ap.add_argument("--tfidf-thresholds", default="0.6", help="comma separated; several values = a sweep, e.g. 0.4,0.5,0.6,0.7")
    ap.add_argument("--no-keyword", action="store_true")
    ap.add_argument("--llm", action="store_true", help="also run the AI matcher (uses quota; asks for confirmation)")
    ap.add_argument("--llm-runs", type=int, default=3, help="repeats of the AI matcher, to measure how much it varies")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between AI calls (free-tier rate limits)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation before AI calls")
    ap.add_argument("--out", default=str(RESULTS), help="where reports are written")
    ap.add_argument("--name", help="report file name prefix")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    try:
        dataset = load_dataset(args.data)
    except DatasetError as err:
        print(f"Error: {err}")
        return 1
    errors, warnings = validate(dataset)
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        print("The dataset has errors; fix these first (python evaluation/label.py --data ... check):")
        for e in errors:
            print(f"  - {e}")
        return 1
    if not dataset.pairs_in(args.split):
        print(f"No labeled pairs in the {args.split!r} split.")
        return 1
    try:
        thresholds = tuple(float(t) for t in args.tfidf_thresholds.split(",") if t.strip())
    except ValueError:
        print("--tfidf-thresholds must be numbers like 0.4,0.6")
        return 1

    out_dir = Path(args.out)
    cache = Cache(None if args.no_cache else out_dir / "cache")
    client = model = None
    if args.llm:
        client, prov, model = llm_setup()
        cfgs = [MatcherConfig("llm", model=model, run=i) for i in range(1, args.llm_runs + 1)]
        confirm_llm(count_uncached_llm_calls(dataset, dataset.pairs_in(args.split), cfgs, cache), prov, model, args.yes)

    if args.split == "test":
        print("Reporting on the TEST split: choose thresholds on dev first, and do not change labels after looking at these results.")
    result = evaluate(dataset, args.split, use_keyword=not args.no_keyword, tfidf_thresholds=thresholds,
                      llm_runs=args.llm_runs if args.llm else 0, llm_model=model, cache=cache, client=client, sleep=args.sleep)
    markdown = to_markdown(result)
    name = args.name or f"{Path(args.data).name}-{args.split}-{stamp()}"
    js, md = write_outputs(out_dir, name, result, markdown)
    print("\n" + markdown)
    print(f"Saved: {md}\n       {js}")
    return 0
