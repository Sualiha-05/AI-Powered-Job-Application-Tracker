import argparse
from pathlib import Path

from . import _paths  # noqa: F401
from .bias import audit, load_names, planned_calls, select_pairs, to_markdown
from .cli import RESULTS, confirm_llm, llm_setup, stamp, write_outputs
from .runner import Cache, MatcherConfig
from .schema import DatasetError, load_dataset, validate

NAMES = Path(__file__).resolve().parents[1] / "data" / "names.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Name-swap bias audit: change only the name on a resume and see whether decisions change.")
    ap.add_argument("--data", required=True)
    ap.add_argument("--names", default=str(NAMES))
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all")
    ap.add_argument("--max-pairs", type=int, default=8)
    ap.add_argument("--names-per-group", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=2, help="noise baseline: same resume, same name, run this many times")
    ap.add_argument("--tfidf-threshold", type=float, default=0.6)
    ap.add_argument("--llm", action="store_true", help="also audit the AI matcher (uses quota; asks for confirmation)")
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--name")
    args = ap.parse_args(argv)

    try:
        dataset = load_dataset(args.data)
        names = load_names(args.names)
    except (DatasetError, OSError, KeyError) as err:
        print(f"Error: {err}")
        return 1
    errors, _ = validate(dataset)
    if errors:
        print("The dataset has errors:\n  - " + "\n  - ".join(errors))
        return 1
    pairs = select_pairs(dataset, args.split, args.max_pairs)
    if not pairs:
        print("No labeled pairs to audit.")
        return 1

    out_dir = Path(args.out)
    cache = Cache(out_dir / "cache")
    cfgs = [MatcherConfig("keyword"), MatcherConfig("tfidf", threshold=args.tfidf_threshold)]
    client = None
    if args.llm:
        client, prov, model = llm_setup()
        cfgs.append(MatcherConfig("llm", model=model))
        confirm_llm(planned_calls(len(pairs), names, args.names_per_group, args.repeats), prov, model, args.yes)

    results = [audit(dataset, cfg, names, pairs, cache, client, args.names_per_group, args.repeats, args.sleep if cfg.is_llm else 0.0) for cfg in cfgs]
    markdown = to_markdown(results, names)
    js, md = write_outputs(out_dir, args.name or f"bias-{Path(args.data).name}-{stamp()}", {"audits": results, "names": names}, markdown)
    print("\n" + markdown)
    print(f"Saved: {md}\n       {js}")
    return 0
