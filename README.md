# ComicOS

ComicOS is a monorepo for building portfolio intelligence tools for comic investors. This starter
setup includes a FastAPI backend and a React + Vite frontend with a dark dashboard-style UI.

## Project Structure

```text
comic-os/
  apps/
    api/   # FastAPI backend
    web/   # React + Vite + TypeScript frontend
  docs/    # Project documentation
  scripts/ # Utility scripts
```

## Current Scope

This scaffold intentionally does **not** include:

- database models
- comic inventory domain models

## Local Development

### Local Runtime

For the clean local runtime workflow, stale-listener cleanup, and Windows helper scripts, see
`docs/LOCAL_RUNTIME.md`.

Typical local startup from `C:\comic-os`:

```bash
npm run kill:dev
npm run db:up
npm run redis:up
npm run dev
npm run dev:worker:local
```

Use `npm run kill:dev` before `npm run dev` when a previous local session did not shut down cleanly.

AI parse jobs still require an `OPENAI_API_KEY` with available quota. Manual draft flows work
without OpenAI, but AI-assisted parse jobs will not succeed until quota is available again.

### Start Both Apps From Root

After installing backend and frontend dependencies, run this from `C:\comic-os`:

```bash
npm run dev
```

This starts:

- FastAPI on `http://127.0.0.1:8000`
- Vite on `http://127.0.0.1:5173`

Run the background worker in a separate terminal:

```bash
npm run dev:worker
```

The worker uses Redis + RQ with scheduler support enabled so queued AI parse jobs, retry
delays, and future scheduled jobs share the same lightweight infrastructure.

### Local Services With Docker

For local development, PostgreSQL and Redis containers are available at the repo root.

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Or use the root script:

```bash
npm run db:up
```

Start Redis:

```bash
npm run redis:up
```

Run migrations:

```bash
npm run db:migrate
```

Reset the local Docker development database:

```bash
npm run db:reset
```

Warning:

- `npm run db:reset` deletes all data in the local Docker `comic_os` database and rebuilds it from Alembic migrations.
- It targets only the local Docker Postgres container for this repo and does not target Render or any production environment.

Stop the database:

```bash
npm run db:down
```

The local connection string is:

```text
postgresql+pg8000://postgres:postgres@localhost:5433/comic_os
```

### Backend

Requirements:

- Python 3.12

Setup:

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
```

API health check:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/health/db`
- `POST http://127.0.0.1:8000/auth/register`
- `POST http://127.0.0.1:8000/auth/login`
- `GET http://127.0.0.1:8000/auth/me`
- `POST http://127.0.0.1:8000/ai/parse-order`
- `POST http://127.0.0.1:8000/imports/parse-jobs`
- `GET http://127.0.0.1:8000/imports/parse-jobs/{job_id}`

### Frontend

Requirements:

- Node.js 20+

Setup:

```bash
cd apps/web
npm install
npm run dev
```

Frontend app:

- `http://127.0.0.1:5173`

## Deploy Guardrails

Run the repo-level deploy checks from the root before pushing code that should be safe for Render:

```bash
npm run verify:deploy
```

That verification blocks pushes when deploy-critical source files are still untracked, then smoke-tests the
FastAPI app import path and the production web build.

To install the local git `pre-push` hook once on your machine:

```bash
npm run hooks:install
```

GitHub Actions also runs the same deploy-readiness check for pull requests and pushes to `main`.

## Environment Files

Copy the example environment files before adding real values:

- `apps/api/.env.example`
- `apps/web/.env.example`

Local backend notes:

- `SECRET_KEY` should be at least 32 bytes for HS256 token signing.
- `OPENAI_API_KEY` is only required when you want to use AI import parsing through `/orders/import` or `POST /ai/parse-order`.
- `REDIS_URL` is required for background job enqueueing and the worker process.

## AI Draft Order Testing

To test the AI draft parser locally:

1. Put your OpenAI key in `apps/api/.env` or the repo root `.env` as `OPENAI_API_KEY=...`.
2. Make sure `SECRET_KEY` is set to a 32+ byte value in the same backend environment.
3. Restart the backend after changing environment variables:

```bash
cd apps/api
uvicorn app.main:app --reload
```

4. Sign in to the web app and open `http://127.0.0.1:5173/orders/import`.
5. Paste sample receipt text from `docs/sample_order_texts/whatnot_sample.txt`, then click `Parse Draft`.
6. Review the AI warnings, confidence score, and every editable field before confirming.
7. Confirm the draft only after manual review. The parser never creates inventory until the normal order submit step runs.

If `OPENAI_API_KEY` is missing, `POST /ai/parse-order` returns a clean `503` response with `AI parser is not configured.` instead of crashing the backend.

For a focused end-to-end checklist, see `docs/LOCAL_AI_SMOKE_TEST.md`.
