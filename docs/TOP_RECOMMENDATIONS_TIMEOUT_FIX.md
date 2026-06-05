# Top Recommendations production timeout fix

## Root cause

`GET /api/v1/cross-system-recommendations/summary` called `generate_cross_system_recommendations` on every page load. On production owner `1`, unified/daily candidate reads alone exceeded **5+ minutes**, exceeding Render HTTP timeouts. The Top Recommendations page used `Promise.all` for list + summary, so one slow/failed call blocked the entire UI.

## Fix

### GET (read-only)

- `GET /api/v1/cross-system-recommendations` — latest persisted snapshot only (`scan_limit` 200).
- `GET /api/v1/cross-system-recommendations/latest` — same read path.
- `GET /api/v1/cross-system-recommendations/summary` — summary from latest snapshot only; **no** `generate_cross_system_recommendations`.
- Empty snapshot → **200** with `readiness_status: NOT_READY` and `readiness_reason` (not 500).
- List GET builds decision payloads **only for the current page** after filter/sort/slice.

### POST (refresh)

- `POST /api/v1/cross-system-recommendations/rebuild` — **only** public API route that runs `generate_cross_system_recommendations` (with `refresh_upstream=True`).
- Frontend **Refresh rankings** button calls POST rebuild, then reloads read-only GETs.
- **Reload** re-fetches GET list + summary without rebuild.

### Frontend

- List and summary errors are isolated; list can render when summary fails.

## Rules

| Method | Behavior |
|--------|----------|
| GET cross-system list/summary/latest | Read persisted snapshot; bounded work |
| POST cross-system-recommendations/rebuild | Full pipeline generate |

Scoring logic unchanged. No automatic production rebuild on deploy or page load.

See also: [RENDER_MEMORY_INVESTIGATION_POST_INTELLIGENCE_DEPLOY.md](RENDER_MEMORY_INVESTIGATION_POST_INTELLIGENCE_DEPLOY.md).
