# LoCG browser capture — production certification

Internal certification uses `locg_capture_certification.json` (not distributor spreadsheets).

## Proof runs (certified)

| Week | Certification | Notes |
|------|---------------|--------|
| 2026-06-24 | PASS | Scroll discovery; 404/404 variants |
| 2026-07-01 | PASS | Adaptive delay; 336/336 variants |

## July 2026 forward validation

See `LOCG_JULY_2026_CAPTURE_VALIDATION.md`.

**Status (2026-06-05):** 2026-07-08, 07-15, 07-22 **PASS**; **2026-07-29 FAIL** (317 rows, below proof threshold 400). Production certified for pipeline use; full July forward gate **open** until 07-29 resolved.

## Production certified (browser capture)

Certified when internal `locg_capture_certification.json` passes with scroll discovery, variant persistence, and proof row count ≥400 (or documented exception).

- 2026-06-24, 2026-07-01, 2026-07-08, 2026-07-15, 2026-07-22
- Pending: 2026-07-29

## Command (production)

```bash
cd apps/api
export DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5433/comic_os
python scripts/capture_locg_date_details_browser.py \
  --production --email ofoy@att.net \
  --date YYYY-MM-DD --headful --save-raw --adaptive-delay
```

## Historical backfill

Planned months are listed in `LOCG_HISTORICAL_BACKFILL_PLAN.md` after July forward weeks pass. **Do not start backfill until approved.**
