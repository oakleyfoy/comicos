# P42 Determinism Guarantees

Explicit invariants for multi-user dealer infrastructure. These are **platform contracts** frozen at P42 closeout.

## Authorization

- Permission evaluation uses stable role definitions and ordered permission keys (`PERMISSION_ORDER`).
- Role listings for a member are sorted by system role `sort_order`.
- Denied permission checks append audit rows with deterministic action keys and results.
- Default stance is **deny-by-default**; absence of membership or permission never grants access.

## Tenant isolation

- All org-scoped reads and writes filter by `organization_id`.
- Cross-org API access returns `403` or `404` without exposing foreign org payloads.
- Session org switch validates membership before binding `organization_id` on the session.
- Storefront public endpoints never return private org identifiers in inventory projections.

## Replay-safe lineage

Append-only tables (no in-place mutation of historical lineage rows in normal operation):

- `organization_events`
- `organization_inventory_workflow_events`
- `organization_review_events` / `organization_review_decisions`
- `dealer_storefront_events`
- `organization_activity_events` (including `lineage.*` types)
- `organization_audit_ledger`, `organization_compliance_events`
- `organization_dealer_dashboard_events`

Projections (dashboard metrics, audit entries from workflows) **read** upstream systems; they do not rewrite upstream lineage.

## Stable ordering

| Surface | Order rule |
|---------|------------|
| Organization list (user) | Stable slug / listing rules per service |
| Org events | Chronological `event_type` sequence per test contracts |
| Activity feed (API) | `id` descending (newest first) |
| Notifications | Newest first in list endpoints |
| Audit ledger (API) | `id` descending |
| Review queues | Queue name + `queue_position` deterministic after moves |
| Inventory queues | Active queue rows ordered by service rules |
| Dashboard snapshots | `generated_at DESC`, `id DESC` tie-break |
| Dashboard metrics | `generated_at DESC`, `id DESC` tie-break |
| Permission audit | `created_at ASC`, `id ASC` in tests |

## Serialization

- JSON payloads for metrics, snapshots, audit, and activity use stable key ordering in service `_stable_payload` helpers where applicable.
- Metric registry keys are fixed tuples (`METRIC_KEYS`, `DASHBOARD_SECTIONS`).

## Storefront visibility

- `PUBLIC` + active profile + enabled public inventory required for listings.
- `PRIVATE` or inactive profiles yield **404** on public inventory routes (fail-closed).
- Public inventory DTOs exclude internal pricing and review fields.

## Dashboard aggregation

- On-demand refresh generates metrics then snapshot; no background scheduler in P42.
- Section order is fixed: inventory, reviews, activity, storefront, notifications, security.
- Latest metric per `metric_key` wins by newest `generated_at` then `id`.

## Notifications

- Status transitions: `UNREAD` → `READ` → `ACKNOWLEDGED` with lineage events for read/ack.
- Targets only see their own notification rows.

## Inventory workflows

- Assignment state machine: assign → complete/unassign with append-only workflow events.
- Unauthorized inventory access attempts log `unauthorized_inventory_access_attempt` events.

## Review workflows

- Terminal statuses: approved, rejected, completed; pending counts exclude terminals for dashboard metrics.
- One append-only decision row per approve/reject action.

## Known non-guarantees (P42 scope)

- No realtime websocket ordering.
- No cross-org deterministic ordering (only within-org).
- Full-repo pytest does not imply ordering guarantees for non-P42 subsystems.
