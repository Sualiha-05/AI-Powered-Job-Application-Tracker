# Deploying for free (no card): Vercel + Neon

Three **Vercel** projects from this one repo (`frontend`, `backend`, `ml-service`) and one **Neon** Postgres
database. The Dockerfiles in this repo are for local development; Vercel does not use them.

> The code is tested locally in production mode (compiled build, `NODE_ENV=production`, empty database,
> shared secret, CORS, small DB pool, upload cap, ML timeout). It has **not** been deployed to Vercel yet, so
> expect to adjust small details in the dashboard. Free-tier terms change: confirm them on the pricing pages.

## 0. Before you start

Generate two long random values and keep them private (never commit them):

```bash
openssl rand -hex 32   # JWT_SECRET
openssl rand -hex 32   # ML_API_KEY
```

No `openssl`? In Node: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`.

Push the repo to GitHub.

## 1. Neon: database and tables

In the Neon console open **Connect** and copy two connection strings for the same database:

- **Direct** (no pooling): used once, from your computer, to create the tables.
- **Pooled** (the host contains `-pooler`): used by the deployed backend.

Both should end with `sslmode=require`.

**Create the tables from your computer** (do this once; the deployed backend will not create them):

```bash
cd backend && npm install
# macOS / Linux
DATABASE_URL='<direct connection string>' DB_SSL=true npm run start:dev
```

```powershell
# Windows PowerShell
cd backend; npm install
$env:DATABASE_URL='<direct connection string>'; $env:DB_SSL='true'; npm run start:dev
```

Wait for "Nest application successfully started", then press Ctrl+C. In the Neon console, the **Tables** view
should now list `users`, `applications` and `resumes`.

**Repeat this step whenever the database schema changes.** Week 2 added a `match_results` table, so run the same
command once more before using the Match feature; existing data is kept and the new table is added. The Neon **Tables**
view should then also list `match_results`.

## 2. Vercel project 1: ML service (deploy this first)

Add New > Project > import the repo, then set **Root Directory** to `ml-service`. Leave build and output
settings empty: Vercel detects FastAPI, and `pyproject.toml` tells it where the app is (`app.main:app`).

| Environment variable | Value |
|---|---|
| `ML_API_KEY` | the second random value |
| `ANTHROPIC_API_KEY` | optional; leave out to keep the LLM extractor off |
| `LLM_MODEL` | optional, default `claude-haiku-5-5` |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | `8` and `0` if your plan's function limit turns out to be 10 s |

Open `<ml-url>/health`. It should return `{"status":"ok","service":"ml-service"}`.

## 3. Vercel project 2: backend

Import the same repo again, **Root Directory** `backend`. Vercel detects NestJS from `src/main.ts`.

| Environment variable | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** connection string |
| `DB_SSL` | `true` |
| `JWT_SECRET` | the first random value |
| `ML_SERVICE_URL` | the ML project URL, no trailing slash |
| `ML_API_KEY` | exactly the same value as on the ML project |
| `ML_TIMEOUT_MS` | optional; `8000` if your function limit is 10 s (default 25000) |
| `FRONTEND_URL` | set in step 5 |

Open `<backend-url>/health`.

## 4. Vercel project 3: frontend

Import the repo a third time, **Root Directory** `frontend`.

| Environment variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the backend URL from step 3, no trailing slash |

`NEXT_PUBLIC_` values are baked in at build time, so redeploy after changing it.

## 5. Finish the wiring

Set `FRONTEND_URL` on the backend project to the frontend's URL (exact scheme, no trailing slash; separate several
origins with commas), then redeploy the backend.

## 6. Smoke test

- [ ] `<backend-url>/health` and `<ml-url>/health` return `ok`
- [ ] The site shows "API connected"
- [ ] Register, add an application, drag it to another column, refresh (it persists)
- [ ] Upload a text-based PDF resume (under 4 MB) and check the extracted text preview
- [ ] `POST <ml-url>/extract` called directly without the key returns 401

## What to expect on the free plan

- **Cold starts.** After a quiet period the first request is slower (function start, plus Neon waking after about
  5 minutes idle). There is no fixed 15-minute sleep, but warm things up before sharing the link.
- **Function limits.** Sources disagree on the Hobby time limit (10 s vs 300 s). Check **Settings > Functions** in
  your Vercel project. If it is 10 s, use the short-timeout variables above.
- **Upload size.** The app caps resumes at 4 MB because Vercel documents a 4.5 MB request-body limit.
- **Hobby is for personal, non-commercial use.** Do not add payments or ads.
- **Background work.** Functions are not long-lived, so work happens inside the request. Week 2 stores match
  results in Postgres instead of using a queue.

## Protecting your wallet

- The ML project is publicly reachable. `ML_API_KEY` stops strangers calling it. Never leave it unset in production.
- Set a monthly spend limit on your Anthropic key. LLM extraction is the only part that can cost money.
- The frontend never uses `method=llm`, so the public demo spends nothing unless you add that.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser "CORS" error | `FRONTEND_URL` does not exactly match the frontend URL; fix it and redeploy the backend |
| `500` on register or match | Tables missing or out of date: repeat the create-tables step in section 1 |
| `502` on resume upload or match | `ML_API_KEY` differs between projects, the ML project is waking up, or `ML_TIMEOUT_MS` is too low; check the ML project's logs |
| `FUNCTION_INVOCATION_TIMEOUT` | The plan's time limit was hit: use the short-timeout variables and retry |
| `413` on upload | File is over 4 MB |
| Frontend calls `localhost:3001` | `NEXT_PUBLIC_API_URL` was not set before the build; set it and redeploy |
| Backend cannot reach the database | `DB_SSL=true` missing, wrong string, or a direct string used where the pooled one belongs |
| ML project build cannot find dependencies | Check Root Directory is `ml-service` and `pyproject.toml` / `requirements.txt` are present; send me the build log |
| Vercel asks for a card | Tell me; we will look at other options |

## Known gaps before real users

- Tables are created with TypeORM sync; move to migrations.
- No rate limiting on login, register or upload yet.
- The login token is kept in `localStorage`; httpOnly cookies are safer.
