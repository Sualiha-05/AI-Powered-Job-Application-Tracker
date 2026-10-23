from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

RESUME = """Built REST APIs with Python and FastAPI
Deployed services using Docker and GitHub Actions
Trained models with PyTorch
"""
JD = "We need Python, FastAPI, Docker, Kubernetes and PostgreSQL experience."


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_extract_finds_skills():
    r = client.post("/extract", json={"text": JD})
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert {"Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL"} <= set(skills)


def test_match_returns_evidence_and_missing():
    r = client.post("/match", json={"resume_text": RESUME, "job_description": JD})
    body = r.json()
    assert r.status_code == 200
    assert body["matcher"] == "keyword-baseline"
    assert 0 < body["score"] < 1
    assert "Kubernetes" in body["missing"]
    python_req = next(x for x in body["requirements"] if x["requirement"] == "Python")
    assert python_req["supported"] and python_req["evidence"][0]["line_number"] == 1


def test_empty_text_rejected():
    assert client.post("/extract", json={"text": ""}).status_code == 422


def test_short_aliases_do_not_match_inside_dotted_names():
    skills = client.post("/extract", json={"text": "Experience with Node.js and React.js"}).json()["skills"]
    assert "JavaScript" not in skills and {"Node.js", "React"} <= set(skills)


def test_standalone_js_still_matches_javascript():
    assert "JavaScript" in client.post("/extract", json={"text": "Skills: JS, HTML, CSS"}).json()["skills"]
