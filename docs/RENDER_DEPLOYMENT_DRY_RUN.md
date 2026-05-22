# Render Deployment Dry-Run

This document is a deployment planning checklist for Render.

Important constraints for this phase:

- Do not deploy yet.
- Do not change product behavior.
- Do not change ingestion logic, DraftImport behavior, confirm flow, Gmail provider logic, or parsing architecture.

The goal is to validate exactly how ComicOS should map onto Render services before any live service is created or changed.

## Placeholder Domains

Use placeholders until real domains are assigned:

- API domain: `https://api.example-comicos.com`
- frontend app domain: `https://app.example-comicos.com`
- Google OAuth redirect URI:
  `https://api.example-comicos.com/gmail/connect/callback`

## 1. Backend API Service

Recommended Render service type:

- `Web Service`

Repository/root settings:

- repository root: repo root
- service root directory: `apps/api`

Build command:

```bash
python -m pip install --upgrade pip
pip install -e .[dev]
```

Start command:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```text
APP_ENV=production
DATABASE_URL=<render postgres internal/external connection string>
REDIS_URL=<render redis connection string>
SECRET_KEY=<strong random jwt secret>
FRONTEND_URL=https://app.example-comicos.com
CORS_ORIGINS=https://app.example-comicos.com
GOOGLE_CLIENT_ID=<google oauth client id>
GOOGLE_CLIENT_SECRET=<google oauth client secret>
GOOGLE_REDIRECT_URI=https://api.example-comicos.com/gmail/connect/callback
OPENAI_API_KEY=<production openai key>
OPS_ADMIN_EMAILS=<comma-separated internal admin emails>
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Health check path:

```text
/health
```

Additional useful runtime checks after deploy:

- `/health/db`
- `/health/redis`
- `/health/worker`

## 2. Worker Service

Recommended Render service type:

- `Background Worker`

Repository/root settings:

- repository root: repo root
- service root directory: `apps/api`

Build command:

```bash
python -m pip install --upgrade pip
pip install -e .[dev]
```

Start command:

```bash
python -m app.workers.rq_worker
```

Required environment variables:

- exactly the same backend runtime env vars used by the API service:
  - `APP_ENV`
  - `DATABASE_URL`
  - `REDIS_URL`
  - `SECRET_KEY`
  - `FRONTEND_URL`
  - `CORS_ORIGINS`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
  - `OPENAI_API_KEY`
  - `OPS_ADMIN_EMAILS`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`

Queues listened to:

- `ai_parse`
- `gmail_sync`

## 3. Frontend Service

Recommended Render service type:

- `Static Site`

Reason:

- The frontend is a Vite SPA with a static build output.

Repository/root settings:

- repository root: repo root
- service root directory: `apps/web`

Build command:

```bash
npm install
npm run build
```

Publish directory:

```text
dist
```

Required frontend env vars:

```text
VITE_API_BASE_URL=https://api.example-comicos.com
VITE_APP_NAME=ComicOS
VITE_OPS_ADMIN_EMAILS=<comma-separated internal admin emails>
```

SPA rewrite rule:

- rewrite all unmatched routes to `/index.html`

Examples that must resolve via SPA rewrite:

- `/dashboard`
- `/orders/3`
- `/imports/email`
- `/ops`

## 4. Managed Services

### Render Postgres

Use:

- `Render PostgreSQL`

Provide to backend and worker:

- `DATABASE_URL`

### Render Redis / Key Value

Use:

- `Render Redis` or the current Render key-value/Redis-compatible managed offering

Provide to backend and worker:

- `REDIS_URL`

## 5. Production Domain Mapping

Planned values for dry-run only:

```text
API domain=https://api.example-comicos.com
Frontend domain=https://app.example-comicos.com
Google OAuth redirect URI=https://api.example-comicos.com/gmail/connect/callback
```

Before real deploy, verify:

- `VITE_API_BASE_URL` points to the real API origin
- `FRONTEND_URL` matches the public frontend origin
- `CORS_ORIGINS` includes the exact frontend origin(s)
- Google Cloud OAuth client has the exact callback URI configured

## 6. Secrets Checklist

These values must never be exposed to the frontend:

- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- `GOOGLE_CLIENT_SECRET`
- encrypted Gmail access/refresh tokens
- raw JWT signing secrets

Frontend-safe variables are limited to:

- `VITE_API_BASE_URL`
- `VITE_APP_NAME`
- `VITE_OPS_ADMIN_EMAILS`

Notes:

- `VITE_*` values are bundled into frontend code and are public by design.
- Do not place any secret or credential in a `VITE_*` variable.

## 7. Migration Process

Recommended order for first production bootstrap:

1. Create managed Postgres.
2. Create managed Redis.
3. Set backend env vars on the API service.
4. Set the same backend env vars on the worker service.
5. Run Alembic migrations:

```bash
cd apps/api
python -m alembic upgrade head
```

6. Start backend API service.
7. Verify:
   - `/health`
   - `/health/db`
   - `/health/redis`
8. Start worker service.
9. Verify:
   - `/health/worker`
   - `/ops/dashboard` as an ops admin user
10. Deploy frontend static site.
11. Verify frontend can reach backend and load authenticated routes.

For later updates:

1. Apply env changes if needed.
2. Run `alembic upgrade head`.
3. Deploy API.
4. Deploy worker.
5. Deploy frontend if frontend assets changed.

## 8. Rollback Plan

### If migration fails

1. Stop rollout.
2. Do not deploy new API/worker code against a partial schema.
3. Inspect Alembic error output.
4. Restore database from backup or snapshot if the migration was partially destructive.
5. Fix the migration issue offline.
6. Re-run `alembic upgrade head` only after validation.

### If API health fails

1. Check Render logs for startup validation failures.
2. Confirm required env vars exist and are non-empty.
3. Verify `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, Google OAuth settings, and `OPS_ADMIN_EMAILS`.
4. Roll back to the last known-good API deploy if necessary.

### If worker cannot connect to Redis

1. Check worker logs.
2. Verify `REDIS_URL`.
3. Confirm the managed Redis service is healthy and reachable from the worker service.
4. Keep API deployed if it is healthy, but treat async ingestion and sync jobs as degraded until worker connectivity is restored.

### If frontend cannot reach API

1. Verify `VITE_API_BASE_URL`.
2. Verify backend `CORS_ORIGINS`.
3. Confirm the API domain is publicly reachable.
4. If needed, redeploy the frontend with corrected public env vars.

### If Google OAuth callback fails

1. Verify `GOOGLE_REDIRECT_URI` in backend env.
2. Verify the exact same URI in Google Cloud OAuth credentials.
3. Confirm the API domain is public and serving the callback route.
4. Re-test Gmail connect flow after correcting the callback mismatch.

## 9. Pre-Deploy Dry-Run Checklist

- backend service shape chosen: `Web Service`
- worker service shape chosen: `Background Worker`
- frontend service shape chosen: `Static Site`
- placeholder API and frontend domains defined
- Google OAuth callback placeholder defined
- all backend secret env vars identified
- no backend secrets planned for frontend
- Alembic migration command confirmed
- bootstrap order documented
- rollback steps documented for API, worker, frontend, migration, and OAuth failures

## Validation Commands

Backend:

```bash
cd apps/api
python -m pytest
python -m ruff check .
```

Frontend:

```bash
npm --workspace apps/web run build
```
