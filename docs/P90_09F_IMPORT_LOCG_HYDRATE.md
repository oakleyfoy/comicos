# P90-09F — Import LOCG live hydration

## Problem

Import catalog resolution reads the local **`ExternalCatalogIssue`** mirror (LOCG sync / browser capture). Valid new releases can exist on [League of Comic Geeks](https://leagueofcomicgeeks.com) but be **missing from the mirror** (dev DB, lagging backfill, or a week never captured). Lines such as **Terminal #1**, **Shaolin Cowboy: Staying A.I. Live #1**, and **Vampyrates! #1** then fail matching even though LOCG has detail pages.

## Solution

When a line **does not match** the mirror and score is **below the accept threshold**, the API may run a **bounded live hydration fallback**:

1. Scan a **small set of LOCG release-calendar Wednesdays** (parsed release week, prior week, up to four future weeks—or a short “from today” window if no parsed date).
2. Find a list stub whose title + issue # aligns with the import line.
3. Fetch the issue detail page and **upsert** into `ExternalCatalogIssue` (same path as sync).
4. **Re-run** catalog matching for that line.

Implementation: `apps/api/app/services/import_locg_hydrate_service.py`, wired from `resolve_import_catalog_match` in `import_catalog_resolution_service.py`.

Multi-item import loads use a **request-scoped cache** (`import_locg_hydrate_request_scope` in `enrich_parse_order_payload_lifecycle`) so duplicate lines do not repeat LOCG fetches in one response.

## Environment flags

| Variable | Default | Meaning |
|----------|---------|---------|
| `IMPORT_LOCG_HYDRATE` | `1` (on) | Set to `0`, `false`, `no`, or `off` to disable live hydration entirely. |
| `IMPORT_LOCG_HYDRATE_TIMEOUT` | `45` | Max seconds per hydrate attempt (calendar + detail). |

**Tests:** `tests/conftest.py` sets `IMPORT_LOCG_HYDRATE=0` globally. Hydrate tests opt in with mocks and `IMPORT_LOCG_HYDRATE=1`.

## Default behavior (API)

- Hydration runs only when **all** are true:
  - Title and issue number present
  - Mirror match **failed** (`matched == false`)
  - Score **&lt; 70** (accept threshold)
  - `IMPORT_LOCG_HYDRATE` enabled
  - This title + issue + date window not already attempted in the **current request** (and optional short process cache)
- LOCG errors, timeouts, and parse failures are **logged and swallowed**; import resolution continues with the previous no-match result (no 500).
- On success, item metadata includes:
  - `catalog_match_hydrated`: `true`
  - `catalog_match_catalog_source`: `"LOCG_LIVE_HYDRATED"`
  - Diagnostics under `catalog_match_diagnostics` (`locg_hydrate_*` keys)

## Performance expectations

- One miss may cost **several HTTP requests** (1–6 calendar pages + 1 detail page), bounded by timeout.
- **Not** suitable as the primary catalog ingestion strategy at scale.
- Prefer **mirror backfill** so draft review stays fast and does not depend on LOCG uptime.

## Preferred production path: mirror backfill

Pre-fill the mirror for the release window you care about:

```bash
cd apps/api
python scripts/backfill_locg_calendar.py \
  --start-date 2026-06-01 \
  --end-date 2026-07-31
```

Optional flags (see script): `--production`, `--dry-run`, `--resume`, `--refresh-existing`, `--max-detail-pages`, `--delay-seconds`.

For weeks that need browser rendering or anti-bot handling:

```bash
cd apps/api
python scripts/capture_locg_date_details_browser.py \
  --date 2026-07-22 \
  --skip-crosswalk
```

See `python scripts/capture_locg_date_details_browser.py --help` for `--headful`, `--max-issues`, `--resume`, etc.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Still no match after hydrate | LOCG list title spelling vs import title; issue #; publisher autofill; logs for `import_locg_hydrate_no_match` / `hydrate_timeout`. |
| Slow import draft load | Many unmatched lines × live fetches; run calendar backfill or set `IMPORT_LOCG_HYDRATE=0` temporarily. |
| 500 on import page | Should not happen from hydrate; file a bug if stack trace points at hydrate (guard should log and continue). |
| QA: “where did this date come from?” | Look for `catalog_match_catalog_source: LOCG_LIVE_HYDRATED` or `locg_hydrated` in diagnostics. |

## Production caution

- Live hydration **calls LOCG over the internet** from the API process (rate limits, blocking, latency).
- Use hydration as a **safety net**; schedule **regular calendar sync/capture** for upcoming Wednesdays.
- Monitor logs: `import_locg_hydrate_success`, `import_locg_hydrate_timeout`, `import_locg_hydrate_calendar_fetch_failed`.
