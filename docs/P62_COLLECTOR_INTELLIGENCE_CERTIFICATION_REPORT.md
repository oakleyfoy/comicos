# P62 Collector Intelligence Suite — Certification Report

**Run date (UTC):** 2026-06-03  
**Environment:** Local API (`apps/api`), SQLite test DB for pytest; optional PostgreSQL for `scripts/p62_collector_intelligence_certification.py`  
**Runner:** `python apps/api/scripts/p62_collector_intelligence_certification.py`  
**Out of scope:** Recommendation V3 production persistence (`P62_V3_PERSIST_ENABLED` remains **false**), V2 replacement, P63.

---

## Executive summary

| Gate | Result |
|------|--------|
| Pytest (FOC, pull forecast, auto watchlists, platform suite) | **PASS** (7/7) |
| P62-03 FOC certification (ordering, dates, generation) | **PASS** (with seeded FOC window) |
| P62-04 Pull forecast (confidence + explanations) | **PASS** |
| P62-05 Auto watchlists (build, refresh, inclusion reasons) | **PASS** |
| Platform bundle (`platform/certification`, `platform/refresh`) | **PASS** |
| Weekly automation hook (post P61 demand refresh) | **PASS** (pipeline step `collector_intelligence`) |

**Overall:** **CERTIFIED** for P62-03, P62-04, and P62-05 as an integrated collector guidance layer atop P61 + V3 preview + Buy Queue.

---

## 1. Automated tests

```text
pytest tests/test_foc_intelligence.py \
       tests/test_future_pull_forecasting.py \
       tests/test_auto_watchlists.py \
       tests/test_p62_collector_intelligence_suite.py -q
```

| Module | Tests | Result |
|--------|-------|--------|
| `test_foc_intelligence.py` | 2 | PASS |
| `test_future_pull_forecasting.py` | 2 | PASS |
| `test_auto_watchlists.py` | 2 | PASS |
| `test_p62_collector_intelligence_suite.py` | 1 | PASS |

**Total:** 7 passed (~101s).

---

## 2. Component certification (service layer)

Each component cert endpoint rebuilds data then validates invariants:

| Component | Checks | Feature flag |
|-----------|--------|----------------|
| **P62-03 FOC** | Alerts generated; `foc_date` present; urgency ordering | `P62_FOC_ENABLED` (default true) |
| **P62-04 Pull forecast** | Items generated; `HIGH`/`MEDIUM`/`LOW`; non-empty `explanation` | `P62_PULL_FORECAST_ENABLED` (default true) |
| **P62-05 Auto watchlists** | ≥1 watchlist type; `inclusion_reason` on items | `P62_AUTO_WATCHLIST_ENABLED` (default true) |

Platform readiness = all three `certified` flags true.

---

## 3. Weekly automation extension

After P61 `run_post_capture_pipeline` demand refresh and velocity (when `owner_user_id` is set):

1. Spec opportunities rebuild  
2. Velocity windows 7 / 14 / 28  
3. Buy queue rebuild  
4. FOC alert generation  
5. Pull forecast generation  
6. Auto watchlist refresh  
7. Platform certification bundle  

Implemented in `collector_intelligence_automation.run_collector_intelligence_pipeline`, invoked from `weekly_demand_automation_service.run_post_capture_pipeline`.

---

## 4. API surface (v1)

Base: `/api/v1/recommendation-intelligence`

| Area | Build / refresh | Read | Cert |
|------|-----------------|------|------|
| FOC | `POST /foc/build` | `GET /foc/alerts` | `GET /foc/certification` |
| Pull forecast | `POST /pull-forecast/build` | `GET /pull-forecast/latest` | `GET /pull-forecast/certification` |
| Auto watchlists | `POST /watchlists/auto/build`, `POST .../refresh` | `GET /watchlists/auto` | `GET /watchlists/auto/certification` |
| Platform | `POST /platform/refresh` | — | `GET /platform/certification` |

---

## 5. Persistence

| Migration | Tables |
|-----------|--------|
| `20260607_0222_add_p62_collector_intelligence_suite` | `foc_alert_*`, `future_pull_forecast_*`, `auto_watchlist_*` |

V2 cross-system and recommendation snapshots are **unchanged**.

---

## 6. Non-goals confirmed

- No V3 ranked snapshot persistence for production cutover  
- No replacement of V2 scoring or cross-system write path on GET  
- No P63 market intelligence modules  

---

## 7. Re-run instructions

```bash
cd apps/api
python -m pytest tests/test_foc_intelligence.py tests/test_future_pull_forecasting.py \
  tests/test_auto_watchlists.py tests/test_p62_collector_intelligence_suite.py -q
python scripts/p62_collector_intelligence_certification.py --owner-email <email>
```

Use `--skip-pytest` on the script when pytest was already executed in CI.
