# Grading Submission Batch Architecture

## Purpose

`P37-04` adds the deterministic grading submission workflow layer for ComicOS. It records which grading candidates are grouped together, how those groups move through the grading lifecycle, and what shipment and cost history belongs to each batch.

This is a ledger and workflow tracker, not a grader integration layer.

## Models

- `GradingSubmissionBatch` stores the batch header, target grader, lifecycle dates, status, costs, checksum, and replay key.
- `GradingSubmissionItem` stores the candidate-to-batch linkage and item-level submission state.
- `GradingSubmissionShipment` stores outbound and return shipment records.
- `GradingSubmissionLifecycleEvent` stores append-only batch lifecycle history.
- `GradingSubmissionCostSnapshot` stores deterministic cost rollups and checksum history.

## Deterministic rules

Batch creation is stable and replay-safe.

- Candidate IDs are normalized into a deterministic sorted set.
- The same owner plus replay key returns the same batch.
- The same batch inputs produce the same checksum signature.
- One grading candidate may only belong to one active submission batch at a time.
- Lifecycle changes append events instead of rewriting history.

## Submission economics

Costs are Decimal-backed and derived from fixed grader schedules:

- grading fees
- outbound shipping
- return shipping
- insurance estimate

The batch layer does not estimate grades, change inventory balances, or import fees from external services.

## Lifecycle rules

Supported statuses:

- `DRAFT`
- `READY`
- `SHIPPED`
- `RECEIVED_BY_GRADER`
- `GRADING`
- `RETURN_SHIPPED`
- `COMPLETED`
- `CANCELLED`

Candidate integration is intentionally limited:

- `READY_FOR_SUBMISSION -> SUBMITTED` when a candidate is included in a batch
- `SUBMITTED -> GRADED` when the batch completes

Final grades remain nullable and are not assigned automatically.

## Shipment tracking

Shipment rows are stored separately from batch lifecycle transitions.

- `OUTBOUND` and `RETURN` directions are both supported
- carrier and tracking metadata are recorded as read-only history
- live carrier integrations and webhooks are intentionally out of scope

## Owner vs ops APIs

Owner routes are scoped to the authenticated user:

- `GET /grading-submission-batches`
- `POST /grading-submission-batches`
- `GET /grading-submission-batches/{id}`
- `PATCH /grading-submission-batches/{id}`
- lifecycle transition routes
- shipment creation route
- dashboard summary route

Ops routes are read-only and support explicit `owner_user_id` filtering:

- `GET /ops/grading-submission-batches`
- `GET /ops/grading-submission-batches/{id}`
- `GET /ops/grading-submission-events`
- `GET /ops/grading-submission-shipments`
- ops dashboard summary route

## Non-goals

- Grader API integrations
- Automated grade import
- Webhook systems
- Live carrier tracking
- Inventory mutation automation
- Recommendation logic or grade prediction
- Invoice reconciliation, label printing, packing workflows, or bulk scan intake
