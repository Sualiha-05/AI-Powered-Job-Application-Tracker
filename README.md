# Job Tracker

An application tracker with an explainable resume-to-job match engine.
Paste a job description, pick a resume, and see which requirements are
supported by which resume lines, and which are missing.

> Status: scaffold (week 1). See `docs/` for the spec and plan.

## Architecture

```
Next.js frontend  ->  NestJS API (Postgres)  ->  FastAPI ML service
                           |
                      Redis (queue, week 2)
```

| Folder | What it is |
|---|---|
| `frontend/` | Next.js (App Router) kanban UI |
| `backend/` | NestJS REST API: auth (JWT), applications CRUD, match proxy |
| `ml-service/` | FastAPI: `/extract` and `/match` (keyword baseline included) |
| `docs/` | MVP spec, architecture, three-week plan |

## Run it

```bash
cp .env.example .env        # then change the secrets
docker compose up --build
```

- Frontend: http://localhost:3000
- API health: http://localhost:3001/health
- ML service docs: http://localhost:8000/docs

Deploying for free, no card needed (three Vercel projects + Neon): see [DEPLOY.md](DEPLOY.md).

## Try the API

```bash
# register (returns an accessToken)
curl -X POST localhost:3001/auth/register -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"password123"}'

# create an application
curl -X POST localhost:3001/applications -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"company":"Acme","title":"Full Stack Engineer"}'

# upload a resume (PDF or .txt, max 4 MB)
curl -X POST localhost:3001/resumes -H "Authorization: Bearer <token>" -F "file=@resume.pdf"

# match a stored resume against an application's job description
curl -X POST localhost:3001/match/by-ids -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"resumeId":"<resume id>","applicationId":"<application id>"}'

# run a match and save it (history is kept per application)
curl -X POST localhost:3001/applications/<application id>/matches -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{"resumeId":"<resume id>"}'
curl localhost:3001/applications/<application id>/matches -H "Authorization: Bearer <token>"

# same, using the free TF-IDF matcher
curl -X POST localhost:3001/applications/<application id>/matches -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{"resumeId":"<resume id>","matcher":"tfidf"}'

# same, using the AI matcher (needs GEMINI_API_KEY or ANTHROPIC_API_KEY on the ML service; limited per day)
curl -X POST localhost:3001/applications/<application id>/matches -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{"resumeId":"<resume id>","matcher":"llm"}'

# or match raw text directly
curl -X POST localhost:3001/match -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"resumeText":"Built APIs with Python and Docker","jobDescription":"Python, Docker, Kubernetes"}'
```

## LLM skill extraction (optional)

Add one provider key to `.env` (`GEMINI_API_KEY=...` has a free tier; `ANTHROPIC_API_KEY=...` is paid), restart, then:

```bash
curl -X POST localhost:8000/extract -H "Content-Type: application/json" \
  -d '{"text":"Need React and Node.js. Kubernetes is a plus.","method":"llm"}'
```

Or compare both extractors from a terminal: `cd ml-service && python scripts/try_extract.py [file.txt]`.
Without a key, `method=llm` returns 503 and everything else keeps working.

## Tests

```bash
cd ml-service && pip install -r requirements-dev.txt && pytest
cd backend && npm install && npm test
cd frontend && npm install && npm run lint
```

## Related work, results, limitations

To fill in during week 3: related-work table, evaluation results,
bias audit, and a "what failed and why" section.
