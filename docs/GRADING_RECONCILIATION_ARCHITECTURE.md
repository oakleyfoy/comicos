# Grading Reconciliation Architecture

## Purpose

`P37-05` adds the deterministic grading-result reconciliation layer for ComicOS. It compares expected grading assumptions against the actual returned grade and realized grading economics after a submission item comes back from a grader.

This is the first grading phase where final grade outcomes, ROI deltas, and historical grader performance become persistent records.

## Models

- `GradingReconciliationRecord` stores the expected vs actual outcome for a single `GradingSubmissionItem`.
- `GradingReconciliationEvidence` stores lineage rows for submission, ROI, spread, FMV, sale, and manual-entry evidence.
- `GradingReconciliationHistory` stores append-safe historical outcome snapshots.
- `GraderPerformanceSnapshot` stores deterministic grader rollups for one owner or the ops/global lane.

## Deterministic calculations

All monetary and ROI math uses Decimal-safe helpers with explicit quantization.

- `roi_delta = realized_roi - expected_roi`
- `realized_roi = (realized_graded_value - expected_raw_value - per_item_cost_share) / per_item_cost_share`
- `expected_roi` prefers the ROI engine snapshot when available, then falls back to candidate estimates and deterministic cost-share math

Checksums are SHA-256 hashes of normalized JSON payloads, so the same inputs produce the same reconciliation signature.

## Accuracy classifications

Grades are normalized to tenth-step Decimal values before comparison.

- `ABOVE_EXPECTATION` when `actual_grade > expected_grade`
- `MET_EXPECTATION` when normalized grades are equal
- `BELOW_EXPECTATION` when `actual_grade < expected_grade`
- `INSUFFICIENT_DATA` when either side is missing or unparsable

## Submission integration

Reconciliation is anchored to `GradingSubmissionItem`.

- The item’s `final_grade` may be populated during reconciliation
- The linked `GradingCandidate` remains on the completed grading track
- History rows and grader performance snapshots append instead of rewriting prior outcomes

## Evidence and performance tracking

Evidence types may include:

- submission batch + cost snapshots
- ROI engine snapshots
- spread engine snapshots
- market FMV snapshots
- manual realized-value entry
- sales ledger and market-sale references

Each reconcile run also appends grader performance snapshots for:

- the owner-specific grader lane
- the ops/global grader lane

## Owner vs ops APIs

Owner routes:

- `GET /grading-reconciliation`
- `GET /grading-reconciliation/{id}`
- `GET /grading-reconciliation/evidence`
- `GET /grading-reconciliation/history`
- `GET /grader-performance`
- `POST /grading-reconciliation/reconcile`
- dashboard summary route

Ops routes are read-only:

- `GET /ops/grading-reconciliation`
- `GET /ops/grading-reconciliation/{id}`
- `GET /ops/grading-reconciliation-evidence`
- `GET /ops/grading-reconciliation-history`
- `GET /ops/grader-performance`
- ops dashboard summary route

## Non-goals

- Automated grader imports
- OCR slab reading or scan verification
- AI grading or defect analysis
- Recommendation logic
- Automatic FMV updates
- Automatic listing pricing changes
- Automatic inventory mutation
- Live grader APIs or probabilistic grading
