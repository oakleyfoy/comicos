# LoCG remediation task — partial June 2026 weeks

**Status:** Open (not urgent)  
**Blocks:** Declaring the LoCG ingestion platform permanently complete for Jan–Aug 2026.

## Scope

Recapture these Wednesday release weeks with **current queue-v1** certification (`LoCG-Certified-v1` / deduped queue counts):

| Week | Why |
|------|-----|
| **2026-06-10** | Legacy artifact `passed: true` but only **45** parent details vs **75** DOM parents. |
| **2026-06-17** | Legacy artifact `passed: true` but only **47** parent details vs **85** DOM parents. |

## Command (one date per run)

From `apps/api`, with production DB and headful browser as usual:

```bash
python scripts/capture_locg_date_details_browser.py --production --email ofoy@att.net --date <YYYY-MM-DD> --headful --save-raw --adaptive-delay
```

Run **2026-06-10** first, then **2026-06-17**. Do not batch other weeks in the same session unless explicitly requested.

## Verification (each week)

Read `data/locg_browser_capture/<date>/locg_capture_certification.json` and confirm:

1. **`passed: true`** with **queue v1 fields** present (`final_parent_issue_queue_count`, `final_variant_queue_count`, `proof_run_assessment.parent_queue_coverage_passed` / `variant_queue_coverage_passed`).
2. **Parent queue coverage:** `detail_pages_succeeded == final_parent_issue_queue_count` (and attempted matches queue).
3. **Variant queue coverage:** `list_variants_persisted == final_variant_queue_count` (and found matches queue).
4. **No duplicate-inflated pass:** if `duplicate_parent_li_rows` or `duplicate_variant_li_rows` > 0, cert must still require queue equality (warnings OK; DOM row counts must not substitute for queue counts).
5. **`skipped_missing_parent` == 0** and **`variant_upsert_failure` == 0** unless documented unavoidable cases.
6. **Shell:** prefer clean **exit 0**; if post-cert stall occurs, artifact PASS still governs.

**Stop** on cert fail, persist gaps, 429/Cloudflare escalation, or parent succeeded &lt; queue count.

## After both weeks pass

1. Regenerate cumulative report:  
   `python scripts/generate_locg_2026_backfill_certification_report.py`
2. Confirm the report no longer lists **2026-06-10** / **2026-06-17** under *Legacy / incomplete captures*.
3. Reconcile executive totals (parent/variant sums, queue-v1 week count) if numbers changed.
4. Optionally append one line per week to `docs/LOCG_BACKFILL_PROGRESS.md`.

## Done when

- Both dates have queue-v1 PASS artifacts with full parent/variant queue coverage.
- Cumulative certification report reflects the new artifacts.
- Platform sign-off can proceed for Jan–Aug 2026 (subject to any separate legacy-schema review for May–Aug weeks without queue fields).
