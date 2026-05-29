# P42 Dealer Operations Dashboard Architecture

## Objective

P42-09 adds an organization-scoped dealer operations dashboard for ComicOS multi-tenant dealer organizations. It aggregates inventory, review, storefront, activity, notification, and session signals into deterministic snapshots and metrics without replacing underlying workflow, activity, audit, or legacy P36 owner dashboards.

## Model separation

P36-07 legacy tables (`dealer_dashboard_snapshot`, owner-scoped) remain unchanged. P42-09 introduces org-scoped append-only tables:

- `organization_dealer_dashboard_snapshots`
- `organization_dealer_operational_metrics`
- `organization_dealer_dashboard_events`

Python models live in `app/models/organization_dealer_dashboard.py` as `OrganizationDealerDashboardSnapshot`, `OrganizationDealerOperationalMetric`, and `OrganizationDealerDashboardEvent`.

## Aggregation model

`dealer_dashboard_service.py` provides:

- `generate_dashboard_snapshot`
- `generate_operational_metrics`
- `list_dashboard_snapshots`
- `list_dashboard_metrics`
- `resolve_dashboard_summary`
- `create_dashboard_event`

On-demand generation runs during dashboard reads (`refresh=true` by default). No background schedulers are introduced in this phase.

## Metric registry

Groups: `inventory`, `reviews`, `assignments`, `storefront`, `activity`, `security`, `notifications`.

Registered keys include:

- `active_inventory_count`
- `pending_reviews_count`
- `assigned_inventory_count`
- `unread_notifications_count`
- `active_staff_count`
- `storefront_public_inventory_count`
- `recent_activity_count`
- `active_org_sessions_count`

Values serialize as stable JSON with sorted keys and `engine_version` metadata.

## Dashboard sections

Rendered section order (fixed):

1. inventory
2. reviews
3. activity
4. storefront
5. notifications
6. security

Snapshots and metric lists order by `generated_at DESC, id DESC`.

## Visibility

Dashboard access requires:

- active organization
- active membership
- `operations:view`

Failed attempts append `lineage.unauthorized_dashboard_access_attempt` events in an isolated session (fail-closed).

## Immutable dashboard lineage

Append-only dashboard events include:

- `lineage.dashboard_snapshot_generated`
- `lineage.dashboard_metric_generated`
- `lineage.dashboard_accessed`
- `lineage.unauthorized_dashboard_access_attempt`
- `lineage.elevated_operational_alert` (when pending review volume crosses configured threshold)

## API surface

- `GET /api/v1/organizations/{organization_id}/dashboard`
- `GET /api/v1/organizations/{organization_id}/dashboard/metrics`
- `GET /api/v1/organizations/{organization_id}/dashboard/snapshots`

All responses use the v1 envelope helpers. Engine key: `organization_dealer_dashboard` → `P42-09-v1`.

## Projection sources

Aggregates read from existing systems only:

- shared inventory assignments and queues
- organization reviews
- storefront public inventory visibility
- organization activity events (non-lineage)
- organization notifications
- organization memberships
- org-bound auth sessions

No duplicate writes to workflow lineage tables occur during aggregation.

## Frontend foundation

`DealerOperationsDashboardPage` renders metric cards, section summaries, and an operational timeline shell with backend-authoritative permissions. No websocket or live streaming updates are included.

## Future expansion

- scheduled snapshot refresh jobs
- forecasting and trend analytics
- AI recommendations
- cross-org benchmarking
- external reporting exports
- customizable dashboard layouts

These remain out of scope for P42-09.
