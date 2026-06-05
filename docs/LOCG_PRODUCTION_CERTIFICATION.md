# LoCG browser capture — production certification

Internal certification uses `locg_capture_certification.json` (not distributor spreadsheets).

## Proof runs (certified)

| Week | Certification | Notes |
|------|---------------|--------|
| 2026-06-24 | PASS | Scroll discovery; 404/404 variants |
| 2026-07-01 | PASS | Adaptive delay; 336/336 variants |

## July 2026 forward — certified

All forward weeks **PASS** (see `LOCG_JULY_2026_CAPTURE_VALIDATION.md`), including **2026-07-29** as a lighter week (completeness signals, not 400-row floor).

## July 2026 forward validation

See `LOCG_JULY_2026_CAPTURE_VALIDATION.md`.

**Status:** July 2026 forward weeks **2026-07-01, 07-08, 07-15, 07-22, 07-29** PASS (07-29 certified as lighter week via completeness signals, not fixed 400-row floor).

## Production certified (browser capture)

Certified when internal `locg_capture_certification.json` passes with scroll discovery, variant persistence, and proof row count ≥400 (or documented exception).

- 2026-06-24, 2026-07-01, 2026-07-08, 2026-07-15, 2026-07-22
- 2026-07-29 (lighter week, 98 parents / 317 li rows)

## Command (production)

```bash
cd apps/api
export DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5433/comic_os
python scripts/capture_locg_date_details_browser.py \
  --production --email ofoy@att.net \
  --date YYYY-MM-DD --headful --save-raw --adaptive-delay --skip-crosswalk
```

Crosswalk is **skipped by default**. Use `--run-crosswalk` only when you need a full owner-wide `rebuild_external_catalog_crosswalk` in the same session (slow on large catalogs).

## Historical backfill

Planned months are listed in `LOCG_HISTORICAL_BACKFILL_PLAN.md` after July forward weeks pass. **Do not start backfill until approved.**
