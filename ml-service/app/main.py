from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request

from .extract import extract_skills
from .llm_extract import LLMNotConfigured, LLMUnavailable, get_llm_client, llm_extract
from .matchers import keyword
from .matchers import llm as llm_matcher
from .matchers import tfidf
from .parse_pdf import ParsePdfError, pdf_to_text
from .security import require_key
from .schemas import MAX_EXTRACT_CHARS, ExtractRequest, ExtractResponse, MatchRequest, MatchResponse, ParsePdfResponse

app = FastAPI(title="Job Tracker ML Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ml-service"}


@app.post("/extract", response_model=ExtractResponse, dependencies=[Depends(require_key)])
def extract(req: ExtractRequest, client: Any = Depends(get_llm_client)) -> ExtractResponse:
    """method=keyword (default, free, deterministic baseline) or method=llm (grounded LLM extraction)."""
    if req.method == "keyword":
        return ExtractResponse(skills=extract_skills(req.text))
    try:
        return llm_extract(req.text, req.kind, client)
    except LLMNotConfigured as err:
        raise HTTPException(status_code=503, detail=str(err))
    except LLMUnavailable as err:
        raise HTTPException(status_code=502, detail=str(err))


@app.post("/match", response_model=MatchResponse, response_model_exclude_none=True, dependencies=[Depends(require_key)])
def match(req: MatchRequest, client: Any = Depends(get_llm_client)) -> MatchResponse:
    """matcher=keyword (default), tfidf (free term overlap) or llm (grounded LLM judgement)."""
    if req.matcher == "keyword":
        return keyword.match(req.resume_text, req.job_description)
    if len(req.resume_text) > MAX_EXTRACT_CHARS or len(req.job_description) > MAX_EXTRACT_CHARS:
        raise HTTPException(
            status_code=422, detail=f"Text too long for this matcher (limit {MAX_EXTRACT_CHARS:,} characters each)"
        )
    if req.matcher == "tfidf":
        return tfidf.match(req.resume_text, req.job_description)
    try:
        return llm_matcher.match(req.resume_text, req.job_description, client)
    except LLMNotConfigured as err:
        raise HTTPException(status_code=503, detail=str(err))
    except LLMUnavailable as err:
        raise HTTPException(status_code=502, detail=str(err))


@app.post("/parse/pdf", response_model=ParsePdfResponse, dependencies=[Depends(require_key)])
async def parse_pdf(request: Request) -> ParsePdfResponse:
    """Raw PDF bytes in the request body (Content-Type: application/pdf)."""
    data = await request.body()
    try:
        text, pages = pdf_to_text(data)
    except ParsePdfError as err:
        raise HTTPException(status_code=err.status, detail=err.message)
    return ParsePdfResponse(text=text, pages=pages)
