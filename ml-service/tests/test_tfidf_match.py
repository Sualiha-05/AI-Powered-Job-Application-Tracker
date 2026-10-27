import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.matchers import tfidf
from app.matchers.common import numbered_lines
from app.matchers.tfidf import document_similarity, requirement_units, tokens

RESUME = """Jane Doe

Built REST services in Python with FastAPI and PostgreSQL
Wrote end-to-end browser tests with Selenium and pytest
Deployed with Docker and GitHub Actions
Curious about learning Kubernetes
Led a team of 3 interns on a dashboard in React"""
#  L1 name | L2 blank | L3 REST/Python/FastAPI/PostgreSQL | L4 Selenium | L5 Docker | L6 Kubernetes (only curious) | L7 React

HEADED_JD = """Backend Engineer
About us: We are a fast-growing fintech company building payments.
Requirements:
- 3+ years of Python and FastAPI experience
- Experience with Selenium
- Docker
Nice to have: Kubernetes, Terraform
Benefits: Free lunch and a gym"""


def by_name(out):
    return {r.requirement: r for r in out.requirements}


# ---------------- tokens ----------------
def test_tokens_stem_alias_and_drop_noise():
    assert tokens("Built REST APIs") == ["build", "rest", "api"]
    assert tokens("ReactJS, Postgres and JS") == ["react", "postgresql", "javascript"]
    assert tokens("3+ years of experience with the Node.js, C++ and CI/CD") == ["node.js", "c++", "ci/cd"]


def test_tokens_are_consistent_across_word_forms():
    assert set(tokens("tested")) == set(tokens("testing")) == set(tokens("tests"))
    assert tokens("deployed") == tokens("deploying") == tokens("deploy")


# ---------------- requirement units ----------------
def test_headings_drive_importance_and_skip_sections():
    units = {u.label: u for u in requirement_units(HEADED_JD)}
    assert {"Docker", "Kubernetes", "Terraform"} <= set(units)
    assert units["Docker"].importance == "required"
    assert units["Kubernetes"].importance == "preferred" and units["Terraform"].importance == "preferred"
    labels = " ".join(units)
    assert "fintech" not in labels and "lunch" not in labels and "Backend Engineer" not in labels


def test_single_line_with_inline_headings():
    units = requirement_units("Requirements: backend API development, Python, Docker. Nice to have: Kubernetes.")
    assert [(u.label, u.importance) for u in units] == [
        ("backend API development", "required"), ("Python", "required"), ("Docker", "required"), ("Kubernetes", "preferred"),
    ]


def test_inline_plus_cue_marks_preferred_without_headings():
    units = requirement_units("We need React and Node.js. Familiarity with Selenium is a plus.")
    assert {u.label: u.importance for u in units}["Familiarity with Selenium is a plus"] == "preferred"


def test_prose_without_requirements_gives_no_units():
    assert requirement_units("We are a friendly team that loves coffee and shipping features quickly together every week.") == []


def test_short_lists_count_but_chatty_sentences_do_not():
    assert [u.label for u in requirement_units("Python, Docker, Kubernetes")] == ["Python", "Docker", "Kubernetes"]
    assert requirement_units("We love coffee and shipping features quickly together every week.") == []


def test_lead_ins_are_stripped_from_terms_but_not_from_labels():
    unit = requirement_units("We need someone with React and Node.js experience.")[0]
    assert unit.label.startswith("We need someone with React") and unit.terms == frozenset({"react"})


def test_duplicates_collapse_and_units_are_capped():
    assert len(requirement_units("Requirements:\n- Python\n- python\n- Python")) == 1
    many = "Requirements:\n" + "\n".join(f"- Skill{chr(97 + i % 26)}{chr(97 + i // 26)}x" for i in range(60))
    assert len(requirement_units(many)) == 25


