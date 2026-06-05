# P66 Phase 6 — Printing Intelligence (P66-06)

## Goal

Separate first prints from reprints, facsimiles, and anniversary reissues so distributor reorder dates cannot overwrite retail first-print metadata.

## Backend

| Piece | Location |
|-------|----------|
| Detection & merge rules | `app/services/printing_intelligence.py` |
| Lunar import split | `app/services/lunar_release_normalizer.py` |
| Issue date guard | `app/services/lunar_issue_resolution.py`, `app/services/release_import.py` |
| LoCG crosswalk stamp | `app/services/external_catalog/crosswalk.py` |
| Decision API fields | `app/schemas/recommendation_decision.py`, `recommendation_decision_engine.py` |
| Migration | `20260612_0227_add_printing_intelligence.py` |

### Data model

- **`release_issue`:** `original_foc_date`, `original_release_date` (preserved first-print schedule; `foc_date` / `release_date` track the same after merge).
- **`release_variant`:** `printing_number`, `printing_kind`, `printing_foc_date`, `printing_release_date`.

### Kinds

- `FIRST_PRINT`, `REPRINT` (2nd–Nth), `FACSIMILE`, `ANNIVERSARY_REISSUE`.

## Frontend

- `PrintingBadge` component — shown on recommendation decision panel and cross-system / daily action titles.
- `formatCalendarDate` — local calendar parsing for date-only API values.

## Tests

`apps/api/tests/test_printing_intelligence.py` (parsing, Lunar normalizer, reprint import guard).
