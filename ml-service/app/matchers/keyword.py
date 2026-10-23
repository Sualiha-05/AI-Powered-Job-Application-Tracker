"""Baseline matcher: skills in the JD that also appear in the resume.

Returns *evidence* (the resume lines that mention each skill) so the UI can
show why a requirement counts as supported. Later matchers (embeddings, LLM)
should return the same MatchResponse shape so they can be swapped and compared.
"""
from ..extract import _contains, extract_skills
from ..schemas import Evidence, MatchResponse, RequirementResult
from ..skills import SKILLS


def match(resume_text: str, job_description: str) -> MatchResponse:
    requirements = extract_skills(job_description)
    resume_lines = [(i + 1, ln.strip()) for i, ln in enumerate(resume_text.splitlines()) if ln.strip()]

    results: list[RequirementResult] = []
    for req in requirements:
        aliases = SKILLS[req]
        evidence = [
            Evidence(line=ln, line_number=num)
            for num, ln in resume_lines
            if any(_contains(ln.lower(), a) for a in aliases)
        ]
        results.append(RequirementResult(requirement=req, supported=bool(evidence), evidence=evidence[:3]))

    supported = sum(r.supported for r in results)
    score = supported / len(results) if results else 0.0
    return MatchResponse(
        matcher="keyword-baseline",
        score=round(score, 3),
        requirements=results,
        missing=[r.requirement for r in results if not r.supported],
    )
