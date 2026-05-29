# P42 API Reference

Authoritative inventory of organization-scoped **P42** HTTP APIs under `/api/v1`. All listed org routes use the **Scan API v1 envelope** unless noted. Legacy owner-scoped `/dealer-dashboard` (P36) is out of scope here.

## Global rules

- **Authentication**: Bearer session token on protected routes.
- **Org context**: Routes under `/organizations/{organization_id}/…` require active membership; many also require explicit permission keys.
- **Deny behavior**: Unauthorized access returns `403`; some routes return `404` for non-members or hidden resources (fail-closed, no cross-org leakage).
- **Pagination**: List endpoints accept `limit` (1–200) and `offset`; responses include `data.items` and `data.pagination`.

## Organizations (P42-01)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| POST | `/organizations` | Authenticated user | Creates org; creator becomes owner |
| GET | `/organizations` | Authenticated user | Lists orgs where user is active member |
| GET | `/organizations/{id}` | `organization:view` | Org detail for members only |
| POST | `/organizations/{id}/invite` | `members:invite` | Invitation row; idempotent per email |
| POST | `/organizations/invitations/{token}/accept` | Invitee session | Accepts invite; assigns default viewer role |
| POST | `/organizations/{id}/archive` | `organization:archive` | Archives org |
| GET | `/organizations/{id}/members` | `members:view` | Member list |
| GET | `/organizations/{id}/events` | `audit:view` | Append-only org events |
| GET | `/organizations/{id}/roles` | `members:view` | System role catalog |
| GET | `/organizations/{id}/members/{member_id}/roles` | `members:view` | Member role assignments |
| POST | `/organizations/{id}/members/{member_id}/roles` | `members:roles:update` | Assign role |
| DELETE | `/organizations/{id}/members/{member_id}/roles/{role_id}` | `members:roles:update` | Remove role assignment |

## Permissions (P42-02)

Permission evaluation is enforced via `require_org_permission` on routes and service-layer `evaluate_permission`. Denied checks append rows to `organization_permission_audit`. Permission keys are defined in `app/security/permissions.py` (owner, admin, manager, staff, viewer role bundles).

## Sessions (P42-03)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/auth/sessions` | Authenticated user | Lists caller’s sessions |
| GET | `/auth/security-context` | Authenticated user | Active org and effective permission keys |
| POST | `/auth/sessions/revoke` | Authenticated user | Revokes one session |
| POST | `/auth/sessions/revoke-all` | Authenticated user | Revokes all caller sessions |
| POST | `/auth/security-context/switch-organization` | Active member of target org | Sets session `organization_id`; validates membership |

## Shared inventory (P42-04)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/inventory?organization_id={id}` | `inventory:view` (org scope) | Owner copies visible to org; hydrated assignment/queue/review fields |
| GET | `/organizations/{id}/inventory/assignments` | `inventory:view` | Assignment list |
| GET | `/organizations/{id}/inventory/queues` | `inventory:view` | Queue list |
| GET | `/organizations/{id}/inventory/workflow-events` | `audit:view` | Append-only workflow events |
| POST | `/organizations/{id}/inventory/assign` | `inventory:update` | Creates active assignment |
| POST | `/organizations/{id}/inventory/unassign` | `inventory:update` | Ends assignment |
| POST | `/organizations/{id}/inventory/complete` | `inventory:update` | Completes assignment |
| POST | `/organizations/{id}/inventory/queues/move` | `inventory:update` | Deterministic queue placement |

## Reviews (P42-05)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/organizations/{id}/reviews` | `operations:view` | Review list |
| GET | `/organizations/{id}/reviews/queues` | `operations:view` | Queue ordering |
| GET | `/organizations/{id}/reviews/{review_id}/decisions` | `operations:view` | Append-only decisions |
| POST | `/organizations/{id}/reviews` | `operations:manage` | Creates review |
| POST | `/organizations/{id}/reviews/{review_id}/assign` | `operations:manage` | Assigns reviewer |
| POST | `/organizations/{id}/reviews/{review_id}/approve` | `operations:manage` | Approve + decision row |
| POST | `/organizations/{id}/reviews/{review_id}/reject` | `operations:manage` | Reject + decision row |
| POST | `/organizations/{id}/reviews/queues/move` | `operations:manage` | Queue move |

## Storefronts (P42-06)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/storefronts/{public_slug}` | Public | Profile when visibility allows |
| GET | `/storefronts/{public_slug}/inventory` | Public | Sanitized inventory only; hidden if private/inactive |
| GET | `/storefronts/{public_slug}/featured` | Public | Featured subset |
| POST | `/organizations/{id}/storefront/profile` | Storefront manage (service gate) | Upsert dealer profile |
| POST | `/organizations/{id}/storefront/settings` | Storefront manage (service gate) | Visibility and featured rules |

Public responses must not include acquisition cost, internal review state, or org operational metadata.

## Activity (P42-07)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/organizations/{id}/activity` | `operations:view` | Non-lineage activity newest-first |
| GET | `/organizations/{id}/notifications` | Active member; target user scoped | User’s notifications for org |
| GET | `/organizations/{id}/notifications/unread-count` | Active member | Unread count for caller |
| POST | `/organizations/{id}/notifications/{nid}/read` | Notification recipient rules | Marks read |
| POST | `/organizations/{id}/notifications/{nid}/acknowledge` | Notification recipient rules | Acknowledges |

## Audit (P42-08)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/organizations/{id}/audit` | `audit:view` (service) | Audit ledger entries |
| GET | `/organizations/{id}/compliance-events` | `audit:view` (service) | Compliance events |
| GET | `/organizations/{id}/audit/access-log` | `audit:view` (service) | Access grant/deny log |

Routes use `resolve_org_context`; enforcement and denied-access logging occur in `audit_ledger_service`.

## Dealer dashboard (P42-09)

| Method | Endpoint | Permission / access | Response / visibility |
|--------|----------|---------------------|------------------------|
| GET | `/organizations/{id}/dashboard?refresh=` | `operations:view` | Section summaries + optional snapshot refresh |
| GET | `/organizations/{id}/dashboard/metrics` | `operations:view` | Metric history list |
| GET | `/organizations/{id}/dashboard/snapshots` | `operations:view` | Snapshot list newest-first |

Org dashboard tables are `organization_dealer_dashboard_*` (distinct from P36 owner `dealer_dashboard_*`).
