# Grading closeout architecture (P37-09)

## Purpose

P37-09 closes the deterministic grading lane by adding a dedicated **grading operational reporting registry** and a final low-risk stabilization pass over the P37 surfaces:

- grading candidates
- spread engine
- ROI engine
- submission batches
- reconciliation
- recommendation engine
- risk / confidence
- dealer grading dashboard

This phase is intentionally **observational**. It adds auditability, exportability, and route consistency without introducing new grading intelligence, scan AI, predictive modeling, or hidden mutation.

## Grading philosophy

ComicOS grading remains:

1. **Deterministic first** — identical persisted state plus identical generation params must yield identical report rows and checksums.
2. **Explainable** — every report row persists lineage metadata and a row checksum.
3. **Replay-safe** — repeated generation with the same `replay_key` returns the original run.
4. **Append-safe** — new grading reports accumulate as immutable run history; report generation does not rewrite source grading ledgers.
5. **Operational, not autonomous** — the system describes grading economics and workflow state; it does not auto-grade, auto-submit, or auto-mutate FMV/inventory.

## Deterministic grading economics

The P37 stack now resolves into a stable grading decision pipeline:

- `GradingCandidate*` expresses deterministic grading intent and lifecycle.
- `GradingSpreadSnapshot` and `GradingRoiSnapshot` expose raw-vs-graded economics and break-even posture.
- `GradingSubmission*` records shipment/cost/workflow state.
- `GradingReconciliation*` and `GraderPerformanceSnapshot` measure realized outcomes versus expected outcomes.
- `GradingRecommendation*` and `GradingRiskSnapshot` provide explainable decision support only.
- `DealerGradingDashboard*` aggregates the grading lane into a command-center snapshot, metrics ledger, alerts, and append-safe feed.

P37-09 does not change the meaning of those ledgers. It adds deterministic CSV closeout reports over them.

## Reporting registry

Persistence lives in:

- `GradingOperationalReportRun`
- `GradingOperationalReportFile`
- `GradingOperationalReportItem`

These mirror the P36 reporting registry shape, but remain grading-specific so the P37 audit trail has its own taxonomy and history.

### Run model

`GradingOperationalReportRun` stores:

- `report_type`
- `status` (`DRAFT | RUNNING | COMPLETED | FAILED`)
- `replay_key`
- normalized `generation_params_json`
- UTF-8 CSV `checksum`
- `csv_row_count`
- timestamps and optional `failure_reason`

`(owner_user_id, replay_key)` is unique, so replay behavior is deterministic and idempotent.

### File model

`GradingOperationalReportFile` stores deterministic CSV artifact metadata:

- `file_name`
- `storage_path`
- `file_type`
- file `checksum`
- persisted `row_count`

### Item model

`GradingOperationalReportItem` stores row-level lineage:

- monotonic `row_number`
- `lineage_domain`
- `lineage_key`
- `lineage_json`
- `row_checksum`

This keeps report rows explainable even after the CSV has been downloaded elsewhere.

## Supported report types

- `grading_candidate_summary`
- `grading_roi_summary`
- `grading_submission_summary`
- `grading_reconciliation_summary`
- `grading_recommendation_summary`
- `grading_risk_summary`
- `grading_dashboard_summary`
- `grader_performance_summary`

All reports render UTF-8 CSV with a stable metric-style schema:

- `metric_family`
- `metric_key`
- `metric_value_integer`
- `metric_value_decimal`
- `metric_value_text`
- `notes`

Within each report, rows are lexicographically ordered by the CSV tuple to preserve stable output ordering.

## Replay-safe reporting

Service: `apps/api/app/services/grading_reporting.py`

Core behavior:

- normalize generation params and stamp `generator_version`
- check `replay_key` before generating
- create `RUNNING` run row
- collect deterministic rows from persisted grading ledgers only
- render UTF-8 CSV
- persist row lineage items and file artifact
- mark the run `COMPLETED`

If the same owner replays the same `replay_key`, the existing run is returned with HTTP `200`. A new replay key produces a new append-safe run, even when the checksum is identical.

## Checksum behavior

- **Row checksum**: SHA-256 over the canonicalized CSV row cells.
- **Run / file checksum**: SHA-256 over the full UTF-8 CSV body.
- **Deterministic filename**: `comic_os_{report_type}_{YYYY-MM-DD}_run_{run_id}.csv`

Example:

`comic_os_grading_roi_summary_2026-05-26_run_12.csv`

Checksums are descriptive fingerprints only; they do not mutate or reconcile source grading data.

## Operational grading workflows

The closeout reporting lane is intended for:

- daily grading pipeline review
- ops audit and cross-owner inspection
- batch cost and turnaround review
- recommendation/risk checkpointing
- reconciliation and grader performance review
- snapshot export for offline analysis or accounting-style closeout

Report generation must remain synchronous, deterministic, and read-only.

## Recommendation and risk philosophy

Recommendations and risk remain **assistive overlays**, not control systems:

- recommendations explain why a book should be graded or held raw
- risk / confidence explains uncertainty, volatility, and evidence weakness
- P37-09 reporting exports those overlays for auditability, but does not elevate them into auto-actions

Nothing in the closeout registry may auto-change:

- recommendation actions
- submission states
- FMV
- liquidity
- inventory status
- listing state

## Owner vs ops APIs

Owner routes:

- `GET /grading-reports`
- `POST /grading-reports/generate`
- `GET /grading-reports/{id}`
- `GET /grading-reports/{id}/download`

Ops routes:

- `GET /ops/grading-reports`
- `GET /ops/grading-reports/{id}`
- `GET /ops/grading-reports/{id}/download`

Owner routes are strictly scoped to `current_user.id`. Ops routes stay read-only and require explicit ops-admin access.

## Route consistency notes

P37 closeout keeps grading route naming explicit and parallel:

- write/generate owner paths use non-ops prefixes
- ops mirrors live under `/ops/*`
- `generate` routes are registered before dynamic `{id}` routes
- download routes resolve persisted file artifacts rather than regenerating content

The closeout pass intentionally avoids risky router refactors outside the new grading-report lane.

## Final stabilization pass

The production stabilization work in P37-09 focuses on low-risk consistency only:

- grading reports now follow the same replay-status contract as P36 operational reports
- CSV filenames, row lineage, and checksum handling use one deterministic pattern
- dashboard and ops surfaces expose lightweight report visibility and downloads
- targeted regression coverage confirms report generation does not mutate source grading systems

No risky model rewrites, background workers, or cross-ledger refactors were introduced during closeout.

## Non-goals

Explicitly deferred beyond P37:

- scan AI
- defect detection
- slab OCR
- broader vision systems
- autonomous grading
- probabilistic ML
- predictive grading models
- live grader API integrations
- automated submission systems
- webhook-driven grading automation
- automatic FMV mutation
- automatic inventory mutation
