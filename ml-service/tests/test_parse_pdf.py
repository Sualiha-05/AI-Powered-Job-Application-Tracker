from fastapi.testclient import TestClient

from app.main import app

from .pdf_helper import make_pdf

client = TestClient(app)
PDF = {"Content-Type": "application/pdf"}


def test_parse_pdf_keeps_lines():
    pdf = make_pdf(["Jane Doe", "Built REST APIs with Python and FastAPI", "Deployed with Docker"])
    r = client.post("/parse/pdf", content=pdf, headers=PDF)
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] == 1
    assert body["text"].splitlines() == ["Jane Doe", "Built REST APIs with Python and FastAPI", "Deployed with Docker"]


def test_parse_pdf_handles_parentheses():
    r = client.post("/parse/pdf", content=make_pdf(["Skills (Python, SQL)"]), headers=PDF)
    assert "Skills (Python, SQL)" in r.json()["text"]


def test_not_a_pdf_is_400():
    r = client.post("/parse/pdf", content=b"just some text", headers=PDF)
    assert r.status_code == 400


def test_scanned_pdf_without_text_is_422():
    r = client.post("/parse/pdf", content=make_pdf([], blank=True), headers=PDF)
    assert r.status_code == 422
    assert "extractable text" in r.json()["detail"]


def test_corrupted_pdf_is_422():
    r = client.post("/parse/pdf", content=b"%PDF-1.4\ngarbage that is not a real pdf", headers=PDF)
    assert r.status_code == 422
