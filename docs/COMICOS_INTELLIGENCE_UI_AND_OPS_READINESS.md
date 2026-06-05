# ComicOS Intelligence UI and Ops Readiness

**Date:** 2026-06-05  
**Production owner reference:** `ofoy@att.net` → `owner_user_id=1`, 22 `inventory_copy` rows (Render Postgres).  
**P63/P64:** Certified on production after `alembic upgrade head` (see prior certification run).

## Phase 1 — Migration safety

| Mechanism | Behavior |
|-----------|----------|
| **Render API boot** | `apps/api/scripts/render_web_start.py` runs `alembic upgrade head` in a **subprocess** when `APP_ENV=production` and `DISABLE_STARTUP_MIGRATIONS` is not set (`app/db/startup_migrations.py`). Uvicorn starts **after** migrations complete. |
| **GitHub Actions** | [`.github/workflows/migrate-production.yml`](../.github/workflows/migrate-production.yml) — manual `workflow_dispatch`; uses repository secret `PRODUCTION_DATABASE_URL` (External Database URL from Render; **not** stored in repo). |
| **Local / CI check** | `cd apps/api && python -m alembic current` and `python -m alembic upgrade head` against target DB before cert or deploy. |

**Production incident (2026-06-05):** API connected to Render before P63/P64 tables existed. Fix: run `alembic upgrade head` (manual cert session + ensure deploy uses `render_web_start.py` with `APP_ENV=production`).

**Do not** commit `DATABASE_URL` or Render credentials. Use Render dashboard or GitHub Actions secrets only.

See also: [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md), [DATABASE_ENVIRONMENT_AUDIT.md](DATABASE_ENVIRONMENT_AUDIT.md).

## Phase 2 — API endpoint status

All paths are authenticated Scan API v1 (`GET`, bearer token). Smoke coverage: `apps/api/tests/test_intelligence_endpoints_smoke.py`.

| Endpoint | Status | Notes |
|----------|--------|--------|
| `/api/v1/recommendation-intelligence/buy-queue/latest` | Registered | P62 buy queue |
| `/api/v1/recommendation-intelligence/foc/latest` | Registered | Alias of FOC alerts (also `/foc/alerts`) |
| `/api/v1/recommendation-intelligence/pull-forecast/latest` | Registered | P62 pull forecast |
| `/api/v1/recommendation-intelligence/watchlists/latest` | Registered | Alias of auto watchlists (also `/watchlists/auto`) |
| `/api/v1/market-intelligence/portfolio/latest` | Registered | P63; requires `P63_MARKET_INTELLIGENCE_ENABLED` (default on) |
| `/api/v1/market-intelligence/sell-signals/latest` | Registered | P63 |
| `/api/v1/market-intelligence/acquisition/latest` | Registered | P63 |
| `/api/v1/market-intelligence/signals/latest` | Registered | P63 market signals |
| `/api/v1/collector-assistant/dashboard/latest` | Registered | P64 executive bundle |
| `/api/v1/collector-assistant/briefing/latest` | Registered | P64 |
| `/api/v1/collector-assistant/recommendations/latest` | Registered | P64 lane recommendations |

**Live production HTTP smoke:** Requires a valid user JWT against the public API base URL (`VITE_API_BASE_URL` on the frontend service). Unauthenticated calls return 401; route absence returns 404. Run authenticated checks from a logged-in browser session on `/comicos-intelligence` or via API client with production token.

**Empty payloads:** Latest endpoints return structured empty/readiness responses when snapshots have not been built yet (not HTTP errors).

## Phase 3 — Frontend surface

| Item | Value |
|------|--------|
| **Route** | `/comicos-intelligence` |
| **Page** | `apps/web/src/pages/ComicOSIntelligenceDashboardPage.tsx` |
| **Nav** | Primary → “ComicOS Intelligence” |
| **Mode** | Read-only `GET` aggregation; no build/mutate buttons in this phase |

Displays: P64 briefing, lane recommendations (BUY/HOLD/SELL/GRADE/ACQUIRE/WATCH), portfolio health, alerts, P63 portfolio/sell/acquire/signals, P62 buy queue / FOC / pull forecast / watchlists.

## Known gaps

- **Acquisition opportunities** on production may be `0` when want-list / catalog signals are thin (cert still passed).
- **P62 FOC / watchlists / pull forecast** may be empty until `POST .../platform/refresh` or scheduled jobs run (dashboard does not trigger builds).
- **Render blueprint** (`render.yaml`) documents static web only; API service must use `render_web_start.py` in the Render dashboard (see PRODUCTION_READINESS).
- **Public API host** is configured per-environment via `VITE_API_BASE_URL`; not embedded in this repo.

## Next steps

1. Confirm Render API service start command is `cd apps/api && python scripts/render_web_start.py` and `APP_ENV=production`.
2. Optionally add a post-deploy GitHub Action that runs `migrate-production` on release tags.
3. Wire scheduled P62/P63 platform refresh for production owners (worker/cron), then re-check dashboard freshness.
4. Add frontend tests for `ComicOSIntelligenceDashboardPage` (loading/error states) when snapshot fixtures exist in CI.
5. Extend dashboard with deep links to Top Recommendations and Today's Actions (read-only links only).

## Verification commands

```bash
cd apps/api
python -m pytest tests/test_intelligence_endpoints_smoke.py -q

cd apps/web
npm run build
```
