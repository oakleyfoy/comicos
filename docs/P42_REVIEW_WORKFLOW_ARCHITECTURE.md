# P42 Review Workflow Architecture

## Objective

P42-05 establishes deterministic organization review and approval infrastructure for dealer teams: review records, immutable decision lineage, approval queues, and shared operational collaboration primitives without real-time editing, chat, notifications, or external workflow engines.

## Core Model

Four tables implement the foundation (three specified models plus append-only lineage):

- `organization_reviews`: operational review requests tied to organization inventory copies.
- `organization_review_decisions`: immutable approve/reject decisions (append-only).
- `organization_approval_queues`: deterministic queue placement per review (`organization_id`, `review_id` unique).
- `organization_review_events`: append-only workflow lineage for lifecycle and queue transitions.

Inventory ownership remains on `inventory_copy.user_id`. Reviews inherit organization scope through the same active-membership inventory rules established in P42-04.

## Review Lifecycle

1. **Create** (`operations:manage`): inserts review (`PENDING` or `ASSIGNED`), seeds default `intake_review` queue unless overridden, appends `review_created`.
2. **Assign**: sets assignee + `ASSIGNED`, appends `review_assigned`.
3. **Approve / Reject**: append-only decision row, terminal review status, append `review_approved` / `review_rejected`.
4. **Complete** (service helper): terminal `COMPLETED` with `review_completed` event.
5. **Queue move**: updates queue row in place with monotonic positions, appends `queue_moved`.

Terminal reviews reject further mutation (`409`).

## Approval Queues

Required queue names:

- `intake_review`
- `grading_review`
- `authentication_review`
- `marketplace_approval`
- `archival_review`

Ordering is deterministic by `(organization_id, queue_name, queue_position, id)`. Each review has at most one queue row per organization.

## Permissions

- `operations:view`: list reviews, queues, and decisions.
- `operations:manage`: create, assign, approve, reject, and move queues.

Access resolution is deny-by-default with organization isolation and inventory scope validation. Unauthorized attempts append `unauthorized_review_access_attempt` events.

## API Surface

- `GET /organizations/{organization_id}/reviews`
- `GET /organizations/{organization_id}/reviews/queues`
- `GET /organizations/{organization_id}/reviews/{review_id}/decisions`
- `POST /organizations/{organization_id}/reviews`
- `POST /organizations/{organization_id}/reviews/{review_id}/assign`
- `POST /organizations/{organization_id}/reviews/{review_id}/approve`
- `POST /organizations/{organization_id}/reviews/{review_id}/reject`
- `POST /organizations/{organization_id}/reviews/queues/move`

All routes use the standard v1 envelope and organization permission dependencies.

## Inventory Integration

When `GET /inventory?organization_id=` is used, active review metadata is hydrated on each row:

- `organization_active_review_id`
- `organization_review_status`
- `organization_review_type`
- `organization_review_queue_name`

Only non-terminal reviews (`PENDING`, `ASSIGNED`) are surfaced as active.

## Operational Invariants

- Decisions and events are never updated or deleted.
- Queue positions are stable and recomputed deterministically on moves.
- Cross-organization review access is denied.
- Replay-safe JSON payloads use sorted keys.

## Future Expansion

- Real-time collaboration can subscribe to `organization_review_events`.
- Notifications/escalations can trigger from terminal decision events.
- Comment threads can attach to review ids without altering decision tables.
- External approval systems can mirror append-only decision imports in later phases.
