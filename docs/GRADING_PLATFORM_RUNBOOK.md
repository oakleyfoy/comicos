# Grading Platform Runbook (P49)

Operational guide for the ComicOS Grading Intelligence Platform (P49-01 through P49-04). All grading outputs are advisory; nothing in this lane submits to graders or mutates inventory automatically.

## Condition Analysis Lifecycle

1. Ingest scan images and create a `ScanAnalysis` (Condition Intelligence).
2. Run quality, defect, profile, and subgrade agents via `/condition-intelligence` POST run endpoints or the UI.
3. Review condition dashboard metrics before requesting grade predictions.
4. **Troubleshooting:** Missing profiles usually means the condition pipeline was not run for that analysis. Re-run agents for the same analysis id (append-only new rows).

## Prediction Lifecycle

1. Ensure condition intelligence exists for the analysis.
2. Run grade prediction via `/grading-intelligence/run/predictions`.
3. Inspect predicted grade, floor/ceiling, confidence, and evidence on the Grading Intelligence dashboard.
4. Predictions are never auto-updated by validation or platform closeout.

## Recommendation Lifecycle

1. After predictions exist, run `/grading-intelligence/run/recommendations` and optional ROI/priority runs.
2. Review recommendations manually; use review endpoints to record human disposition (append-only reviews).
3. Platform certification reads recommendation counts and scores only.

## Calibration Lifecycle

1. Record actual grades (manual entry) via `/grading-validation/run/validation` with `actual_grades`.
2. Run calibration via `/grading-validation/run/calibration` to append calibration metrics.
3. Run reliability and outcomes agents for drift and outcome tracking.
4. Historical validation rows are never overwritten.

## Validation Lifecycle

1. Use Grading Validation dashboard for accuracy, drift, and reliability snapshots.
2. Use Grading Platform (`/grading-platform`) for cross-layer PASS/WARNING/FAIL validation and certification.
3. Re-run validation after meaningful new scans or actual grade data—each run is observational.

## Troubleshooting

| Symptom | Likely cause | Action |
|--------|----------------|--------|
| Validation WARNING on predictions | No predictions yet | Run condition pipeline then prediction agent |
| Validation WARNING on calibration | No actual grades recorded | POST validation with actual grades |
| Health DISABLED | No agent executions | Run the relevant grading agents once |
| Certification not ready | FAIL on any check or FAILED health | Fix data issues; re-check `/grading-platform/validation` |

## Recovery Procedures

1. **Stale dashboards:** Refresh UI; APIs recompute on demand (no cache invalidation required).
2. **Failed agent execution:** Inspect `/grading-intelligence/executions` or `/grading-validation/executions`; re-run the agent (new execution row).
3. **Incorrect advisory output:** Do not edit prediction rows; create a new analysis or prediction run after corrected scans.
4. **Personal go-live:** Confirm `/grading-platform/certification` shows `APPROVED_FOR_PERSONAL_USE` before relying on grading workflows daily.
