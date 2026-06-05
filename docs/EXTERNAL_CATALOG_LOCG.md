# External catalog — League of Comic Geeks (LoCG)

## Purpose: external intelligence for the Recommendation Decision Engine

LoCG is **not** a simple release calendar scraper. Ingest exists so ComicOS can decide **BUY / WATCH / PASS**, **how many copies**, **which cover**, and **why it matters**—the same outcomes as the Recommendation Decision Engine (RDE).

```
LoCG ingest → external_catalog_* + decision_signals_json
                    ↓
         crosswalk → ReleaseIssue (Lunar spine, unchanged)
                    ↓
         [future phase] RDE merges inventory + spec + LoCG signals
```

Signal mapping contract: **`docs/EXTERNAL_CATALOG_RDE_SIGNAL_MAP.md`**

Code: `app/services/external_catalog/decision_signals.py`

**This phase:** build and store RDE-oriented `decision_signals_json` at normalize/sync. **Does not** alter ranking weights or `compute_recommendation_decision()` yet.

## Tables

- `external_catalog_source` — registered sources (LoCG seeded on first sync)
- `external_catalog_issue` — issue intelligence + `importance_signals_json` + `decision_signals_json`
- `external_catalog_variant` / `external_catalog_creator` — child rows
- `external_catalog_sync_run` — backfill / incremental / refresh audit
- `external_catalog_match` — per-owner crosswalk to `release_issue` (or missing)

## Workflows

### One-time backfill

```powershell
cd apps/api
python scripts/backfill_locg_calendar.py --start-date 2026-06-10 --through-farthest-available
python scripts/backfill_locg_calendar.py --production --start-date 2026-06-10 --end-date 2026-06-17 --max-detail-pages 500 --resume
```

Options: `--dry-run`, `--refresh-existing`, `--delay-seconds` (default 1.5), `--max-detail-pages` (default 500).

### Weekly incremental

```powershell
python scripts/sync_locg_new_weeks.py --production
```

Only discovers release calendar dates **after** the max `release_date` already stored for LoCG; does not re-scrape entire history.

### Upcoming signal refresh (90-day window)

```powershell
python scripts/refresh_locg_upcoming_signals.py --production --days-forward 90
python scripts/refresh_locg_upcoming_signals.py --production --refresh-details
```

Updates demand (pull/want), dates, descriptions, and recomputes `decision_signals_json` on refresh via normalize path.

### Coverage / missing-from-Lunar report

```powershell
python scripts/report_external_catalog_coverage.py --production --email you@example.com
```

## Rich metadata for importance (BUY / WATCH / PASS)

LoCG ingest captures issue, creator, variant, and **importance-detection** fields so ComicOS can reason about copies and covers without changing recommendation scoring in this phase.

### Issue-level
Title, publisher, series, issue number, release/FOC/cover dates, price, solicitation (`description`), `story_summary`, `product_url`, pull/want/variant counts, cover/thumbnail/high-res URLs, `imprint`, `universe`, plus `importance_signals_json` and **`decision_signals_json`**.

### Creators
One row per credit with `creator_name`, `role_display` (exact LoCG label), and normalized `role` bucket (WRITER, ARTIST, COVER_ARTIST, COLORIST, LETTERER, EDITOR, …).

### Variants
`cover_label`, `variant_name`, `artist`, `ratio_value` (from `1:25` / `1:50` text), `price`, `image_url`, `variant_detail_url`.

## Cover image URLs (required metadata)

Each `external_catalog_issue` stores **URL references only** during backfill and refresh:

| Field | Purpose |
|-------|---------|
| `cover_image_url` | Primary cover art URL (required when LoCG exposes any art) |
| `thumbnail_url` | Smaller listing/thumb URL when available |
| `high_resolution_image_url` | Full-size art URL when available |

No image bytes are downloaded during backfill (see **External Catalog Image Cache** future phase).

## Crosswalk

`POST /api/v1/external-catalog/crosswalk/rebuild` (authenticated) or the report script rebuilds matches:

| Status | Meaning |
|--------|---------|
| `MATCHED_RELEASE_ISSUE` | Confident match to owner `ReleaseIssue` |
| `MISSING_FROM_LUNAR` | Upcoming in horizon, no release row |
| `POSSIBLE_DUPLICATE` | Multiple external rows map to one release |
| `NEEDS_REVIEW` | Weak or out-of-horizon match |

No automatic promotion into `ReleaseIssue`.

## API (read-mostly)

- `GET /api/v1/external-catalog/issues`
- `GET /api/v1/external-catalog/issues/{id}`
- `GET /api/v1/external-catalog/issues/{id}/decision-signals`
- `GET /api/v1/external-catalog/missing-from-lunar` (owner-scoped)
- `GET /api/v1/external-catalog/sync-runs`
- `POST /api/v1/external-catalog/crosswalk/rebuild`

Sync/backfill remain **script-only** in V1.

## Rate limits and legal caution

- Sequential requests only (no parallel scrape in V1)
- Default **1.5s** delay between HTTP calls
- Retries with backoff; graceful stop on 401/403/429
- Identify with `ComicOS-ExternalCatalog/1.0` user agent
- Respect LoCG terms; licensed API is the long-term alternative (`docs/TECH_DEBT.md` P51)

## Future: RDE merge + image cache

1. **RDE integration** — merge `decision_signals_json` with inventory, spec, and Lunar rows inside `compute_recommendation_decision()`.
2. **External Catalog Image Cache** — download, thumbnail, dedupe after metadata ingest.
