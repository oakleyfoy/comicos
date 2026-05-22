# ComicOS Savepoint P22B Async Worker

## Purpose
This document records the ComicOS state after Redis/RQ background job infrastructure was added, the `/orders/import` UI was moved to async parse-job polling, and the Windows local worker path was fixed so local queued jobs execute reliably. Live AI smoke testing is paused because the configured OpenAI key currently returns `429 insufficient_quota`.

## Scope of This Savepoint
- Redis-backed background job infrastructure exists for AI import parsing.
- A separate worker process exists for queued AI parse jobs.
- `/orders/import` uses async parse jobs instead of the old synchronous draft creation path.
- Windows local development now has a dedicated worker mode that actually executes queued jobs.
- A local worker diagnostic command exists and passes.
- The confirm boundary is unchanged: async parse jobs still only produce drafts, and `POST /imports/{id}/confirm` remains the only path that creates orders or inventory.

## Current Async Architecture

### Queue and Worker Foundation
- Redis is the backing queue store.
- RQ is the job system.
- The AI parse queue name is `ai_parse`.
- Async parse jobs are enqueued through `POST /imports/parse-jobs`.
- Job status is read through `GET /imports/parse-jobs/{job_id}`.
- The frontend polls job status and waits for a terminal state before loading the draft form.

### Backend Flow
1. User submits pasted receipt text.
2. API enqueues an AI parse job on Redis/RQ.
3. Worker executes `run_ai_parse_import_job`.
4. Job runs the existing parser and persisted-draft creation flow.
5. If successful, the job result includes the created `DraftImport` identifier.
6. Frontend polls until the job reaches `finished` or `failed`.
7. If finished, the frontend loads the saved draft into the editable import review form.
8. User can save edits with `PATCH /imports/{id}`.
9. User can confirm with `POST /imports/{id}/confirm`.

## Windows Local Worker Path

### Why It Was Needed
The original local Windows runtime showed this failure pattern:
- Redis healthy
- API healthy
- worker starts and listens on `ai_parse`
- jobs enqueue successfully
- jobs move into RQ intermediate/WIP Redis structures
- polling remains `queued`
- worker never actually executes the job body

### Local Fix
- Production-style worker path remains available through `app.workers.rq_worker`.
- Windows local development now uses `app.workers.rq_worker_local`.
- The local worker uses a Windows-compatible non-forking worker mode with a Windows-safe timeout/death-penalty implementation.
- Job lifecycle logging was added for:
  - worker startup
  - queue name
  - job pickup
  - job start
  - job finish
  - job failure

### Current Commands
- Standard worker:
  - `npm run dev:worker`
- Windows local worker:
  - `npm run dev:worker:local`
- Local worker diagnostic:
  - `npm run worker:local:diagnose`

## Diagnostic Verification
The local diagnostic command now completes successfully:
- it enqueues a no-op diagnostic job
- the local worker picks it up
- the job reaches `finished`
- the diagnostic result is printed back to the terminal

This proves that local Windows queued job execution is now working at the worker/runtime layer.

## Async Import UI State
- `/orders/import` now enqueues parse jobs instead of calling the synchronous draft creation path directly.
- The UI supports these job states:
  - `queued`
  - `started`
  - `finished`
  - `failed`
- While a job is active, the parse button is disabled.
- On success, the returned `DraftImport` is loaded into the editable review form.
- The existing draft save, confirm, and discard flows remain intact.

## Current Known Blocker
Live async AI smoke testing is currently blocked by the upstream OpenAI account state, not by Redis/RQ worker execution.

### Observed Runtime Behavior
- Async jobs now leave `queued`.
- Observed real status progression:
  - `queued`
  - `scheduled`
  - `started`
  - `failed`
- Worker logs show the job being picked up and started.
- The job then fails during the outbound OpenAI API request.

### Current Error
- OpenAI response: `HTTP 429`
- Reported error code: `insufficient_quota`
- Meaning: the configured API key is present, but the account quota/billing state does not currently allow successful model execution.

## What Is Working Right Now
- Redis container starts and stays healthy.
- API starts and serves health endpoints.
- Web app starts and protects `/orders/import` behind auth.
- Local worker execution now works on Windows.
- Async job enqueueing works.
- Async job polling works.
- Async job failure now reaches a terminal state instead of getting stuck forever.
- Backend tests pass.
- Backend Ruff passes.
- Frontend build passes.

## What Is Not Yet Verified End to End
Because OpenAI parsing is failing upstream with `insufficient_quota`, this savepoint does not yet include a successful live verification of:
- parse job reaching `finished`
- `DraftImport` loading from a successful real AI parse
- saving edits to that successful draft
- confirming that successful draft into a real order
- `/imports` showing a confirmed linked order from a successful AI parse
- `/orders` showing the created order from that successful AI parse
- dashboard inventory increasing from that successful AI parse flow

## Confirm Boundary Status
The confirm boundary remains intact:
- async parse jobs only create persisted drafts
- async parse jobs do not create orders directly
- async parse jobs do not create inventory directly
- `POST /imports/{id}/confirm` is still the only import workflow step that creates orders and inventory

## Next Action After Quota Is Fixed
Resume P22 live smoke testing with the following steps:
1. Start Redis.
2. Start API and web.
3. Start the local Windows worker with `npm run dev:worker:local`.
4. Log in to the app.
5. Open `/orders/import`.
6. Paste `docs/sample_order_texts/whatnot_sample.txt`.
7. Verify the parse job reaches `finished`.
8. Verify the `DraftImport` loads into the editable form.
9. Save a small draft edit.
10. Confirm the draft.
11. Verify:
    - `/imports` shows the confirmed import with linked order
    - `/orders` shows the created order
    - `/dashboard` inventory increases

## Recommended Follow-Up
- Once quota/billing is corrected, rerun the full P22 smoke test before making any new ingestion changes.
- If OpenAI still fails after quota is restored, capture the exact worker log error and continue debugging from this savepoint rather than changing the queue or confirm architecture again.
