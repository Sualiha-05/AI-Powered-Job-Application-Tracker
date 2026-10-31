"""Dataset format.

evaluation/data/<name>/
    labels.json
    postings/<posting-id>.txt     job description text
    resumes/<resume-id>.txt       resume text; the FIRST non-blank line must be the candidate's (made-up) name

labels.json
    postings:  id -> { split: "dev"|"test", requirements: [ {id, label, aliases[], importance} ] }
    resumes:   id -> { tags: [..] }
    pairs:     [ { posting, resume, supported: [requirement ids], evidence: { requirement id: [resume line numbers] } } ]
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from . import _paths  # noqa: F401
from app.matchers.common import numbered_lines

SPLITS = ("dev", "test")
IMPORTANCE = ("required", "preferred")


class DatasetError(Exception):
    pass


@dataclass
class GoldRequirement:
    id: str
    label: str
    aliases: list[str]
    importance: str = "required"


@dataclass
class Posting:
    id: str
    text: str
    split: str
    requirements: list[GoldRequirement]


@dataclass
class Resume:
    id: str
    text: str
    tags: list[str]


@dataclass
class Pair:
    posting: str
    resume: str
    supported: set[str]
    evidence: dict[str, list[int]]


@dataclass
class Dataset:
    root: Path
    postings: dict[str, Posting]
    resumes: dict[str, Resume]
    pairs: list[Pair]

    def pairs_in(self, split: str) -> list[Pair]:
        return [p for p in self.pairs if split == "all" or self.postings[p.posting].split == split]


def assign_split(posting_id: str) -> str:
    """Deterministic, so a posting never moves between dev and test: about one third goes to dev."""
    return "dev" if int(hashlib.sha1(posting_id.encode()).hexdigest(), 16) % 3 == 0 else "test"


def load_raw(root: Path) -> dict:
    path = Path(root) / "labels.json"
    if not path.exists():
        raise DatasetError(f"{path} not found. Create a dataset with: python evaluation/label.py init {root}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise DatasetError(f"{path} is not valid JSON: {err}") from err


def save_raw(root: Path, raw: dict) -> None:
    (Path(root) / "labels.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_dataset(root: Path) -> Dataset:
    root = Path(root)
    raw = load_raw(root)
    postings: dict[str, Posting] = {}
    for pid, p in (raw.get("postings") or {}).items():
        file = root / "postings" / f"{pid}.txt"
        if not file.exists():
            raise DatasetError(f"Missing job description file: {file}")
        reqs = [
            GoldRequirement(
                id=r["id"],
                label=r["label"],
                aliases=[a.lower() for a in (r.get("aliases") or [r["label"]])],
                importance=r.get("importance", "required"),
            )
            for r in p.get("requirements", [])
        ]
        postings[pid] = Posting(pid, file.read_text(encoding="utf-8"), p.get("split") or assign_split(pid), reqs)

    resumes: dict[str, Resume] = {}
    for rid, r in (raw.get("resumes") or {}).items():
        file = root / "resumes" / f"{rid}.txt"
        if not file.exists():
            raise DatasetError(f"Missing resume file: {file}")
        resumes[rid] = Resume(rid, file.read_text(encoding="utf-8"), list(r.get("tags", [])))

    pairs = [
        Pair(
            posting=p["posting"],
            resume=p["resume"],
            supported=set(p.get("supported", [])),
            evidence={k: list(v) for k, v in (p.get("evidence") or {}).items()},
        )
        for p in raw.get("pairs", [])
    ]
    return Dataset(root, postings, resumes, pairs)


def validate(ds: Dataset) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors make a dataset unusable; warnings are things to look at."""
    errors: list[str] = []
    warnings: list[str] = []

    for p in ds.postings.values():
        if p.split not in SPLITS:
            errors.append(f"posting {p.id}: split must be one of {SPLITS}, got {p.split!r}")
        if not p.requirements:
            warnings.append(f"posting {p.id}: no gold requirements yet (run: label.py requirements {p.id})")
        ids = [r.id for r in p.requirements]
        if len(ids) != len(set(ids)):
            errors.append(f"posting {p.id}: duplicate requirement ids")
        for r in p.requirements:
            if r.importance not in IMPORTANCE:
                errors.append(f"posting {p.id}, requirement {r.id}: importance must be one of {IMPORTANCE}")
            if not r.aliases or any(not a.strip() for a in r.aliases):
                errors.append(f"posting {p.id}, requirement {r.id}: aliases must be non-empty")

    for r in ds.resumes.values():
        first = next((ln.strip() for ln in r.text.splitlines() if ln.strip()), "")
        if not first:
            errors.append(f"resume {r.id}: file is empty")
        elif len(first.split()) > 5:
            warnings.append(f"resume {r.id}: first line should be just a made-up name (bias audit replaces it): {first[:40]!r}")

    seen: set[tuple[str, str]] = set()
    for pair in ds.pairs:
        key = (pair.posting, pair.resume)
        where = f"pair {pair.posting} x {pair.resume}"
        if key in seen:
            errors.append(f"{where}: labeled twice")
        seen.add(key)
        if pair.posting not in ds.postings or pair.resume not in ds.resumes:
            errors.append(f"{where}: unknown posting or resume id")
            continue
        req_ids = {r.id for r in ds.postings[pair.posting].requirements}
        for rid in pair.supported - req_ids:
            errors.append(f"{where}: supported requirement {rid!r} does not exist in the posting")
        lines = numbered_lines(ds.resumes[pair.resume].text)
        for rid, nums in pair.evidence.items():
            if rid not in pair.supported:
                errors.append(f"{where}: evidence given for {rid!r}, which is not marked supported")
            for n in nums:
                if n not in lines:
                    errors.append(f"{where}: evidence line {n} for {rid!r} is not a non-blank resume line")

    pairs_per_posting = {pid: 0 for pid in ds.postings}
    for pair in ds.pairs:
        if pair.posting in pairs_per_posting:
            pairs_per_posting[pair.posting] += 1
    for pid, n in pairs_per_posting.items():
        if n == 0:
            warnings.append(f"posting {pid}: no labeled pairs")
        elif n < 3:
            warnings.append(f"posting {pid}: only {n} labeled resume(s); per-posting ranking needs at least 3")
    if ds.postings and not any(p.split == "test" for p in ds.postings.values()):
        warnings.append("no posting is in the test split")
    return errors, warnings
