# Dealer Grading Dashboard Architecture

## Purpose

`P37-08` adds the unified grading command center for ComicOS.

This layer is the grading equivalent of the P36 Dealer OS surface:

- deterministic
- replay-safe
- append-safe
- explainable
- owner / ops separated
- observational only

It does **not** perform scan AI, image grading, defect analysis, probabilistic modeling, autonomous grading, or hidden mutation of recommendations, inventory, FMV, pricing, or submissions.

## Inputs

The dashboard reads existing grading ledgers only:

- grading candidates
- grading spread snapshots
- grading ROI snapshots
- grading submission batches and lifecycle events
- grading reconciliation records and grader performance
- grading recommendations
- grading risk / confidence snapshots
- liquidity snapshots

No external grader APIs, webhooks, or background streaming systems are involved.

## Models

The grading dashboard persists four artifacts:

- `DealerGradingDashboardSnapshot`
- `DealerGradingDashboardMetric`
- `DealerGradingDashboardAlert`
- `DealerGradingDashboardFeedEvent`

### Snapshot

`DealerGradingDashboardSnapshot` stores the frozen grading rollup for one owner and one `snapshot_date`.

Primary launch fields:

- pipeline counts (`active_candidate_count`, `ready_for_submission_count`, `submitted_candidate_count`, `graded_candidate_count`)
- opportunity / risk posture (`elite_recommendation_count`, `high_risk_candidate_count`, `low_confidence_candidate_count`)
- economic rollups (`average_estimated_roi`, `average_risk_adjusted_roi`, `grading_pipeline_value`, `estimated_total_submission_cost`, `expected_total_profit`)
- operational rollups (`active_submission_batch_count`)
- replay / integrity fields (`replay_key`, `checksum`, `snapshot_date`, `created_at`)

### Metrics

`DealerGradingDashboardMetric` stores deterministic detail behind the top-line snapshot. Launch metrics include:

- recommendation action counts
- elite opportunity count
- low / high risk counts
- confidence counts
- shipped / delayed batch counts
- average turnaround
- above / below expectation counts
- average ROI delta
- grader performance rollup metadata

Metrics are keyed uniquely by `(dashboard_snapshot_id, metric_key)`.

### Alerts

`DealerGradingDashboardAlert` stores observational grading issues only.

Launch alert types:

- `NEGATIVE_ROI`
- `HIGH_RISK`
- `LOW_CONFIDENCE`
- `SUBMISSION_DELAY`
- `RECONCILIATION_FAILURE`
- `WEAK_LIQUIDITY`
- `MISSING_EVIDENCE`

Severity remains bounded to:

- `info`
- `warning`
- `critical`

Alerts never auto-fix, auto-route, or mutate the underlying grading records.

### Feed

`DealerGradingDashboardFeedEvent` is an append-safe grading activity ticker keyed by deterministic identities.

Launch event types:

- `CANDIDATE_CREATED`
- `RECOMMENDATION_GENERATED`
- `SUBMISSION_BATCH_CREATED`
- `SUBMISSION_SHIPPED`
- `GRADES_RETURNED`
- `RECONCILIATION_COMPLETED`
- `HIGH_RISK_DETECTED`
- `ELITE_OPPORTUNITY_DETECTED`

Feed rows are unique per `(owner_user_id, deterministic_key)` so repeated dashboard generations do not duplicate the same source evidence.

## Deterministic aggregation

`POST /dealer-grading-dashboard/generate` performs pure-read aggregation first, then persists derived rows:

1. Trim and check `replay_key`.
2. Build a pure-read payload scoped to `(owner_user_id, snapshot_date)`.
3. Select the latest recommendation, risk, liquidity, and grader-performance rows per deterministic scope.
4. Compute snapshot rollups from those persisted rows only.
5. Materialize sorted metrics, alerts, and feed candidates in deterministic order.
6. Hash the full payload using sorted-key JSON to produce a stable `checksum`.
7. Reuse an existing snapshot when replay key or checksum already matches.
8. Persist metrics, alerts, and new feed rows without changing upstream grading ledgers.

Important aggregation rules:

- deterministic ordering
- append-safe history
- stable checksums
- no hidden mutation
- latest-in-scope selection uses stable `(snapshot_date, created_at, id)` precedence

## Alert logic

Launch alert rules are deterministic:

- `NEGATIVE_ROI`: active recommendation projects negative ROI or negative expected profit
- `HIGH_RISK`: latest risk snapshot is `HIGH` or `EXTREME`
- `LOW_CONFIDENCE`: latest risk snapshot confidence is `LOW`
- `SUBMISSION_DELAY`: active batch elapsed days exceed `estimated_turnaround_days`
- `RECONCILIATION_FAILURE`: reconciliation result is `BELOW_EXPECTATION`
- `WEAK_LIQUIDITY`: latest liquidity snapshot marks inventory `LOW` or `ILLIQUID`
- `MISSING_EVIDENCE`: recommendation or linked risk evidence count falls below the minimum launch threshold

These alerts remain descriptive. No dashboard action changes a candidate, recommendation, batch, or inventory row automatically.

## Feed behavior

The grading feed is an append-safe operational ticker over the grading lifecycle.

Behavioral guarantees:

- deterministic keys per source event
- stable ordering from `created_at DESC, id DESC` on reads
- repeated generations skip previously-seen deterministic keys
- historical feed rows stay intact even when new snapshots are generated later

## Replay safety

Replay guarantees:

- `replay_key` uniqueness is enforced per owner on snapshots
- identical `(owner, snapshot_date, checksum)` reuses the existing snapshot
- metrics are unique per snapshot key
- alerts are unique per owner + deterministic snapshot-local replay key
- feed rows are unique per owner + deterministic source key

This keeps rebuilds replay-safe while preserving append-safe history.

## Owner vs Ops APIs

Owner routes:

- `GET /dealer-grading-dashboard`
- `POST /dealer-grading-dashboard/generate`
- `GET /dealer-grading-dashboard/metrics`
- `GET /dealer-grading-dashboard/alerts`
- `GET /dealer-grading-dashboard/feed`

Ops routes:

- `GET /ops/dealer-grading-dashboard`
- `GET /ops/dealer-grading-dashboard/metrics`
- `GET /ops/dealer-grading-dashboard/alerts`
- `GET /ops/dealer-grading-dashboard/feed`

Supported filters:

- `owner_user_id` on ops routes
- `severity`
- `alert_type`
- `event_type`
- `created_from`
- `created_to`

Ops routes remain read-only mirrors. Only owners generate snapshots.

## Operational workflow

Recommended dealer workflow:

1. Materialize upstream grading ledgers first (recommendations, risk, submissions, reconciliation as needed).
2. Generate a grading dashboard snapshot explicitly.
3. Review the pipeline overview, recommendation/risk posture, submission delays, and reconciliation outcomes.
4. Use the alerts panel and grading feed to inspect evidence, not to auto-run remediation.
5. Move to ops routes for cross-owner read-only inspection when needed.

## Frontend philosophy

The grading dashboard UI stays dense and operational:

- `DashboardPage` becomes the grading command center with sections A-G
- `OperationsPage` exposes alerts, feed, metrics, and grading KPI tables
- inventory detail remains lightweight and continues to rely on the existing grading recommendation / risk / submission / reconciliation badges

No marketing tiles, autoplay refresh, or websocket dependency is required.

## Non-goals

Hard stops for `P37-08`:

- scan AI
- defect overlays
- image grading
- live grader APIs
- websocket streaming
- autonomous grading decisions
- automatic recommendation mutation
- automatic inventory mutation
- predictive grading models
