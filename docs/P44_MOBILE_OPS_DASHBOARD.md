# P44-06 — Mobile Ops Dashboard

P44-06 establishes ComicOS's organization-scoped mobile operations dashboard. It aggregates mobile foundation, offline inventory, scanning, convention mode, and quick-sale activity into deterministic summaries, metric snapshots, diagnostic rows, and append-only mobile ops lineage.

## Aggregation model

The dashboard reads from existing P44 subsystem tables:

- `mobile_devices`
- `mobile_sessions`
- `offline_sync_contracts`
- `offline_inventory_records`
- `offline_sync_queue`
- `offline_sync_conflicts`
- `scan_captures`
- `intake_staging_records`
- `convention_sessions`
- `convention_booths`
- `convention_inventory_stages`
- `quick_sales`
- `quick_sale_payments`

No scheduled jobs are introduced in this phase. Dashboard state is generated on demand and persisted as immutable metrics, diagnostics, snapshots, and events.

## Metric registry

Metrics are centralized in `mobile_ops_metric_registry.py` and emitted in a fixed order:

- Devices: `active_mobile_devices`, `inactive_mobile_devices`, `active_mobile_sessions`
- Offline: `offline_inventory_records`, `pending_sync_queue_items`, `open_sync_conflicts`
- Scanning: `scan_captures_count`, `pending_intake_staging_records`, `approved_intake_staging_records`
- Convention: `active_convention_sessions`, `staged_convention_inventory`, `active_booths`
- Quick sales: `quick_sales_count`, `completed_quick_sales_count`, `quick_sales_total_amount`, `recorded_external_payments_count`

Each generated metric row is append-only. Current dashboard metric state is derived by taking the latest row per `metric_key`.

## Diagnostic rules

Diagnostics are generated deterministically from fixed rules:

- `no_active_mobile_devices`
- `open_sync_conflicts_present`
- `pending_sync_queue_items_present`
- `pending_intake_records_present`
- `active_convention_without_booth`
- `completed_sales_without_payment_record`

Categories:

- `devices`
- `offline`
- `scanning`
- `convention`
- `quick_sales`

Statuses:

- `ok`
- `warning`
- `error`

Diagnostic rows are not auto-resolved in P44-06.

## Dashboard lifecycle

1. `GET /mobile-ops` computes the current summary and records `mobile_ops_dashboard_accessed`
2. `POST /mobile-ops/generate` generates:
   - metrics
   - diagnostics
   - a full dashboard snapshot
3. `GET /mobile-ops/metrics`, `/diagnostics`, and `/snapshots` expose the current/latest deterministic view

## Replay-safe guarantees

- Append-only `MobileOpsEvent` lineage
- Immutable metric and diagnostic history
- Immutable dashboard snapshots
- Deterministic ordering by registry/rule order and `(created_at, id)` tiebreaks
- Stable JSON serialization for metric, diagnostic, event, and snapshot payloads
- Explicit organization-scoped permission enforcement

## Future dependencies

P44-06 intentionally stops at operational visibility. Later phases can build on this foundation for:

- mobile trend analytics
- operator scorecards
- anomaly clustering
- forecast-style mobile reporting

without changing the replay-safe dashboard lineage introduced here.
