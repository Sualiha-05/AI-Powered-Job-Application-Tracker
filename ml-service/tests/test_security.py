from fastapi.testclient import TestClient

from app.main import app

from .pdf_helper import make_pdf

client = TestClient(app)
EXTRACT = {"text": "Python and Docker"}
MATCH = {"resume_text": "Python", "job_description": "Python"}


def test_open_when_no_key_is_configured(monkeypatch):
    monkeypatch.delenv("ML_API_KEY", raising=False)
    assert client.post("/extract", json=EXTRACT).status_code == 200


def test_protected_routes_require_the_key(monkeypatch):
    monkeypatch.setenv("ML_API_KEY", "s3cret")
    pdf = make_pdf(["Python developer"])
    calls = [
        lambda h: client.post("/extract", json=EXTRACT, headers=h),
        lambda h: client.post("/match", json=MATCH, headers=h),
        lambda h: client.post("/parse/pdf", content=pdf, headers={"Content-Type": "application/pdf", **h}),
    ]
    for call in calls:
        assert call({}).status_code == 401
        assert call({"X-API-Key": "wrong"}).status_code == 401
        assert call({"X-API-Key": "s3cret"}).status_code == 200


def test_health_stays_open(monkeypatch):
    monkeypatch.setenv("ML_API_KEY", "s3cret")
    assert client.get("/health").status_code == 200
