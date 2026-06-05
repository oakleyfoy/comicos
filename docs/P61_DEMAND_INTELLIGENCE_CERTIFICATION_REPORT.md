# P61 Demand Intelligence — Certification Report

**Run date (UTC):** 2026-06-05  
**Environment:** Local API (`apps/api`) against configured `DATABASE_URL` (PostgreSQL)  
**Runner:** `python apps/api/scripts/p61_demand_intelligence_certification.py`  
**Recommendation V3:** Out of scope (consumer phase).

---

## Executive summary

| Gate | Result |
|------|--------|
| Pytest (P61 + P51 demand modules) | **PASS** (6/6) |
| Pipeline (refresh → velocity → spec → automation) | **PASS** |
| Persisted artifacts (snapshots, observations, velocity windows) | **PASS** |
| Service-layer certification (all four components + bundle) | **PASS** |
| HTTP certification APIs | **PASS** (200 on all routes; owner-scoped spec/bundle noted below) |

**Overall:** **CERTIFIED** for P61-01 through P61-04 on catalog owner **user id 36** (`live-lunar-5b175ec8@example.com`).

---

## 1. Automated tests

```text
pytest tests/test_demand_intelligence_platform.py \
       tests/test_market_demand_engine.py \
       tests/test_market_demand_seed.py -q
```

| Module | Tests | Result |
|--------|-------|--------|
| `test_demand_intelligence_platform.py` | 4 | PASS |
| `test_market_demand_engine.py` | 1 | PASS |
| `test_market_demand_seed.py` | 1 | PASS |

**Total:** 6 passed (~65s).

---

## 2. Pipeline execution

Steps run in order against the live database (Alembic at `20260605_0220`).

| Step | Action | Outcome |
|------|--------|---------|
| LoCG seed guard | Ensure ≥1 upcoming `external_catalog_issue` | Already present (no synthetic insert) |
| **P61-01** Demand refresh | `run_demand_refresh(scope=ALL, days_forward=90, trigger_type=CERTIFICATION)` | `SUCCESS`; run id **1**; **1736** issues refreshed; **267** entity profiles updated |
| **P61-02** Velocity compute | `compute_demand_velocity` for windows **7 / 14 / 28** | **5208** snapshot rows upserted (**1736** per window) |
| **P61-03** Spec build | `build_spec_opportunities(owner_user_id=36, limit=50)` | Snapshot id **1**; **50** ranked rows |
| **P61-04** Weekly automation | `discover_capture_schedule` + `run_post_capture_pipeline` for `2026-06-10` | Schedule **CERTIFIED**; post-capture refresh + velocity logged |

Second `demand_refresh_run` (id **2**) was created inside the weekly post-capture pipeline (`ISSUE_UPCOMING`, 14-day window).

---

## 3. Data verification

| Table / metric | Count | Expectation | Status |
|----------------|-------|-------------|--------|
| `issue_demand_snapshot` | 1736 | > 0 | OK |
| `issue_demand_observation` | 2116 | > 0 (append on refresh) | OK |
| `demand_velocity_snapshot` (total) | 5208 | > 0 | OK |
| Velocity window **7d** | 1736 | Populated | OK |
| Velocity window **14d** | 1736 | Populated | OK |
| Velocity window **28d** | 1736 | Populated | OK |
| `spec_opportunity_snapshot` | 1 | Owner-scoped header | OK |
| `spec_opportunity_row` | 50 | `row_count` on snapshot | OK |
| `weekly_demand_capture_schedule` | 6 | Discovered Wednesdays | OK |
| `weekly_demand_capture_event` | 3 | Pipeline audit steps | OK |
| Certified capture weeks | 1 | `status=CERTIFIED` | OK |

---

## 4. Certification (service layer)

Evaluated via `demand_intelligence_certification` for owner **36**.

| Component | Status | Certified | Notes |
|-----------|--------|-----------|-------|
| P61-01_REFRESH | PASS | yes | 1736 issue snapshots; latest successful refresh |
| P61-02_VELOCITY | PASS | yes | 5208 `demand_velocity_snapshot` rows |
| P61-03_SPEC | PASS | yes | Latest snapshot 50 rows |
| P61-04_AUTOMATION | PASS | yes | 6 schedule rows; 1 certified |
| **Platform bundle** | PASS | `platform_ready=true` | Refresh + velocity + spec certified |

---

## 5. Certification HTTP APIs

Authenticated smoke test (ephemeral user `p61-cert-runner-36@example.com`):

| Endpoint | HTTP | Service-equivalent |
|----------|------|-------------------|
| `GET /api/v1/demand/certification` | 200 | Global refresh — **certified** |
| `GET /api/v1/velocity/certification` | 200 | Global velocity — **certified** |
| `GET /api/v1/spec/certification` | 200 | Owner-scoped — **not certified** for ephemeral user (no owner snapshot) |
| `GET /api/v1/automation/certification` | 200 | Schedule — **certified** |
| `GET /api/v1/demand/platform/certification` | 200 | Bundle — **platform_ready false** for ephemeral user |

**Interpretation:** Spec and platform bundle endpoints key off **JWT `owner_user_id`**. Production sign-off should call them with the same owner used for `POST /api/v1/spec/build` (here: user **36**). Global components (refresh, velocity, automation) certify for any authenticated caller once pipeline data exists.

---

## 6. Reproduction

```bash
cd apps/api
alembic upgrade head
python -m pytest tests/test_demand_intelligence_platform.py \
  tests/test_market_demand_engine.py tests/test_market_demand_seed.py -q
python scripts/p61_demand_intelligence_certification.py \
  --owner-email live-lunar-5b175ec8@example.com
```

Optional: `--json-out` for machine-readable artifact (not required for PASS).

---

## 7. Follow-on (non-blocking)

- Wire owner JWT (or ops impersonation) into CI certification for `/spec/certification` and `/platform/certification` business flags.
- LoCG browser capture remains script-driven; API automation cert reflects **post-capture** pipeline status, not browser runtime.
- Recommendation V3 should consume persisted snapshots only (no refresh on GET).

---

## Sign-off

| Role | Result |
|------|--------|
| P61 Demand Intelligence Platform | **CERTIFIED** |
| Blocker for Recommendation V3 signal wiring | **None** (data layer ready) |
