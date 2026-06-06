# P71 Production Review — Sell Intelligence Platform

**Review date:** 2026-06-06  
**Scope:** Certify existing P71 implementation for production readiness (defect fixes only; no new platform scope).  
**Reviewer:** GPT-assisted production review (ComicOS workspace).

## Executive summary

| Item | Result |
|------|--------|
| **Final status** | **CONDITIONAL** — ready after commit/deploy checklist below |
| **P71 targeted pytest** | **33 passed** (~5m 38s) |
| **Web build** | **Passed** (`npm run build` in `apps/web`) |
| **Alembic** | **At head** (`20260615_0230` applied locally) |
| **eBay credentials** | **Not required** for P71 |
| **GET routes mutate data** | **No** (verified in `test_p71_get_routes_do_not_mutate_snapshots`) |

P71 is a **read-only advisory layer**: snapshots and recommendations are append-only per owner. Inventory FMV is not overwritten when `P68_AUTO_OVERWRITE_INVENTORY_FMV` is false (certification check).

**Not approved for production on `origin/main` until** the P71 file set is committed, `main.py` router wiring ships, migration runs in production, and `Settings` includes P71 feature flags (see risks).

---

## Routes reviewed

Router: `attach_sell_intelligence_layer` → prefix `/api/v1/sell-intelligence` (`apps/api/app/api/sell_intelligence_api.py`).

| Method | Path | Auth | Mutates | Notes |
|--------|------|------|---------|--------|
| `POST` | `/platform/build` | Owner JWT | **Yes** | Builds all P71 snapshots; explicit operator action only |
| `GET` | `/platform/certification` | Owner JWT | No | Readiness checks; no inventory FMV writes |
| `GET` | `/exit-recommendations` | Owner JWT | No | 404 if no snapshot; 403 if flag disabled |
| `GET` | `/listing-intelligence` | Owner JWT | No | Listing guidance from latest snapshot |
| `GET` | `/liquidity` | Owner JWT | No | Liquidity bands / days-to-sell |
| `GET` | `/exit-queue` | Owner JWT | No | Priority-ordered queue |
| `GET` | `/dashboard` | Owner JWT | No | Investor sell dashboard cards |

**Owner scoping:** All routes use `get_current_user`; snapshots and items are keyed by `owner_user_id`. Cross-owner access returns empty/404 (see `test_p71_owner_isolation`).

**Pagination / limits:** List endpoints read persisted snapshot rows with service-level limits (e.g. exit recommendations `limit=200`, exit queue `limit=100`). Platform list API does not accept client page params; UI slices client-side.

**Empty states:** Empty inventory still completes `POST /platform/build` with zero-item snapshots; GET returns 200 with empty `items` where applicable. Missing snapshot → **404** with stable error codes (`NO_EXIT_RECOMMENDATION_SNAPSHOT`, etc.).

---

## Files reviewed

### Backend (P71)

- `apps/api/app/api/sell_intelligence_api.py` — HTTP surface
- `apps/api/app/services/p71_platform_service.py` — build orchestration
- `apps/api/app/services/p71_sell_context.py` — read-only P67/P68 context
- `apps/api/app/services/p71_sell_scoring.py` — deterministic exit/listing/liquidity scoring
- `apps/api/app/services/exit_recommendation_service.py` — P71-01
- `apps/api/app/services/listing_intelligence_service.py` — P71-02
- `apps/api/app/services/liquidity_intelligence_service.py` — P71-03
- `apps/api/app/services/exit_queue_service.py` — P71-04
- `apps/api/app/services/investor_sell_dashboard_service.py` — P71-05
- `apps/api/app/services/p71_certification_service.py`, `p71_feature_flags.py`
- `apps/api/app/models/sell_intelligence_platform.py`
- `apps/api/app/schemas/sell_intelligence.py`
- `apps/api/alembic/versions/20260615_0230_add_p71_sell_intelligence.py`
- `apps/api/app/main.py` — `attach_sell_intelligence_layer(app)` (local change)
- `apps/api/app/models/__init__.py` — P71 model exports (staged from stash)

### Frontend

- `apps/web/src/pages/SellIntelligencePage.tsx` — **loads GET snapshots only**; `POST /platform/build` on explicit “Build snapshots” (no page-load rebuild)
- `apps/web/src/api/p71SellIntelligence.ts` — optional GET helpers treat **404 as empty**
- `apps/web/src/App.tsx`, `apps/web/src/config/appNavigation.ts` — route/nav (local)

### Tests

- `tests/test_p71_production_review.py`
- `tests/test_p71_sell_intelligence_platform.py`
- `tests/test_exit_recommendations.py`, `tests/test_exit_queue.py`, `tests/test_liquidity_intelligence.py`, `tests/test_sell_dashboard.py`
- Legacy exit stack tests (`test_exit_certification.py`, `test_exit_dashboard.py`, `test_exit_candidate.py`) — run with P71 batch; still pass

### Docs (platform)

- `docs/P71_SELL_INTELLIGENCE_PLATFORM.md` and phase docs P71-01–05

