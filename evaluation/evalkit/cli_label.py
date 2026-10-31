"""Interactive labeling. Never runs a matcher: label blind."""
import argparse
from pathlib import Path

from . import _paths  # noqa: F401
from app.matchers.common import numbered_lines
from . import labeling
from .schema import DatasetError, load_dataset, load_raw, validate

GUIDELINE = """Labeling guideline - answer YES only if some line says the candidate HAS used or DOES the requirement:
  yes: a bullet describing the work, or the skill in a skills list; the same capability in different words
  no : only wanted or being learned ("curious about", "currently learning"), coursework or tutorials only,
       a different tool (Docker is not Kubernetes), or nothing about it
Decide from the resume text alone. Do not look at what any matcher says."""


def label_pair_interactive(root: Path, posting_id: str, resume_id: str, ask=input, out=print) -> bool:
    ds = load_dataset(root)
    posting, resume = ds.postings.get(posting_id), ds.resumes.get(resume_id)
    if not posting or not resume:
        out(f"Unknown posting or resume. Run: label.py --data {root} sync")
        return False
    if not posting.requirements:
        out(f"{posting_id} has no requirements yet. Run: label.py --data {root} requirements {posting_id}")
        return False
    lines = numbered_lines(resume.text)
    out(f"\n=== {posting_id}  x  {resume_id}   tags: {', '.join(resume.tags) or '(none)'}\n{GUIDELINE}\n\nResume:")
    out("\n".join(f"  {n:>3}  {t}" for n, t in lines.items()))
    supported, evidence = [], {}
    try:
        for i, req in enumerate(posting.requirements, 1):
            while True:
                answer = ask(f"\n[{i}/{len(posting.requirements)}] {req.label} ({req.importance})  supported? [y/n/q=stop without saving]: ").strip().lower()
                if answer in ("y", "n", "q"):
                    break
                out("  please type y, n or q")
            if answer == "q":
                out("Stopped; nothing saved for this pair.")
                return False
            if answer == "y":
                supported.append(req.id)
                while True:
                    try:
                        evidence[req.id] = labeling.parse_line_numbers(ask("  evidence line numbers (Enter to skip): "), set(lines))
                        break
                    except ValueError as err:
                        out(f"  {err}")
    except EOFError:
        out("\nInput ended; nothing saved for this pair.")
        return False
    labeling.save_pair(root, posting_id, resume_id, supported, evidence)
    out(f"Saved: {len(supported)} of {len(posting.requirements)} requirements supported.")
    return True


def cmd_requirements(root: Path, posting_id: str, replace: bool, ask=input, out=print) -> int:
    file = root / "postings" / f"{posting_id}.txt"
    if not file.exists():
        out(f"{file} not found.")
        return 1
    out(file.read_text(encoding="utf-8"))
    out("\nType the REQUIREMENTS of this posting, one per line, then an empty line to finish.\n"
        "Format:  Label | alias one, alias two | required or preferred   (aliases and importance are optional)\n"
        "Aliases are words a matcher's wording would contain (matched at the start of a word), for example:  REST API design | rest, api")
    lines = []
    try:
        while (line := ask("> ").strip()):
            lines.append(line)
    except EOFError:
        pass
    try:
        new = labeling.add_requirements(root, posting_id, lines, replace)
    except (ValueError, DatasetError) as err:
        out(f"Error: {err}")
        return 1
    out(f"Added {len(new)} requirement(s).")
    return 0


def main(argv=None, ask=input, out=print) -> int:
    ap = argparse.ArgumentParser(description="Build and check a labeled dataset by hand.")
    ap.add_argument("--data", required=True, help="dataset folder, e.g. evaluation/data/mine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create an empty dataset folder")
    sub.add_parser("sync", help="register new files from postings/ and resumes/")
    sub.add_parser("status")
    sub.add_parser("check", help="validate labels.json")
    r = sub.add_parser("requirements", help="enter the gold requirements of a posting")
    r.add_argument("posting")
    r.add_argument("--replace", action="store_true")
    t = sub.add_parser("tags", help="set resume tags, e.g. strong,synonyms")
    t.add_argument("resume")
    t.add_argument("tags")
    p = sub.add_parser("pair", help="label one resume against one posting")
    p.add_argument("posting")
    p.add_argument("resume")
    ps = sub.add_parser("pairs", help="label every resume not yet labeled for a posting")
    ps.add_argument("posting")
    args = ap.parse_args(argv)
    root = Path(args.data)

    try:
        if args.cmd == "init":
            labeling.init_dataset(root)
            out(f"Created {root}. Put job descriptions in {root / 'postings'} and resumes in {root / 'resumes'} (one .txt each; the resume's first line is a made-up name), then run: sync")
        elif args.cmd == "sync":
            added = labeling.sync(root)
            out(f"Registered postings: {added['postings'] or 'none new'}; resumes: {added['resumes'] or 'none new'}")
        elif args.cmd == "status":
            out(labeling.status_text(root))
        elif args.cmd == "check":
            errors, warnings = validate(load_dataset(root))
            for w in warnings:
                out(f"warning: {w}")
            for e in errors:
                out(f"ERROR: {e}")
            out("OK: no errors." if not errors else f"{len(errors)} error(s).")
            return 1 if errors else 0
        elif args.cmd == "requirements":
            return cmd_requirements(root, args.posting, args.replace, ask, out)
        elif args.cmd == "tags":
            labeling.set_tags(root, args.resume, args.tags.split(","))
            out("Saved.")
        elif args.cmd == "pair":
            return 0 if label_pair_interactive(root, args.posting, args.resume, ask, out) else 1
        elif args.cmd == "pairs":
            raw = load_raw(root)
            done = {p["resume"] for p in raw["pairs"] if p["posting"] == args.posting}
            todo = [r for r in raw["resumes"] if r not in done]
            out(f"{len(todo)} resume(s) to label for {args.posting}")
            for resume in todo:
                if not label_pair_interactive(root, args.posting, resume, ask, out):
                    return 1
    except (DatasetError, ValueError) as err:
        out(f"Error: {err}")
        return 1
    return 0
