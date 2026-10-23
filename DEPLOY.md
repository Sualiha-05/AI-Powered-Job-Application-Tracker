# Deploying for free

Frontend on **Vercel Hobby**, backend and ML service on **Render free web services**, database on **Neon Free**.
No credit card is needed for these. Free-tier terms change, so confirm each pricing page when you sign up.

> The code is prepared and tested locally in production mode (compiled build, `NODE_ENV=production`,
> empty database, secrets, CORS). It has not been deployed to these services yet, so expect to adjust
> small details such as setting names in each dashboard.

## 0. Before you start

Generate two long random values (keep them private; never commit them):

```bash
openssl rand -hex 32   # use once for JWT_SECRET
openssl rand -hex 32   # use once for ML_API_KEY
```

Push the repo to GitHub.

## 1. Neon (Postgres)

1. Create a project and copy its connection string (it ends with `?sslmode=require`).
2. If the backend cannot connect later, first check `DB_SSL=true` is set, then try the string with
   only the `sslmode` parameter.

## 2. Render: ML service (deploy this first)

New > Web Service > your repo.

| Setting | Value |
|---|---|
| Language | Docker |
| Root Directory | `ml-service` |
| Instance type | Free |
| Health Check Path | `/health` |

Environment variables:

| Name | Value |
|---|---|
| `ML_API_KEY` | the second random value |
| `ANTHROPIC_API_KEY` | optional; leave out to keep the LLM extractor off |
| `LLM_MODEL` | optional, default `claude-haiku-5-5` |

Copy its public URL (for example `https://job-tracker-ml.onrender.com`).

## 3. Render: backend

New > Web Service > same repo.

| Setting | Value |
|---|---|
| Language | Docker |
| Root Directory | `backend` |
| Instance type | Free |
| Health Check Path | `/health` |

Environment variables:

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `DB_SSL` | `true` |
| `DB_SYNCHRONIZE` | `true` for the **first deploy only** (creates the tables) |
| `JWT_SECRET` | the first random value |
| `ML_SERVICE_URL` | the ML service URL from step 2 |
| `ML_API_KEY` | exactly the same value as on the ML service |
| `FRONTEND_URL` | set in step 5 (Vercel URL) |

Copy the backend's public URL.

## 4. Vercel: frontend

Import the repo, set **Root Directory** to `frontend`, and add:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | the backend URL from step 3, no trailing slash |

`NEXT_PUBLIC_` values are baked in at build time, so redeploy after changing it.

## 5. Finish the wiring

1. On the Render backend set `FRONTEND_URL` to your Vercel URL (no trailing slash). Separate several
   origins with commas. Redeploy the backend.
2. **Delete `DB_SYNCHRONIZE`** from the backend and redeploy, so the schema is no longer auto-changed.

## 6. Smoke test

- [ ] `<backend>/health` returns `{"status":"ok"}`
- [ ] The Vercel site shows "API connected"
- [ ] Register, add an application, drag it to another column, refresh (it persists)
- [ ] Upload a text-based PDF resume and check the extracted text preview
- [ ] `<ml-service>/extract` called directly without the key returns 401

## Free-tier behavior to expect

- **Cold starts.** Free Render services sleep after about 15 minutes idle and take around a minute to wake.
  A cold backend calling a cold ML service can take about two minutes. Warm both up before sharing the link.
- **Instance hours.** Render's free allowance is shared across the workspace (about 750 hours a month).
  Pinging both services around the clock would exceed it. If you use a pinger, ping only the backend, or
  both only in the days around interviews.
- **Neon** suspends compute after about 5 minutes idle; the first query after that is a little slower.
- **Vercel Hobby** is for personal, non-commercial use. Do not add payments or ads.

## Protecting your wallet

- The ML service is publicly reachable on free hosting. `ML_API_KEY` stops strangers from calling it.
  Never leave it unset in production.
- Set a monthly spend limit on your Anthropic key. LLM extraction is the only part that costs money.
- The frontend never uses `method=llm`, so the public demo spends nothing unless you add that.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Browser "CORS" error | `FRONTEND_URL` does not exactly match the Vercel URL (scheme, no trailing slash); redeploy the backend |
| `500` on register | Tables missing: set `DB_SYNCHRONIZE=true` once, redeploy, then remove it |
| `502` on resume upload or match | `ML_API_KEY` differs between backend and ML service, or the ML service is waking up; retry in a minute |
| Frontend calls `localhost:3001` | `NEXT_PUBLIC_API_URL` was not set before the Vercel build; set it and redeploy |
| Backend cannot reach the database | `DB_SSL=true` missing, or a wrong connection string |

## Known gaps before real users

- Move from `DB_SYNCHRONIZE` to migrations.
- No rate limiting on login, register or upload yet.
- The login token is kept in `localStorage`; httpOnly cookies are safer.