# ---------------- matching ----------------
def test_matches_skills_outside_the_keyword_vocabulary():
    out = tfidf.match(RESUME, HEADED_JD)
    reqs = by_name(out)
    assert reqs["Experience with Selenium"].supported            # Selenium is not in the keyword matcher's list
    assert reqs["Experience with Selenium"].evidence[0].line_number == 4
    assert reqs["Experience with Selenium"].evidence[0].line == "Wrote end-to-end browser tests with Selenium and pytest"
    assert out.matcher == "tfidf-overlap" and 0 < out.score < 1 and 0 <= out.doc_similarity <= 1


def test_interest_in_a_skill_is_not_evidence():
    out = tfidf.match(RESUME, HEADED_JD)
    kube = by_name(out)["Kubernetes"]
    assert not kube.supported and kube.evidence == [] and "Kubernetes" in out.missing


def test_unsupported_requirements_are_listed_and_explained():
    terraform = by_name(tfidf.match(RESUME, HEADED_JD))["Terraform"]
    assert not terraform.supported and terraform.note == "no shared terms"


def test_synonyms_are_a_known_limitation():
    # "API design" shares no terms with "Built REST services": TF-IDF cannot know they are related.
    out = tfidf.match(RESUME, "Requirements: API design")
    assert out.requirements[0].supported is False
    assert out.score == 0.0


def test_partial_overlap_below_threshold_is_not_supported(monkeypatch):
    jd = "Requirements:\n- Python microservices architecture"
    monkeypatch.setenv("TFIDF_THRESHOLD", "0.95")
    assert tfidf.match(RESUME, jd).score == 0.0
    monkeypatch.setenv("TFIDF_THRESHOLD", "0.05")
    assert tfidf.match(RESUME, jd).score == 1.0           # the threshold really controls the decision


def test_invalid_threshold_falls_back_to_default(monkeypatch):
    baseline = tfidf.match(RESUME, HEADED_JD).score
    monkeypatch.setenv("TFIDF_THRESHOLD", "not-a-number")
    assert tfidf.match(RESUME, HEADED_JD).score == baseline > 0


def test_line_numbers_use_the_same_numbering_as_the_other_matchers():
    evidence = tfidf.match(RESUME, "Requirements: Docker").requirements[0].evidence[0]
    assert evidence.line_number == 5 and numbered_lines(RESUME)[5] == evidence.line


def test_deterministic_and_empty_cases():
    assert tfidf.match(RESUME, HEADED_JD) == tfidf.match(RESUME, HEADED_JD)
    empty = tfidf.match(RESUME, "We love coffee and shipping features quickly together every week.")
    assert empty.score == 0.0 and empty.requirements == [] and empty.missing == []
    assert tfidf.match("   ", HEADED_JD).score == 0.0      # nothing in the resume


def test_document_similarity_bounds():
    assert document_similarity("Python Docker", "Python Docker") == pytest.approx(1.0, abs=0.001)
    assert document_similarity("Python Docker", "Figma Sketch") == 0.0
    assert document_similarity("", "Python") == 0.0


# ---------------- endpoint ----------------
client = TestClient(app)


def post(**extra):
    return client.post("/match", json={"resume_text": RESUME, "job_description": HEADED_JD, "matcher": "tfidf", **extra})


def test_endpoint_works_without_any_llm_key():
    r = post()
    assert r.status_code == 200
    body = r.json()
    assert body["matcher"] == "tfidf-overlap" and "doc_similarity" in body and "usage" not in body
    assert body["requirements"][0]["importance"] in ("required", "preferred")


def test_endpoint_rejects_oversized_text_for_tfidf_but_not_keyword():
    huge = "Python " * 6000
    assert post(resume_text=huge).status_code == 422
    assert client.post("/match", json={"resume_text": huge, "job_description": HEADED_JD}).status_code == 200


def test_endpoint_requires_the_shared_key_when_configured(monkeypatch):
    monkeypatch.setenv("ML_API_KEY", "k")
    assert post().status_code == 401
    assert client.post("/match", headers={"X-API-Key": "k"}, json={"resume_text": RESUME, "job_description": HEADED_JD, "matcher": "tfidf"}).status_code == 200
