# Local Runtime

This guide keeps local startup predictable on Windows and helps avoid stale listener conflicts during smoke tests.

## Clean Start

From `C:\comic-os`:

```bash
npm run kill:dev
npm run db:up
npm run redis:up
npm run db:migrate
npm run dev
```

That gives you:

- API on `http://127.0.0.1:8000`
- Web on `http://127.0.0.1:5173`

Run the local worker in a separate terminal if you need async parsing jobs:

```bash
npm run dev:worker:local
```

## Database And Redis

Start PostgreSQL:

```bash
npm run db:up
```

Start Redis:

```bash
npm run redis:up
```

Apply Alembic migrations:

```bash
npm run db:migrate
```

If you need a clean local database rebuild:

```bash
npm run db:reset
```

Stop Docker services:

```bash
npm run db:down
```

## Start API And Web

Start both together:

```bash
npm run dev
```

Or start each independently:

```bash
npm run dev:api
npm run dev:web
```

## Start Local Worker

For Windows local development, use the local worker entrypoint:

```bash
npm run dev:worker:local
```

The local worker watches every app queue needed for background execution:

- `ai_parse`
- `gmail_sync`

If you want the production-style worker instead:

```bash
npm run dev:worker
```

## Kill Stale Listeners

These helpers kill by port and print the PID they stopped. They do not fail when no matching process exists.

Kill stale API listeners on port `8000`:

```bash
npm run kill:api
```

Kill stale Vite listeners on port `5173`:

```bash
npm run kill:web
```

Kill both local dev listeners:

```bash
npm run kill:dev
```

Use `npm run kill:dev` before `npm run dev` whenever a smoke test behaves inconsistently or a previous terminal did not shut down cleanly.

## API Runtime Identity Check

Before OAuth testing or any runtime-sensitive local verification:

```bash
# in your local backend env
DEBUG_RUNTIME=true
```

Then restart the API and open:

```text
http://127.0.0.1:8000/debug/runtime
```

Confirm the reported `pid`, `cwd`, masked database URL, and masked Redis URL match the local repo and process you intend to test. Set `DEBUG_RUNTIME=false` again after the sanity check.

## Worker Diagnostics

Validate the local worker against the AI parse queue:

```bash
npm run worker:local:diagnose
```

Validate the local worker against the Gmail sync queue:

```bash
npm run worker:local:diagnose:gmail
```

If a dead local worker leaves jobs stuck in `StartedJobRegistry`, clean them up before rerunning smoke tests:

```bash
npm run worker:local:cleanup
```

This cleanup helper removes started jobs whose recorded worker is no longer active, which prevents dead-worker leftovers from blocking new Gmail sync attempts in local development.

## OpenAI Note

The current known blocker for AI parsing smoke tests is OpenAI quota. Manual draft flows can be verified locally without OpenAI, but AI-assisted import parsing remains blocked until the configured API key has quota again.
