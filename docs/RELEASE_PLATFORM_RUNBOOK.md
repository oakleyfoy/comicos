# Release Platform Runbook (P50)

Operational guide for the ComicOS Release Intelligence Platform (P50-01 through P50-05). Certification and validation are on-demand; they do not trigger imports or rescoring.

## Lunar import lifecycle

1. Configure `LUNAR_USERNAME` / `LUNAR_PASSWORD` (or settings equivalents).
2. Run a manual import via `/lunar-feed` or wait for the scheduler when enabled.
3. Confirm `lunar_feed_run.status = COMPLETED` and stable issue/variant counts on re-import.
4. **Troubleshooting:** Zero variants after import may require variant repair (legacy flat rows) — use documented repair endpoints; closeout does not run repair automatically.

## Scheduler lifecycle

1. Enable owner scheduler config (`lunar_schedule_config.enabled = true`).
2. Monitor `lunar_scheduled_run` for COMPLETED vs FAILED.
3. Certification WARNING when scheduler disabled is acceptable if manual imports are intentional.

## Signal and opportunity lifecycle

1. Refresh signals via release intelligence agent runs (new #1, milestone, variant agents).
2. Review `/release-platform` horizons and opportunities — engines recompute from current catalog and signals.
3. Spec recommendations require spec scoring then recommendation agent runs (or historical rows).

## Validation lifecycle

1. Open `/release-platform-certification` or GET `/api/v1/release-platform/validation`.
2. Resolve any FAIL checks before production signoff (duplicate canonical issues, zero variants with issues present, no completed imports when imports are required).
3. WARNING checks (missing watchlists, missing Lunar creds with successful history) may still allow conditional operation but block full `APPROVED_FOR_PRODUCTION` if overall validation is not PASS.

## Certification lifecycle

1. GET `/api/v1/release-platform/certification` after validation PASS and health ≠ FAILED.
2. `go_live_recommendation = APPROVED_FOR_PRODUCTION` indicates P50 closeout criteria met for the owner catalog.
3. Re-check after major Lunar re-imports or variant repair — certification is computed, not stored.

## Troubleshooting

| Symptom | Likely cause | Action |
|--------|----------------|--------|
| Validation FAIL on variants | Variants not grouped | Run variant repair; verify `release_variant` rows |
| Validation FAIL on Lunar connector | No completed runs | Complete at least one import |
| Validation FAIL on re-import idempotency | Duplicate canonical UUID groups | Re-run idempotent import fix; inspect duplicate groups |
| Health FAILED on import pipeline | Recent FAILED runs | Inspect `lunar_feed_error`; fix source and re-import |
| Certification NOT_READY | Validation not PASS or health FAILED | Fix failing checks first |

## Recovery procedures

1. **Stale UI:** Refresh certification page; APIs recompute each request.
2. **Failed scheduled run:** Inspect scheduler run errors; re-enable scheduler after credentials and feed health restored.
3. **Legacy flat Lunar rows:** Repair groups variants; legacy issue rows may remain without blocking idempotent re-import when canonical resolution is active.
4. **Production go-live:** Confirm certification shows `APPROVED_FOR_PRODUCTION` before relying on release workflows daily.
