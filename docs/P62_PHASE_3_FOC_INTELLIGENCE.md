# P62 Phase 3 — FOC Intelligence

**Status:** Implemented (P62-03).

**Purpose:** Surface books that need action before Final Order Cutoff, ranked by V3 preview score, P61 demand/velocity/spec, and owner preference.

---

## Models

| Table | Purpose |
|-------|---------|
| `foc_alert_snapshot` | Owner header (`snapshot_date`, `total_items`, `generated_at`) |
| `foc_alert_item` | Per-issue alert with scores, `alert_reason`, `suggested_quantity`, `status` |

API field `owner_id` maps to `owner_user_id`.

**Statuses:** `NEW`, `REVIEWED`, `ORDERED`, `DISMISSED`.

---

## Scoring

`FOCIntelligenceService` (`foc_intelligence_service.py`):

- Window: FOC dates from today through **30 days**
- **Urgency:** blend of recommendation, demand, velocity, spec, preference, and days-to-FOC
- Boost when velocity trend is **RISING** or spec/demand/V3 thresholds are met
- Items sorted by `urgency_score` descending

Does not replace V2 cross-system persistence or enable V3 production persist.

---

## API

| Method | Path |
|--------|------|
| `GET` | `/api/v1/recommendation-intelligence/foc/alerts` |
| `POST` | `/api/v1/recommendation-intelligence/foc/build` |
| `GET` | `/api/v1/recommendation-intelligence/foc/certification` |

**Feature flag:** `P62_FOC_ENABLED` (default **true**).

---

## Migration

`20260607_0222_add_p62_collector_intelligence_suite.py`

---

## Tests

`apps/api/tests/test_foc_intelligence.py`
