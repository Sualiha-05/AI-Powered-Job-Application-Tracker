"""Helpers for building a labeled dataset by hand.

This module deliberately never imports a matcher: labels must be written WITHOUT seeing what any matcher says,
otherwise the evaluation just measures agreement with the labeler's anchoring.
"""
import re
from pathlib import Path

from . import _paths  # noqa: F401
from app.matchers.common import numbered_lines
from .schema import IMPORTANCE, DatasetError, assign_split, load_raw, save_raw


def init_dataset(root: Path) -> None:
    root = Path(root)
    if (root / "labels.json").exists():
        raise DatasetError(f"{root / 'labels.json'} already exists; refusing to overwrite it")
    (root / "postings").mkdir(parents=True, exist_ok=True)
    (root / "resumes").mkdir(parents=True, exist_ok=True)
    save_raw(root, {"version": 1, "postings": {}, "resumes": {}, "pairs": []})


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def unique_id(base: str, taken: set[str]) -> str:
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def parse_importance(text: str) -> str:
    t = text.strip().lower()
    for value in IMPORTANCE:
        if t and value.startswith(t):
            return value
    raise ValueError(f"importance must be 'required' or 'preferred', got {text!r}")


def parse_requirement_line(line: str, taken_ids: set[str]) -> dict:
    """'Label | alias one, alias two | required'. Aliases and importance are optional."""
    parts = [p.strip() for p in line.split("|")]
    label = parts[0]
    if not label:
        raise ValueError("a requirement needs a label")
    aliases = [a.strip().lower() for a in parts[1].split(",") if a.strip()] if len(parts) > 1 and parts[1] else [label.lower()]
    importance = parse_importance(parts[2]) if len(parts) > 2 and parts[2] else "required"
    return {"id": unique_id(slug(label), taken_ids), "label": label, "aliases": aliases, "importance": importance}


def parse_line_numbers(text: str, valid: set[int]) -> list[int]:
    if not text.strip():
        return []
    try:
        nums = [int(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    except ValueError as err:
        raise ValueError("use numbers separated by commas, for example 4, 7") from err
    bad = [n for n in nums if n not in valid]
    if bad:
        raise ValueError(f"not a resume line with text: {bad}")
    return nums


def sync(root: Path) -> dict[str, list[str]]:
    """Registers every file in postings/ and resumes/ that labels.json does not know yet."""
    root = Path(root)
    raw = load_raw(root)
    added = {"postings": [], "resumes": []}
    for f in sorted((root / "postings").glob("*.txt")):
        if f.stem not in raw["postings"]:
            raw["postings"][f.stem] = {"split": assign_split(f.stem), "requirements": []}
            added["postings"].append(f.stem)
    for f in sorted((root / "resumes").glob("*.txt")):
        if f.stem not in raw["resumes"]:
            raw["resumes"][f.stem] = {"tags": []}
            added["resumes"].append(f.stem)
    save_raw(root, raw)
    return added


def add_requirements(root: Path, posting_id: str, lines: list[str], replace: bool = False) -> list[dict]:
    raw = load_raw(root)
    if posting_id not in raw["postings"]:
        raise DatasetError(f"unknown posting {posting_id!r}; put {posting_id}.txt in postings/ and run: label.py sync")
    entry = raw["postings"][posting_id]
    if replace:
        entry["requirements"] = []
    taken = {r["id"] for r in entry["requirements"]}
    new = []
    for line in lines:
        req = parse_requirement_line(line, taken)
        taken.add(req["id"])
        new.append(req)
    entry["requirements"] += new
    save_raw(root, raw)
    return new


def set_tags(root: Path, resume_id: str, tags: list[str]) -> None:
    raw = load_raw(root)
    if resume_id not in raw["resumes"]:
        raise DatasetError(f"unknown resume {resume_id!r}; put {resume_id}.txt in resumes/ and run: label.py sync")
    raw["resumes"][resume_id]["tags"] = sorted({t.strip().lower() for t in tags if t.strip()})
    save_raw(root, raw)


def save_pair(root: Path, posting_id: str, resume_id: str, supported: list[str], evidence: dict[str, list[int]]) -> None:
    raw = load_raw(root)
    entry = {"posting": posting_id, "resume": resume_id, "supported": supported, "evidence": {k: v for k, v in evidence.items() if v and k in supported}}
    raw["pairs"] = [p for p in raw["pairs"] if (p["posting"], p["resume"]) != (posting_id, resume_id)] + [entry]
    raw["pairs"].sort(key=lambda p: (p["posting"], p["resume"]))
    save_raw(root, raw)


def status_text(root: Path) -> str:
    raw = load_raw(root)
    labeled = {(p["posting"], p["resume"]) for p in raw["pairs"]}
    out = [f"Dataset: {root}", f"  postings: {len(raw['postings'])}   resumes: {len(raw['resumes'])}   labeled pairs: {len(labeled)}", ""]
    for pid, p in raw["postings"].items():
        todo = [r for r in raw["resumes"] if (pid, r) not in labeled]
        out.append(f"  {pid}  [{p.get('split')}]  {len(p['requirements'])} requirements, {len(labeled) - len([1 for k in labeled if k[0] != pid])}/{len(raw['resumes'])} resumes labeled"
                   + ("" if p["requirements"] else "  <- add requirements: label.py requirements " + pid)
                   + (f"  | still to label: {', '.join(todo)}" if todo and p["requirements"] else ""))
    untagged = [r for r, v in raw["resumes"].items() if not v.get("tags")]
    if untagged:
        out += ["", f"  resumes without tags (tags give the 'F1 by resume type' table): {', '.join(untagged)}"]
    test = sum(1 for p in raw["postings"].values() if p.get("split") == "test")
    out += ["", f"  split: {len(raw['postings']) - test} dev, {test} test"]
    return "\n".join(out)
