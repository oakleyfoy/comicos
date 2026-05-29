# P42-07 Organization Activity Feed Architecture

## Purpose

P42-07 establishes append-only organization activity feeds and internal notifications for ComicOS dealer organizations. It projects operational workflow events into a deterministic, org-scoped feed without replacing existing audit tables or organization event logs.

## Activity aggregation model

- **OrganizationActivityEvent** stores immutable operational activity rows keyed by `organization_id`.
- Payloads are normalized with stable JSON serialization (`sort_keys`, UTC timestamps).
- Each payload includes an optional `category` (`organization`, `inventory`, `reviews`, `storefront`, `security`, `permissions`) and `engine_version`.
- **OrganizationNotification** targets a single org member (`target_user_id`) and optionally links to a source activity via `activity_event_id`.
- **OrganizationNotificationReceipt** tracks per-user `read_at` and `acknowledged_at` with a unique `(notification_id, user_id)` constraint.

Workflow services call `activity_feed_integration` helpers before their existing `session.commit()` boundaries. Helpers flush only; they do not duplicate underlying audit/event systems.

## Notification lifecycle

1. **Created** — `notification_status=UNREAD`, receipt row inserted for the target user, lineage `lineage.notification_created`.
2. **Read** — receipt `read_at` set, status moves to `READ`, lineage `lineage.notification_read`.
3. **Acknowledged** — receipt `acknowledged_at` set, status `ACKNOWLEDGED`, lineage `lineage.notification_acknowledged`.

Notifications are visible only to the targeted user within the same organization. Membership is required; feed listing requires `operations:view`.

## Feed ordering guarantees

Public feed queries order by:

1. `created_at` descending (newest first)
2. `id` descending (stable tiebreak)

Lineage rows (`activity_type` prefixed with `lineage.`) and `visibility_scope=SYSTEM` rows are excluded from operator-facing feeds. Category filters apply after fetch using payload `category`.

## Visibility rules

- **Fail-closed / deny-by-default** — missing membership or permission yields HTTP 403.
- **Org isolation** — all queries constrain `organization_id`; cross-org URLs cannot surface foreign rows.
- **Activity feed** — requires active org + `operations:view`.
- **Notifications** — requires active membership; target user must match the notification row.
- Unauthorized attempts append isolated-session lineage events (`lineage.unauthorized_feed_access_attempt`, `lineage.visibility_denied`) without granting access.

## Replay-safe activity lineage

Lineage event types (SYSTEM visibility, append-only):

- `lineage.activity_generated`
- `lineage.notification_created`
- `lineage.notification_read`
- `lineage.notification_acknowledged`
- `lineage.visibility_denied`
- `lineage.unauthorized_feed_access_attempt`

Activity rows are never updated or deleted in this phase. Notification status updates apply only to notification delivery state, not historical activity events.

## API surface (v1 envelope)

- `GET /organizations/{id}/activity`
- `GET /organizations/{id}/notifications`
- `GET /organizations/{id}/notifications/unread-count`
- `POST /organizations/{id}/notifications/{notification_id}/read`
- `POST /organizations/{id}/notifications/{notification_id}/acknowledge`

Engine key: `organization_activity_feed` → `P42-07-v1`.

## Workflow projections

Integrated projections (non-exhaustive):

- Organization membership accept/remove
- Shared inventory assignment
- Review approve/reject decisions
- Storefront profile/settings updates
- Permission role assignment
- Session security (organization switch, session revoke when org-bound)

## Future expansion points

- Email/SMS/push delivery channels
- Websocket or SSE live feed updates
- Escalation policies and digest batching
- Async fanout workers for multi-recipient notifications
- Public or partner-facing activity feeds

Realtime delivery and external integrations are intentionally out of scope for P42-07.

## Operational invariants

- Single Alembic head maintained (`20260630_0118`).
- No destructive cascades on activity FK relationships.
- Deterministic pagination via stable ordering + explicit `limit`/`offset`.
- Backend-authoritative visibility; UI must not infer cross-org or cross-user access.
