# P74-01 Release Intelligence Monitoring

## Purpose

Monitor upcoming comic releases and catalog changes without purchase quantities, FOC scoring, or recommendation engine changes.

## Architecture

```
Release import feed (P50)
        ↓
release_change_detector (before/after diff)
        ↓
p74_release_change_record + p74_release_event_history
        ↓
release_monitoring_service (windows, dashboard, watchlist activity)
        ↓
p74_* snapshots (foundation analytics)
```

## Data sources

- `release_series`, `release_issue`, `release_variant` (owner-scoped release intelligence)
- `release_watchlist` / `release_watchlist_item` (P50-02)
- Optional `release_key_signal` for discovery highlights

## Change detection rules

| Change type | Trigger |
|-------------|---------|
| NEW_ISSUE | First import of an issue row |
| NEW_VARIANT | New variant row on import |
| RELEASE_DATE_CHANGE | `release_date` differs before/after update |
| PUBLISHER_CHANGE | Publisher on series snapshot differs |
| COVER_CHANGE | Title or cover price change |
| METADATA_CHANGE | FOC, status, or issue number change |
| REMOVED / RESTORED | Reserved for full-catalog sync (future) |

## Event definitions

- `DISCOVERED` — new issue seen
- `UPDATED` — issue metadata changed
- `VARIANT_ADDED` — new variant
- `RELEASE_DATE_CHANGED` — date shift
- `REMOVED` / `RESTORED` — catalog membership

## APIs

| Method | Path |
|--------|------|
| GET | `/api/v1/release-monitoring/upcoming` |
| GET | `/api/v1/release-monitoring/changes` |
| GET | `/api/v1/release-monitoring/history` |
| GET | `/api/v1/release-monitoring/watchlist` |
| GET | `/api/v1/release-monitoring/dashboard` |

## Known limitations

- Removals are not inferred from partial feeds unless a full sync is added later.
- Watchlist matching uses simple string/publisher rules on titles and series names.
- No purchase or FOC quantity recommendations (P74-02).

## Verification

```bash
pytest tests/test_release_monitoring.py -v
pytest tests/test_release_change_detection.py -v
pytest tests/test_release_history.py -v
pytest tests/test_release_watchlist.py -v
pytest tests/test_release_dashboard.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
