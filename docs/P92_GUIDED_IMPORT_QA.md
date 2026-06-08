# P92 guided import QA

## Flow

1. Open `/imports/guided` (also linked from home checklist).
2. Paste order text → processing shows user-friendly steps (no parser jargon).
3. Review step shows auto-match count collapsed; exceptions expanded.
4. Summary → **Add to inventory** → success panel with next actions.

## APIs

- `GET /imports/parse-jobs/{job_id}/guided-progress`
- `GET /imports/{import_id}/guided-review`
- `GET /imports/{import_id}/guided-summary`
- Confirm still uses `POST /imports/{import_id}/confirm` (records `p92_import_health_event`).

## P91-04 checklist

- Recommendations task: `POST /api/v1/collector-profile/recommendations/mark-viewed` on recommendations page load.
- Review imports: incomplete until `has_any_import`; complete when imports exist and no draft pending.
- Setup status includes `percent_complete`.

## Limitations

- Exception actions deep-link to legacy `/orders/import` for catalog fixes (full inline search TBD).
- PDF/screenshot upload UI is placeholder; Gmail uses `/imports/email`.
- Health metrics stored as events; no ops dashboard yet.
