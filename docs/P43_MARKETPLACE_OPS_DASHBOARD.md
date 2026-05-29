# P43-09 Marketplace Ops Dashboard

P43-09 adds deterministic, org-scoped marketplace operations visibility for ComicOS without introducing any external marketplace calls or remediation automation.

## Scope

This phase provides:

- marketplace ops dashboard summaries
- marketplace metric snapshots
- marketplace diagnostics generation
- replay-safe ops lineage events
- deterministic frontend views for ops health

This phase does not:

- call external marketplace APIs
- auto-fix marketplace issues
- retry failed marketplace jobs
- modify inventory or listings automatically
- host live webhook endpoints
- add alerting or forecasting

## Data Model

The ops layer stores append-only history in four tables:

- `MarketplaceOpsSnapshot`
- `MarketplaceOpsMetric`
- `MarketplaceOpsDiagnostic`
- `MarketplaceOpsEvent`

Snapshots capture a deterministic JSON payload for a given dashboard generation. Metrics and diagnostics are also append-only so the current dashboard can be rebuilt from history without mutating earlier rows.

## Metric Registry

Metrics are defined centrally and emitted in a stable order:

- `accounts`
- `listings`
- `sync`
- `orders`
- `pricing`
- `events`
- `live_sales`

Representative metrics include:

- `connected_marketplace_accounts`
- `ready_listing_drafts`
- `latest_sync_run_status`
- `open_sync_conflicts`
- `imported_orders_count`
- `pending_pricing_recommendations`
- `received_offers_count`
- `unprocessed_events_count`
- `active_live_sale_sessions`

## Diagnostics Rules

Diagnostics are generated deterministically from org-scoped marketplace data and ordered by a fixed registry. Current rules include:

- `no_marketplace_accounts_connected`
- `listing_validation_failures_present`
- `unresolved_sync_conflicts_present`
- `failed_sync_runs_present`
- `transaction_mismatches_present`
- `pending_offer_reviews_present`
- `failed_event_processing_runs_present`
- `active_live_sale_without_queue_items`

Diagnostics are read-only visibility signals. They are not auto-resolved by the dashboard layer.

## Dashboard Lifecycle

The dashboard endpoint returns:

- backend-authoritative permissions
- summary panels by marketplace area
- current metric cards
- current diagnostics
- recent snapshots
- a short ops event timeline

Manual actions can generate diagnostics and snapshots, which write lineage events in addition to the persisted rows.

## Replay-Safe Lineage

The ops event stream is append-only and records:

- `marketplace_ops_dashboard_accessed`
- `marketplace_ops_metrics_generated`
- `marketplace_ops_diagnostics_generated`
- `marketplace_ops_snapshot_generated`
- `marketplace_ops_diagnostic_created`
- `unauthorized_marketplace_ops_access_attempt`

The design keeps history immutable so dashboard state can be audited and replayed without destructive updates.

## Future Work

Later phases can layer on:

- background scheduled generation
- alert routing
- notification escalation
- richer monitoring integrations

Those integrations are intentionally out of scope for P43-09.
