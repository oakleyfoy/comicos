# ComicOS API

FastAPI backend for ComicOS.

## Environment

The API uses `DATABASE_URL` for database connectivity.

Example:

```text
DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5433/comic_os
SECRET_KEY=dev-secret-key-32-bytes-minimum-1234
ACCESS_TOKEN_EXPIRE_MINUTES=60
OPENAI_API_KEY=
REDIS_URL=redis://localhost:6379/0
```

For local Docker-based development, the repo root `docker-compose.yml` starts PostgreSQL on
`localhost:5433` with that same connection string.

Notes:

- `SECRET_KEY` should be at least 32 bytes for HS256 token signing.
- `OPENAI_API_KEY` is only required for AI import parsing.
- `REDIS_URL` is required for background job enqueueing and the RQ worker.

## Migrations

Run the initial migration with:

```bash
alembic upgrade head
```

## Authentication

Available endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /ai/parse-order`
- `POST /imports/parse-jobs`
- `GET /imports/parse-jobs/{job_id}`

## AI Draft Parsing

`POST /ai/parse-order` accepts pasted receipt or invoice text and returns an editable draft order.

For background parsing infrastructure, `POST /imports/parse-jobs` enqueues AI parse work on Redis + RQ
and `GET /imports/parse-jobs/{job_id}` reports status until the draft import record is created.

Important:

- The AI parser never writes to the database.
- The AI parser never creates inventory directly.
- Users must still review and confirm the draft through the normal order creation flow.
- If `OPENAI_API_KEY` is missing, the endpoint returns `503` with `AI parser is not configured.`

To enable the parser locally:

1. Set `OPENAI_API_KEY` in `apps/api/.env` or the repo root `.env`.
2. Make sure `SECRET_KEY` is set to a 32+ byte value.
3. Restart the backend:

```bash
uvicorn app.main:app --reload
```

4. Open `/orders/import` in the frontend and paste sample text from `docs/sample_order_texts/whatnot_sample.txt`.
5. Review all warnings, confidence, and extracted fields before submitting.

AI output is draft data only and must be manually reviewed before confirmation.

## Worker

Run the worker in a separate terminal:

```bash
python -m app.workers.rq_worker
```

The worker runs with scheduler support enabled so retry intervals and delayed jobs work without
introducing a heavier async stack.
