import re
from pathlib import Path

import pytest

from evalkit import labeling
from evalkit.cli_label import label_pair_interactive, main
from evalkit.schema import DatasetError, load_dataset, load_raw, validate


def test_requirement_line_parsing():
    r = labeling.parse_requirement_line("REST API design | rest, API | preferred", set())
    assert r == {"id": "rest-api-design", "label": "REST API design", "aliases": ["rest", "api"], "importance": "preferred"}
    plain = labeling.parse_requirement_line("Docker", {"docker"})
    assert plain["aliases"] == ["docker"] and plain["importance"] == "required" and plain["id"] == "docker-2"
    assert labeling.parse_requirement_line("X | x | pref", set())["importance"] == "preferred"
    for bad in ("", "  | x", "Docker | docker | maybe"):
        with pytest.raises(ValueError):
            labeling.parse_requirement_line(bad, set())


def test_line_number_parsing():
    assert labeling.parse_line_numbers("4, 7 9", {4, 7, 9}) == [4, 7, 9]
    assert labeling.parse_line_numbers("", {1}) == []
    for bad in ("x", "4, 99"):
        with pytest.raises(ValueError):
            labeling.parse_line_numbers(bad, {4})


def scaffold(tmp_path):
    root = tmp_path / "mine"
    labeling.init_dataset(root)
    (root / "postings" / "job-a.txt").write_text("Role\nRequirements:\n- Python\n- Docker\n")
    (root / "resumes" / "r1.txt").write_text("Alex Test\nBuilt APIs in Python\nShipped with Docker\n")
    (root / "resumes" / "r2.txt").write_text("Blair Test\nWrote documentation\n")
    return root


def test_full_labeling_flow_produces_a_valid_dataset(tmp_path):
    root = scaffold(tmp_path)
    with pytest.raises(DatasetError, match="already exists"):
        labeling.init_dataset(root)
    assert labeling.sync(root) == {"postings": ["job-a"], "resumes": ["r1", "r2"]}
    assert labeling.sync(root) == {"postings": [], "resumes": []}                  # idempotent
    labeling.add_requirements(root, "job-a", ["Python | python", "Docker | docker, container | preferred"])
    labeling.set_tags(root, "r1", ["Strong", " strong ", "backend"])
    answers = iter(["y", "2", "y", "3"])
    assert label_pair_interactive(root, "job-a", "r1", ask=lambda _: next(answers), out=lambda *_: None)
    answers = iter(["n", "n"])
    assert label_pair_interactive(root, "job-a", "r2", ask=lambda _: next(answers), out=lambda *_: None)
    ds = load_dataset(root)
    errors, warnings = validate(ds)
    assert errors == [] and warnings == ["posting job-a: only 2 labeled resume(s); per-posting ranking needs at least 3"]   # honest warning
    p1 = next(p for p in ds.pairs if p.resume == "r1")
    assert p1.supported == {"python", "docker"} and p1.evidence == {"python": [2], "docker": [3]}
    assert ds.resumes["r1"].tags == ["backend", "strong"] and ds.postings["job-a"].split in ("dev", "test")


def test_relabeling_replaces_instead_of_duplicating(tmp_path):
    root = scaffold(tmp_path)
    labeling.sync(root)
    labeling.add_requirements(root, "job-a", ["Python"])
    for answers in (["y", ""], ["n"]):
        it = iter(answers)
        label_pair_interactive(root, "job-a", "r1", ask=lambda _: next(it), out=lambda *_: None)
    pairs = [p for p in load_raw(root)["pairs"] if p["resume"] == "r1"]
    assert len(pairs) == 1 and pairs[0]["supported"] == []


def test_invalid_answers_reprompt_and_quit_saves_nothing(tmp_path):
    root = scaffold(tmp_path)
    labeling.sync(root)
    labeling.add_requirements(root, "job-a", ["Python"])
    said = []
    answers = iter(["maybe", "y", "oops", "99", "q"])      # bad answer, yes, bad evidence, evidence not on a line -> then EOF handling below
    def ask(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError
    assert not label_pair_interactive(root, "job-a", "r1", ask=ask, out=said.append)
    assert load_raw(root)["pairs"] == [] and any("please type y, n or q" in str(s) for s in said)


def test_cannot_label_before_requirements_exist(tmp_path):
    root = scaffold(tmp_path)
    labeling.sync(root)
    msgs = []
    assert not label_pair_interactive(root, "job-a", "r1", ask=lambda _: "y", out=msgs.append)
    assert any("no requirements yet" in m for m in msgs)


def test_status_lists_what_is_left(tmp_path):
    root = scaffold(tmp_path)
    labeling.sync(root)
    assert "label.py requirements job-a" in labeling.status_text(root)
    labeling.add_requirements(root, "job-a", ["Python"])
    assert "still to label: r1, r2" in labeling.status_text(root)


def test_requirements_command_reads_lines_until_blank(tmp_path):
    root = scaffold(tmp_path)
    labeling.sync(root)
    lines = iter(["Python | python", "Docker", ""])
    out = []
    assert main(["--data", str(root), "requirements", "job-a"], ask=lambda _: next(lines), out=out.append) == 0
    assert [r["label"] for r in load_raw(root)["postings"]["job-a"]["requirements"]] == ["Python", "Docker"]


def test_labeling_code_never_runs_a_matcher():
    """Labels must be written blind. Guard against someone adding matcher output to the labeling tools."""
    for name in ("labeling.py", "cli_label.py"):
        src = (Path(__file__).resolve().parents[1] / "evalkit" / name).read_text()
        imports = "\n".join(re.findall(r"^\s*(?:from|import)\s.*$", src, re.M))
        assert not re.search(r"runner|tfidf|keyword|llm_matcher|matchers\.(?!common)", imports), (name, imports)
