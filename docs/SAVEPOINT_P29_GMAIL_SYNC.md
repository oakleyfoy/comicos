# ComicOS Savepoint P29 Gmail Sync

## Purpose
This document records the ComicOS state after scheduled Gmail sync support was added on top of the existing Gmail OAuth and Redis/RQ worker foundation. The goal of this savepoint is to confirm the app is ready for real OAuth testing without changing the confirm boundary: Gmail sync still creates draft imports only, and inventory creation still requires explicit confirmation.

## Scope of This Savepoint
- Gmail OAuth foundation exists in the backend and frontend.
- Scheduled Gmail sync settings and last-run status fields exist on `gmail_account`.
- Manual Gmail sync and scheduled Gmail sync both enqueue background jobs rather than creating inventory directly.
- Local runtime verification was run after applying migrations.
- Runtime bug fixes were limited to issues discovered during this verification:
  - local listener cleanup scripts now clear live port listeners more reliably on Windows
  - backend dependency install now uses a pinned `cryptography==46.0.3` wheel version that installs cleanly on this Windows ARM environment

## Gmail OAuth Foundation Status

### Backend Integration
- Gmail OAuth config is driven by:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
- Gmail account state is stored in `gmail_account`.
- Imported-message deduplication is stored in `gmail_import_record`.
- OAuth tokens are encrypted before storage.
- Missing Gmail config is handled as a clean disabled state rather than a server crash.

### Current Endpoint Surface
- `GET /gmail/connect/start`
  - builds the Google OAuth authorization URL
  - returns `503` if Gmail OAuth is not configured locally
- `GET /gmail/connect/callback`
  - exchanges the auth code and stores Gmail tokens
- `GET /gmail/status`
  - returns config and connection state
  - when local Gmail env vars are missing, it still responds cleanly with `configured=false` and `connected=false`
- `POST /gmail/disconnect`
  - removes stored Gmail tokens and disables future syncs until reconnect
- `PATCH /gmail/sync/settings`
  - toggles scheduled auto sync
- `GET /gmail/sync/status`
  - returns current auto-sync setting plus last sync timestamps, status, and error
- `POST /gmail/sync`
  - enqueues a Gmail sync job
  - returns `503` if Gmail OAuth is not configured or the account is not connected
- `GET /gmail/sync/{job_id}`
  - returns manual Gmail sync job status
- `GET /gmail/imports`
  - lists Gmail-created draft imports

## Scheduled Sync Fields
The `gmail_account` model now tracks scheduled-sync runtime state with:

- `auto_sync_enabled`
- `last_sync_started_at`
- `last_sync_completed_at`
- `last_sync_status`
- `last_sync_error`

These fields are updated by the Gmail sync job and by the scheduled scan runner so the UI can show the latest Gmail sync state without querying worker internals directly.

## Queue And Worker Commands

### Required Local Services
- PostgreSQL:
  - `npm run db:up`
- Redis:
  - `npm run redis:up`
- Migrations:
  - `npm run db:migrate`

### App Runtime
- API + web:
  - `npm run dev`
- Windows local worker:
  - `npm run dev:worker:local`
- Standard worker:
  - `npm run dev:worker`

### Cleanup Helpers
- API listener cleanup:
  - `npm run kill:api`
- Web listener cleanup:
  - `npm run kill:web`
- Combined cleanup:
  - `npm run kill:dev`

The cleanup scripts were updated during this verification so they repeatedly inspect live listeners and stop real processes rather than relying on a single snapshot.

## Local Verification Performed

### Migrations
- `npm run db:migrate` applied successfully, including:
  - `20260523_0006_add_gmail_foundation`
  - `20260523_0007_add_gmail_sync_status_fields`

### Runtime
- PostgreSQL started successfully.
- Redis started successfully.
- `npm run dev` started a fresh API/web runtime.
- `npm run dev:worker:local` started a healthy local worker.

### Non-OAuth Gmail State
Local Gmail OAuth env vars were not configured during this verification, so no OAuth attempt was made.

Verified behavior from a clean isolated API process:
- `GET /health` returned `200`
- `GET /health/db` returned `200` with `database=connected`
- `GET /gmail/status` returned `200` with:
  - `configured=false`
  - `connected=false`
- `GET /gmail/sync/status` returned `200` with:
  - `auto_sync_enabled=false`
  - no last-run timestamps
  - no sync error

This confirms the missing-config and not-connected states are handled cleanly instead of failing with server errors.

### Integrations UI State
- The protected route for `/settings/integrations` exists in the web app.
- The page uses `GET /gmail/status` and `GET /gmail/sync/status` to render Gmail state.
- In the unconfigured state, the UI is designed to show:
  - `Not configured`
  - `Not connected`
  - setup guidance for `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`
  - disabled connect/auto-sync/disconnect controls
- Frontend build verification passed, which confirms the integrations page compiles cleanly.

## Runtime Caveat Observed On This Machine
During verification, `http://127.0.0.1:8000` showed evidence of stale or ghost listener behavior on this Windows environment even after the live `uvicorn` process restarted. To complete deterministic API verification, a clean isolated API instance was run on `http://127.0.0.1:8011`.

What this means:
- the Gmail codepaths themselves are healthy when exercised against the current app code
- the repo-level fixes above improved local reproducibility
- real OAuth testing on this machine should prefer a fresh listener check before assuming `8000` is serving the newest process

## Known Blockers
- Real Gmail OAuth testing still requires valid Google OAuth credentials:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
- Parsing synced Gmail receipts still depends on OpenAI parsing capacity and quota.

## Confirm Boundary Reminder
The confirm boundary remains intact:

- Gmail sync creates `DraftImport` records only.
- Gmail sync does not create orders directly.
- Gmail sync does not create inventory directly.
- `POST /imports/{id}/confirm` remains the only path that creates orders and inventory.

## Verified Check Summary
- Migrations applied successfully.
- Backend dependency install is reproducible again on the verified Windows ARM environment.
- Backend health endpoints passed.
- Gmail missing-config and not-connected states passed cleanly.
- Backend worker startup passed.
- Backend tests are expected to cover Gmail sync and scheduled Gmail sync behavior.
- Backend Ruff and frontend build should remain part of the final verification after this savepoint.
