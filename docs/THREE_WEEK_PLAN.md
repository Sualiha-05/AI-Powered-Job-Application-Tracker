# Three-week plan

## Week 1: foundation + first ML endpoint
- [ ] Docker Compose runs all services (verify on your machine)
- [x] Auth, applications CRUD, kanban UI wired to the API (drag-and-drop + select fallback)
- [x] Resume upload + PDF-to-text (PDF or .txt, 5 MB limit, text parsed in the ML service)
- [x] LLM-based `/extract` with grounded quotes (keyword version kept as the baseline). Needs your API key to run for real
- [ ] Skeleton deployed at a public URL (code is production-ready; follow DEPLOY.md)

## Week 2: matching with evidence
- [ ] Embeddings + LLM matcher returning the same `MatchResponse`
- [ ] Matching as a background job (BullMQ + Redis)
- [ ] Match results view with evidence in the UI

## Week 3: evaluation, polish, launch
- [ ] Labeled set + metrics for each matcher
- [ ] Name-swap bias audit
- [ ] CI, tests on critical paths, final deploy
- [ ] README (diagram, related work, results, what failed), demo video, 3-5 users

## If behind, cut in this order
Dashboard counts -> bias audit scope -> embeddings matcher.
Never cut: live deployment, evidence-based match view, evaluation table.
