# P62 Phase 4 — Future Pull Forecasting

**Status:** Implemented (P62-04).

**Purpose:** Predict series and issues the owner is likely to add to pulls or buy queue, with confidence and plain-language explanations.

---

## Models

| Table | Purpose |
|-------|---------|
| `future_pull_forecast` | Owner forecast header (`total_items`, `generated_at`) |
| `future_pull_forecast_item` | Row with `series_name`, `title`, `confidence`, `explanation`, `reasons_json` |

**Confidence:** `HIGH`, `MEDIUM`, `LOW`.

**Reason codes (examples):** ongoing run, creator following, franchise following, publisher following, demand trend, similar ownership, pull-list affinity, buy-queue history.

---

## Inputs

`FuturePullForecastService` uses:

- Active `PullList` rows
- Recent `BuyQueueItem` history
- Forward `ReleaseIssue` horizon
- P61 demand/velocity context where available

---

## API

| Method | Path |
|--------|------|
| `GET` | `/api/v1/recommendation-intelligence/pull-forecast/latest` |
| `POST` | `/api/v1/recommendation-intelligence/pull-forecast/build` |
| `GET` | `/api/v1/recommendation-intelligence/pull-forecast/certification` |

**Feature flag:** `P62_PULL_FORECAST_ENABLED` (default **true**).

---

## Migration

`20260607_0222_add_p62_collector_intelligence_suite.py`

---

## Tests

`apps/api/tests/test_future_pull_forecasting.py`
