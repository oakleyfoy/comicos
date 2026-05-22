# Production Readiness

This guide prepares ComicOS for deployment without changing product behavior.

Important invariants remain unchanged:

- Gmail ingestion still creates `DraftImport` records only.
- `POST /imports/{id}/confirm` remains the only path that creates orders and inventory.
- No new providers, OCR, or FMV automation are introduced here.

## Required Environment Variables

Backend:

```text
APP_ENV=production
DATABASE_URL=<managed postgres connection string>
REDIS_URL=<managed redis connection string>
SECRET_KEY=<strong random secret>
FRONTEND_URL=<public frontend origin>
CORS_ORIGINS=<comma-separated frontend origins>
GOOGLE_CLIENT_ID=<google oauth client id>
GOOGLE_CLIENT_SECRET=<google oauth client secret>
GOOGLE_REDIRECT_URI=<public backend oauth callback>
OPENAI_API_KEY=<production openai key>
OPS_ADMIN_EMAILS=<comma-separated internal admin emails>
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Frontend:

```text
VITE_API_BASE_URL=<public backend api origin>
VITE_APP_NAME=ComicOS
VITE_OPS_ADMIN_EMAILS=<comma-separated internal admin emails>
```

Notes:

- Backend startup now fails clearly in `APP_ENV=production` if critical variables are missing.
- Do not put backend secrets in frontend `VITE_*` variables.
- The frontend only needs the public API base URL, app name, and optional ops-admin email allowlist.

## Production Config Checklist

Confirm all of the following before deploy:

- API URL is set and reachable from the frontend.
- frontend URL is set in `FRONTEND_URL`.
- `CORS_ORIGINS` includes the real frontend origin(s).
- Google OAuth redirect URI matches the deployed backend callback URL.
- OpenAI key is present and belongs to the intended funded project/org.
- Redis URL points to the managed Redis instance.
- database URL points to the managed Postgres instance.
- JWT `SECRET_KEY` is strong and not the development default.
- ops admin emails are populated for internal `/ops` access.

## Health Checks

Available health endpoints:

- `GET /health`
- `GET /health/db`
- `GET /health/redis`
- `GET /health/worker`

Expected behavior:

- `/health` confirms the API process is responding.
- `/health/db` confirms database connectivity.
- `/health/redis` confirms Redis connectivity.
- `/health/worker` confirms worker visibility and reports the registered queue names.

The internal `/ops/dashboard` page also surfaces queue and worker state, recent job results, duplicate skips, parser failures, and import lifecycle events.

## Migration Readiness

Confirm Alembic is at head before deployment:

```bash
cd apps/api
.\.venv\Scripts\python -m alembic current
.\.venv\Scripts\python -m alembic heads
```

Run migrations:

```bash
cd apps/api
.\.venv\Scripts\python -m alembic upgrade head
```

Empty production database bootstrap:

1. Provision Postgres.
2. Set `DATABASE_URL`.
3. Run `alembic upgrade head`.
4. Start the API.
5. Start the worker.

No manual seed step is required for the current application shape.

## Render Deployment Notes

Suggested service layout:

1. Backend web service
   - start command:
   ```bash
   cd apps/api && ./.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
   - env:
     `APP_ENV`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `FRONTEND_URL`, `CORS_ORIGINS`,
     `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
     `OPENAI_API_KEY`, `OPS_ADMIN_EMAILS`

2. Worker service
   - start command:
   ```bash
   cd apps/api && ./.venv/Scripts/python -m app.workers.rq_worker
   ```
   - env:
     same backend env set, especially `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`,
     Google OAuth settings, and `SECRET_KEY`

3. Frontend static/web service
   - build command:
   ```bash
   npm --workspace apps/web run build
   ```
   - env:
     `VITE_API_BASE_URL`, `VITE_APP_NAME`, `VITE_OPS_ADMIN_EMAILS`

4. Managed Postgres
   - provide the production `DATABASE_URL`

5. Managed Redis
   - provide the production `REDIS_URL`

## Pre-Deploy Checklist

- `alembic upgrade head` succeeds against the target database.
- backend starts cleanly with `APP_ENV=production`.
- `/health`, `/health/db`, `/health/redis`, and `/health/worker` return healthy responses.
- worker process is running and visible.
- frontend points to the correct public API URL.
- Google OAuth redirect URI matches deployed callback exactly.
- OpenAI key is present and funded.
- `/ops` is restricted to configured ops admin emails only.

## Validation Commands

Backend:

```bash
cd apps/api
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

Frontend:

```bash
npm --workspace apps/web run build
```
