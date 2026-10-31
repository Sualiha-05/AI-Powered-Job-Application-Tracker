# Three-week plan

## Week 1: foundation + first ML endpoint
- [ ] Docker Compose runs all services (verify on your machine)
- [x] Auth, applications CRUD, kanban UI wired to the API (drag-and-drop + select fallback)
- [x] Resume upload + PDF-to-text (PDF or .txt, 4 MB limit, text parsed in the ML service)
- [x] LLM-based `/extract` with grounded quotes (keyword version kept as the baseline). Needs your API key to run for real
- [ ] Skeleton deployed at a public URL (code is ready for three Vercel projects + Neon; follow DEPLOY.md)

## Week 2: matching with evidence
- [x] LLM matcher returning the same `MatchResponse` (grounded evidence, per-user and global daily limits)
- [x] TF-IDF matcher as the lightweight middle option (pure Python; embedding models are too big for the 250 MB function limit)
- [x] Matching saved as a result row in Postgres (runs inside the request; Vercel functions cannot keep a worker alive, so no BullMQ/Redis and no pending state)
- [x] Match dialog with evidence in the UI (keyword baseline for now)

## Week 3: evaluation, polish, launch
- [x] Evaluation harness built: `evaluation/` (labeling tool, scoring, bias audit; see `evaluation/README.md`)
- [ ] Write about 10 real postings and 4 to 5 made-up resume variants each; label them blind; commit `labels.json`
- [ ] Tune the TF-IDF threshold on `dev`, then report `test` once (keyword, TF-IDF, AI with 3 repeats)
- [ ] Name-swap bias audit (replace the illustrative name list with a validated one)
- [ ] CI, tests on critical paths, final deploy
- [ ] README (diagram, related work, results, what failed), demo video, 3-5 users

## If behind, cut in this order
Dashboard counts -> bias audit scope -> number of AI repeats.
Never cut: live deployment, evidence-based match view, evaluation table.
