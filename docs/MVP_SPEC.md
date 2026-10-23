# MVP spec

## In scope
- Register / login (JWT)
- Kanban of applications: Saved, Applied, Interview, Offer, Rejected
- Paste a job description, upload a resume (PDF to text)
- Match result with evidence: supported requirements show the resume lines
  behind them; missing requirements are listed
- Simple dashboard counts

## Out of scope (until MVP works)
Auto-apply, browser extension, email parsing, fine-tuned models.

## Evaluation (week 3)
- 40-60 labeled resume/JD pairs from public or synthetic data
- Compare: keyword baseline vs embeddings vs LLM-with-evidence
- Name-swap bias audit on ~30 pairs
- README: results table and a "what failed and why" section
