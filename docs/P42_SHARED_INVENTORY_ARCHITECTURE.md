# P42 Shared Inventory Architecture

## Objective

P42-04 establishes deterministic organization-scoped shared inventory infrastructure for dealer organizations: assignment tracking, operational queues, shared visibility, and append-only workflow lineage. It does not implement live collaboration, locking, marketplace sync, storefront publishing, workflow automation, notifications, or field-level ACL systems.

## Core Model

Three tables anchor the foundation:

- `organization_inventory_assignments`: staff responsibility records with explicit status transitions (`ACTIVE`, `COMPLETED`, `UNASSIGNED`).
- `organization_inventory_queues`: one active queue row per organization/inventory item with deterministic `queue_position` ordering inside named queues.
- `organization_inventory_workflow_events`: immutable append-only lineage for assignment and queue transitions plus unauthorized access attempts.

Inventory ownership remains on `inventory_copy.user_id`. Organization visibility is derived from active organization membership: an inventory copy is visible to an organization when its owning user is an active member.

## Assignment Lifecycle

1. An authorized actor (`inventory:update`) assigns a copy to an active member.
2. The service validates organization scope, membership, and assignee membership.
3. A new `ACTIVE` assignment row is created and an `inventory_assigned` workflow event is appended.
4. If no queue row exists, the copy enters the default `intake` queue.
5. `unassign` transitions the active row to `UNASSIGNED` and appends `inventory_unassigned`.
6. `complete` transitions the active row to `COMPLETED`, sets `completed_at`, and appends `assignment_completed`.

Assignment history is preserved; active assignment uniqueness is enforced in the service layer.

## Queue Architecture

Required queue names:

- `intake`
- `grading_review`
- `scan_review`
- `marketplace_ready`
- `archived`

Queue ordering is deterministic:

- Positions are monotonic within `(organization_id, queue_name)` for active rows.
- `move_inventory_queue` updates the existing org/item row in place to preserve the unique `(organization_id, inventory_item_id)` constraint.
- Workflow events capture `queue_created`, `queue_moved`, and `queue_removed` transitions with stable JSON payloads.

## Organization Inventory Visibility

Shared visibility is resolved through:

- `validate_shared_inventory_access` for fail-closed permission checks.
- `resolve_inventory_visibility` for deterministic inventory id sets owned by active members.
- `GET /inventory?organization_id=` for backward-compatible list rendering with assignment/queue metadata hydration.

Cross-organization inventory access is denied by default. Inventory outside member ownership is treated as out of scope (`403`).

## Workflow Lineage

Workflow events are append-only and never mutated. Supported event types:

- `inventory_assigned`
- `inventory_unassigned`
- `assignment_completed`
- `queue_moved`
- `queue_created`
- `queue_removed`
- `unauthorized_inventory_access_attempt`

Payloads are deterministically serialized with sorted JSON keys for replay-safe comparisons.

## API Surface

Owner routes (v1 envelope):

- `GET /organizations/{organization_id}/inventory/assignments`
- `GET /organizations/{organization_id}/inventory/queues`
- `GET /organizations/{organization_id}/inventory/workflow-events`
- `POST /organizations/{organization_id}/inventory/assign`
- `POST /organizations/{organization_id}/inventory/unassign`
- `POST /organizations/{organization_id}/inventory/complete`
- `POST /organizations/{organization_id}/inventory/queues/move`

Permissions:

- `inventory:view` for read/list surfaces
- `inventory:update` for assignment and queue mutations
- `audit:view` for workflow event feed

## Future Expansion Points

- Real-time collaboration and websocket feeds can subscribe to append-only workflow events.
- Inventory locking can wrap assignment transitions without changing historical rows.
- Custom queue builders can extend the fixed queue registry while preserving deterministic ordering contracts.
- Marketplace and storefront flows can consume queue state as downstream triggers once synchronization phases begin.
