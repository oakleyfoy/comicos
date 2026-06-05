# P62 Phase 2 — Buy Queue Intelligence

**Status:** Implemented.

**Replaces:** ephemeral `build_future_buy_queue` for persisted owner buy planning (read via P62 API; legacy dashboard may still call old helper until UI cutover).

---

## Models

| Table | Purpose |
|-------|---------|
| `buy_queue_snapshot` | Owner-scoped header (`snapshot_date`, `generated_at`, `total_items`, `metadata_json`) |
| `buy_queue_item` | Ranked row with V3/P61 scores, budget fields, `status` |

API exposes `owner_id`; database column is `owner_user_id`.

**Item statuses:** `NEW`, `WATCH`, `BUY`, `ORDERED`, `SKIPPED`.

---

## Scoring

`BuyQueueService` builds from forward **90-day** release window:

- **Recommendation score:** V3 preview component bundle (`recommendation_v3_components`)
- **Priority score:** blend of V3 preview, V2 cross-system priority (in-memory candidates only), demand, velocity, spec
- **User preference:** `RecommendationV2ScoringContext.market_user_fit`
- **Pull list:** boost when `PullList` / `PullListIssue` matches

Does **not** persist V3 or cross-system snapshots.

---

## Budget

Uses `PurchaseBudget` (`monthly_budget`, `weekly_budget`, `is_active`):

- Effective cap = `weekly_budget` if &gt; 0 else `monthly_budget`
- When cap exceeded, lower-priority rows demoted to `WATCH` with `budget_demoted` in `buy_reason`

---

## API

| Method | Path |
|--------|------|
| `GET` | `/api/v1/recommendation-intelligence/buy-queue` |
| `GET` | `/api/v1/recommendation-intelligence/buy-queue/latest` |
| `POST` | `/api/v1/recommendation-intelligence/buy-queue/build` |
| `PATCH` | `/api/v1/recommendation-intelligence/buy-queue/item/{id}` |
| `GET` | `/api/v1/recommendation-intelligence/buy-queue/certification` |

---

## Migration

`20260606_0221_add_p62_buy_queue_intelligence.py`

---

## Tests

`apps/api/tests/test_buy_queue_intelligence.py`
