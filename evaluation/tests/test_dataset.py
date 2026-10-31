import json
import shutil

import pytest

from evalkit.schema import DatasetError, assign_split, load_dataset, validate

from conftest import EXAMPLE


def test_example_dataset_is_valid_and_has_both_splits(example):
    errors, warnings = validate(example)
    assert errors == [] and warnings == []
    assert {p.split for p in example.postings.values()} == {"dev", "test"}
    assert len(example.pairs) == 12 and len(example.pairs_in("all")) == 12
    assert len(example.pairs_in("dev")) == 4 and len(example.pairs_in("test")) == 8


def test_evidence_lines_in_the_example_really_support_the_requirement(example):
    # the example labels were written by hand; make sure each cited line mentions one of the requirement's aliases or
    # an obviously equivalent phrase (guards against off-by-one line numbers)
    from app.matchers.common import numbered_lines

    equivalents = {"rest-api": ["json endpoints"], "rest-apis": ["json endpoints"], "browser-automation": ["browser"], "cicd": ["pipelines", "github actions"],
                   "test-cases": ["test", "browser tests"], "docker": ["docker", "container"]}
    for pair in example.pairs:
        lines = numbered_lines(example.resumes[pair.resume].text)
        reqs = {r.id: r for r in example.postings[pair.posting].requirements}
        for rid, nums in pair.evidence.items():
            words = reqs[rid].aliases + equivalents.get(rid, [])
            assert any(w in lines[nums[0]].lower() for w in words), (pair.posting, pair.resume, rid, lines[nums[0]])


def broken(tmp_path, mutate):
    root = tmp_path / "d"
    shutil.copytree(EXAMPLE, root)
    raw = json.loads((root / "labels.json").read_text())
    mutate(raw)
    (root / "labels.json").write_text(json.dumps(raw))
    return validate(load_dataset(root))


def test_validation_catches_label_mistakes(tmp_path):
    def mutate(raw):
        raw["pairs"][0]["supported"].append("not-a-requirement")
        raw["pairs"][1]["evidence"] = {"python": [3]} if "python" not in raw["pairs"][1]["supported"] else {"python": [99]}
        raw["pairs"].append(dict(raw["pairs"][2]))                      # duplicate pair
        raw["postings"]["qa-automation"]["split"] = "validation"
    errors, _ = broken(tmp_path, mutate)
    text = " | ".join(errors)
    assert "does not exist in the posting" in text and "labeled twice" in text and "split must be one of" in text
    assert "is not a non-blank resume line" in text or "not marked supported" in text


def test_warns_about_long_first_line_and_thin_postings(tmp_path):
    root = tmp_path / "d"
    shutil.copytree(EXAMPLE, root)
    (root / "resumes" / "weak-frontend.txt").write_text("Sam Rivera, a frontend developer from somewhere far away\nBuilt things\n")
    raw = json.loads((root / "labels.json").read_text())
    raw["pairs"] = [p for p in raw["pairs"] if p["posting"] != "backend-api"][:6] + [p for p in raw["pairs"] if p["posting"] == "backend-api"][:1]
    (root / "labels.json").write_text(json.dumps(raw))
    _, warnings = validate(load_dataset(root))
    assert any("first line should be just a made-up name" in w for w in warnings)
    assert any("only 1 labeled resume" in w for w in warnings)


def test_loading_problems_are_reported_clearly(tmp_path):
    with pytest.raises(DatasetError, match="label.py init"):
        load_dataset(tmp_path)
    (tmp_path / "labels.json").write_text("{not json")
    with pytest.raises(DatasetError, match="not valid JSON"):
        load_dataset(tmp_path)
    (tmp_path / "labels.json").write_text(json.dumps({"postings": {"x": {"requirements": []}}}))
    with pytest.raises(DatasetError, match="Missing job description"):
        load_dataset(tmp_path)


def test_split_assignment_is_stable_and_roughly_one_third_dev():
    ids = [f"posting-{i}" for i in range(300)]
    assert [assign_split(i) for i in ids] == [assign_split(i) for i in ids]
    share = sum(assign_split(i) == "dev" for i in ids) / len(ids)
    assert 0.25 < share < 0.42
