# LoCG historical backfill plan (draft)

**Status:** Do not start until July 2026 forward validation is complete (including resolution of **2026-07-29**).

## Prerequisites

- [x] Internal certification rules (scroll discovery, variant parent stubs, proof row threshold ≥400)
- [x] Adaptive delay (`--adaptive-delay`)
- [ ] All target forward weeks PASS (July 8/15/22/29 — **07-29 pending**)

## Proposed backfill windows (newest first)

| Period | Suggested release Wednesdays | Est. runs | Notes |
|--------|------------------------------|-----------|--------|
| June 2026 | 2026-06-03, 10, 17, 24 | 4 | 06-24 proof PASS; 06-10/17 captured earlier |
| May 2026 | Weekly Wednesdays in May | ~4–5 | |
| April 2026 | Weekly Wednesdays in April | ~4–5 | |
| March 2026 | Weekly Wednesdays in March | ~4–5 | |
| Jan–Feb 2026 | Weekly Wednesdays Jan–Feb | ~8–9 | |

## Command template

```bash
python scripts/capture_locg_date_details_browser.py \
  --production --email ofoy@att.net \
  --date YYYY-MM-DD --headful --save-raw --adaptive-delay
```

## Operational estimates

- ~3–4 minutes per week × ~25–30 weeks ≈ **1.5–2 hours** wall clock (sequential headful).
- Run **one week at a time**; review `locg_capture_certification.json` before continuing.
- Weeks with initial DOM ≥400 rows may pass without scroll growth; weeks stuck at ~165–317 need scroll verification (see 07-29).

## Storage

- Raw HTML: `data/locg_browser_capture/<date>/`
- DB: `ExternalCatalogIssue` / `ExternalCatalogVariant` via production Postgres

## Rollout order (recommended)

1. Finish July 2026 forward (re-run or sign off 07-29).
2. June 2026 gaps (if any Wednesdays missing).
3. May → April → March → January–February 2026.

## Sign-off

- Product/ops: confirm 07-29 completeness vs LoCG live site.
- Engineering: mark `LOCG_PRODUCTION_CERTIFICATION.md` backfill section **approved to start**.
