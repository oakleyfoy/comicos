# LoCG remediation task — partial June 2026 weeks

**Status:** Complete (2026-06-05)  
**Outcome:** Both weeks recaptured with queue-v1 PASS artifacts.

## Scope (resolved)

| Week | Prior issue | Current artifact |
|------|-------------|------------------|
| **2026-06-10** | Legacy partial capture (45 parents) | queue-v1 **218/218** parents, **476/476** variants |
| **2026-06-17** | Legacy partial capture (47 parents) | queue-v1 **147/147** parents, **331/331** variants (dup DOM warning only) |

## Command (one date per run)

From `apps/api`, with production DB and headful browser as usual:

```bash
python scripts/capture_locg_date_details_browser.py --production --email ofoy@att.net --date <YYYY-MM-DD> --headful --save-raw --adaptive-delay --skip-crosswalk
```

## Verification checklist (both weeks satisfied)

- `passed: true` with queue v1 fields and `parent_queue_coverage_passed` / `variant_queue_coverage_passed`
- Parent and variant queue equality with persistence counts
- `skipped_missing_parent` == 0, `variant_upsert_failure` == 0

Artifacts: `data/locg_browser_capture/2026-06-10/` and `.../2026-06-17/locg_capture_certification.json`.

Cumulative report: `docs/LOCG_2026_BACKFILL_CERTIFICATION_REPORT.md` (regenerate via `generate_locg_2026_backfill_certification_report.py`).
