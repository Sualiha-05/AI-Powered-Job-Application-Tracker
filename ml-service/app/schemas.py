from typing import Literal

from pydantic import BaseModel, Field

MAX_EXTRACT_CHARS = 30_000


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_EXTRACT_CHARS, description="Job description or resume text")
    kind: Literal["job_description", "resume"] = "job_description"
    method: Literal["keyword", "llm"] = "keyword"


class SkillDetail(BaseModel):
    name: str
    importance: Literal["required", "preferred", "mentioned"]
    quote: str = Field(description="Verbatim text from the input that supports this skill")


class ExtractResponse(BaseModel):
    skills: list[str]
    extractor: str = "keyword-baseline"
    details: list[SkillDetail] = []
    dropped: int = Field(default=0, description="LLM items discarded because their quote was not in the text")
    usage: dict | None = None


class MatchRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    matcher: Literal["keyword", "tfidf", "llm"] = "keyword"


class Evidence(BaseModel):
    line: str
    line_number: int


class RequirementResult(BaseModel):
    requirement: str
    supported: bool
    evidence: list[Evidence]
    # Only set by the LLM matcher
    importance: Literal["required", "preferred"] | None = None
    note: str | None = Field(default=None, description="Short model-written reason; not verified")


class MatchResponse(BaseModel):
    matcher: str
    score: float = Field(ge=0.0, le=1.0)
    requirements: list[RequirementResult]
    missing: list[str]
    # Only set by the LLM matcher
    ungrounded: int | None = Field(default=None, description="Claims removed because the cited resume line did not exist")
    usage: dict | None = None
    # Only set by the TF-IDF matcher: cosine similarity of the whole resume and whole job description (0 to 1)
    doc_similarity: float | None = None


class ParsePdfResponse(BaseModel):
    text: str
    pages: int
