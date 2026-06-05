# P62 Phase 5 — Auto Watchlists

**Status:** Implemented (P62-05).

**Purpose:** Build dynamic, explainable watchlists from demand, spec, FOC window, franchise, and affinity signals.

---

## Models

| Table | Purpose |
|-------|---------|
| `auto_watchlist` | Typed list header (`watchlist_type`, `item_count`, `generated_at`) |
| `auto_watchlist_item` | Entry with `title`, optional `release_issue_id`, `inclusion_reason` |

**Watchlist types:**

- `AUTO_DEMAND_RISING`
- `AUTO_SPEC_TOP`
- `AUTO_FOC_THIS_WEEK`
- `AUTO_FOC_NEXT_30_DAYS`
- `AUTO_BATMAN`
- `AUTO_SPIDER_MAN`
- `AUTO_IMAGE`
- `AUTO_INDIE_BREAKOUT`
- `AUTO_CREATOR_FOLLOWING`
- `AUTO_PUBLISHER_FOLLOWING`

---

## Service

`AutoWatchlistService`:

- `build_auto_watchlists` — create typed lists for owner
- `refresh_auto_watchlists` — rebuild and drop stale entries
- Each item includes a human-readable `inclusion_reason`

---

## API

| Method | Path |
|--------|------|
| `GET` | `/api/v1/recommendation-intelligence/watchlists/auto` |
| `POST` | `/api/v1/recommendation-intelligence/watchlists/auto/build` |
| `POST` | `/api/v1/recommendation-intelligence/watchlists/auto/refresh` |
| `GET` | `/api/v1/recommendation-intelligence/watchlists/auto/certification` |

**Feature flag:** `P62_AUTO_WATCHLIST_ENABLED` (default **true**).

---

## Migration

`20260607_0222_add_p62_collector_intelligence_suite.py`

---

## Tests

`apps/api/tests/test_auto_watchlists.py`