---

## Logic validation

### Exit recommendations (`p71_sell_scoring.score_exit`)

Actions: `SELL_NOW`, `HOLD`, `WATCH`, `TRIM_POSITION`, `GRADE_THEN_SELL`.

- Deterministic numeric rules on gain %, liquidity, portfolio share, quantity, trend, FMV confidence
- Stable ordering for list views: `exit_score` desc, `id` asc
- Weak pricing: copies with no FMV and no cost basis skipped at build time; scoring tolerates missing FMV via hold/low-score paths
- Unit coverage in `test_p71_scoring_actions_are_deterministic`

### Listing intelligence (`score_listing`)

- BIN, auction start, sale low/high, expected profit/ROI, days-to-sell, channel recommendation
- Uses `SellIntelCopyContext` fed by P68 snapshots / title FMV bridge / internal ledger (read-only)
- `estimated_fmv <= 0` → null prices, safe factors (`fmv_missing`)

### Liquidity (`score_liquidity`)

- Bounded `days_to_sell` (5–150); handles zero sales, low confidence, no comps via low band defaults
- No live eBay requirement

### Exit queue

- Ranks exit items by score; skips `HOLD`; priority ascending
- `test_p71_exit_queue_priority_ordering`

---

## Test results

Commands run during review:

```text
pytest tests/test_p71_production_review.py tests/test_p71_sell_intelligence_platform.py \
  tests/test_exit_queue.py tests/test_exit_recommendations.py \
  tests/test_exit_certification.py tests/test_exit_dashboard.py tests/test_exit_candidate.py \
  tests/test_liquidity_intelligence.py tests/test_sell_dashboard.py -v
→ 33 passed in ~338s

npm run build  (apps/web) → passed
alembic upgrade head  (apps/api) → at head
```

**Full suite** `pytest tests/` was started but **did not complete** (interrupted ~8%). Unrelated early failures observed elsewhere: agent platform routes **404** (`test_agent_analytics`, `test_agent_dashboard`, `test_agent_platform`, `test_agent_registry`). Those are **out of P71 scope** but block a whole-repo green run.

---

## Defects found and fixes applied (local)

| Defect | Fix |
|--------|-----|
| P71 router not mounted on `main.py` | Added `attach_sell_intelligence_layer` import + call |
| Sell Intelligence UI called `POST /platform/build` on every page load | Page loads GET only; build is explicit button |
| GET 404 treated as hard failure in UI | `requestP71Optional` + empty state |
| `models/__init__.py` missing P71 exports | Restored from `stash@{0}` (staged) |

---

## Known limitations

- **No live eBay** listing or sold-data ingest in P71; uses P68 snapshots, internal sales, CSV comps (P69), manual/stub FMV where present
- **No auto-listing** or inventory deletion; recommendations only
- **Snapshots required** before GET dashboards show data; first-time users must run build once (or ops job)
- **GET returns 404** without snapshot (not an empty envelope); frontend handles as empty
- **Legacy exit stack** (P36-style exit certification/dashboard) coexists; P71 is a separate snapshot model
- **P69 CSV import** is adjacent tooling; not required for P71 certification path

---

## Production risks

| Risk | Mitigation |
|------|------------|
| P71 code not on `origin/main` | Commit and deploy listed files + migration |
| **`Settings` missing `p71_*` flags** on current `main` (flags lived in stashed `config.py`) | Add five `p71_*_enabled` fields (default `True`) before deploy or restore from stash |
| Accidental page-load rebuild | Fixed in `SellIntelligencePage`; verify after deploy |
| Large snapshot build on shared DB | Keep build as explicit POST; do not hook to other dashboards |
| `models/__init__.py` only partially staged | Ensure full P71 commit includes all imports |
| Full pytest not green | Triage agent 404 tests separately |

---

## Deploy checklist

1. Apply migration `20260615_0230` on production Postgres  
2. Ship `main.py` P71 attach + all P71 backend/frontend/tests  
3. Add P71 feature flags to `apps/api/app/core/config.py`  
4. Run targeted P71 pytest + `npm run build` on CI  
5. Smoke: login → `/sell-intelligence` → empty state → “Build snapshots” → sections populate  
6. Confirm `GET` routes do not increase snapshot row counts without `POST /platform/build`

---

## Pass / fail criteria (this review)

| Criterion | Met? |
|-----------|------|
| P71 targeted pytest passes | Yes |
| `npm run build` passes | Yes |
| `alembic upgrade head` passes | Yes (local) |
| P71 dashboard loads without auto-rebuild | Yes (local UI) |
| P71 GET routes do not mutate data | Yes |
| No eBay credential dependency | Yes |
| Full `pytest tests/` | **No** (incomplete / other failures) |
| Shipped on production `main` | **No** (pending commit) |

**Verdict:** **CONDITIONAL APPROVAL** — approve for production **after** commit, config flags, migration, and deploy smoke above. Not **APPROVED_FOR_PRODUCTION** on remote until then.
