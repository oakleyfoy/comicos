# LoCG historical backfill progress

One line per completed capture (newest queue entries appended below).

| Date | PASS/FAIL | Rows | Parents | Variants | Persisted | Runtime | Cloudflare | 429 | Notes |
|------|-----------|------|---------|----------|-----------|---------|------------|-----|-------|
| 2026-06-03 | PASS | 522 | 256 | 266 | 266 | 375.9s | 0 | 0 | pre-queue standalone |
| 2026-05-27 | PASS | 634 | 267 | 367 | 367 | 401.2s | 0 | 0 | runner subprocess; cert complete |
| 2026-05-20 | PASS | 666 | 268 | 398 | 398 | 403.7s | 0 | 0 | controlled queue |
| 2026-05-13 | PASS | 819 | 272 (DOM) | 547 (DOM) | 415 | 347.2s | 0 | 0 | queue parents 239/239, variants 415/415; dup DOM +33 parent / +132 variant; naive DOM gap was duplicates not missing capture (artifact diagnosis) |
