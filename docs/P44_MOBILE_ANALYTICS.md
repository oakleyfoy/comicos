# P44-08 Mobile Analytics / Usage Metrics

P44-08 establishes deterministic mobile analytics infrastructure for ComicOS. This phase adds organization-scoped KPI rows, usage-trend snapshots, analytics snapshots, and append-only analytics lineage across device activity, offline workflows, scanning, convention operations, quick sales, and mobile security.

## Aggregation Model

Mobile analytics aggregates from the existing mobile subsystem rows without modifying workflow behavior:

- mobile devices
- mobile sessions
- offline inventory records
- offline sync queue
- offline sync conflicts
- scan captures
- intake staging records
- convention sessions
- convention inventory stages
- quick sales
- quick sale payments
- mobile ops diagnostics
- mobile device security access logs and trust states

All calculations are organization-scoped, deterministic, and replay-safe. Analytics reads existing state and writes new immutable analytics rows; it does not mutate operational workflow data.

## KPI Registry

`mobile_kpi_registry.py` centralizes KPI definitions in stable order:

- Devices:
  - `registered_devices`
  - `active_devices`
  - `suspended_devices`
  - `active_sessions`
- Offline:
  - `offline_records_created`
  - `queued_sync_operations`
  - `open_sync_conflicts`
- Scanning:
  - `scans_captured`
  - `successful_lookup_rate`
  - `staged_intake_records`
  - `approved_intake_records`
- Convention:
  - `convention_sessions_created`
  - `active_convention_sessions`
  - `inventory_items_staged`
- Quick sales:
  - `quick_sales_created`
  - `completed_quick_sales`
  - `quick_sales_total_amount`
  - `average_quick_sale_value`
- Security:
  - `denied_mobile_access_attempts`
  - `suspended_device_count`

The registry determines serialization order for generated KPI rows and current KPI views.

## Trend Engine

`mobile_usage_trends.py` generates deterministic, non-predictive trend payloads for:

- `device_activity`
- `offline_activity`
- `scanning_activity`
- `convention_activity`
- `quick_sale_activity`
- `security_activity`

Each trend row contains stable point lists derived from current subsystem state. This phase does not implement forecasting, prediction, or external telemetry.

## Analytics Lifecycle

The analytics lifecycle is append-only:

1. Generate KPI rows.
2. Generate trend rows.
3. Calculate derived performance summary values.
4. Persist a full analytics snapshot.
5. Persist analytics lineage events.

Immutable analytics events include:

- `mobile_metrics_generated`
- `mobile_trends_generated`
- `mobile_snapshot_generated`
- `mobile_performance_calculated`
- `mobile_analytics_generated`
- `unauthorized_mobile_analytics_access_attempt`

## Replay-Safe Guarantees

- All analytics timestamps are created in UTC.
- JSON payloads are normalized with stable key ordering.
- KPI and trend ordering is defined centrally by registries rather than query coincidence.
- Snapshots, metric rows, trend rows, and analytics events are append-only.
- Current dashboard views are built from the latest generated rows per key, falling back to fresh deterministic aggregation when no generated rows exist.

## Frontend Workspace

The mobile analytics workspace provides:

- KPI cards
- grouped analytics overview panels
- metric table
- trend panels
- performance summary visibility
- latest snapshot viewer
- manual analytics generation action
- append-only analytics event timeline

The UI remains backend-authoritative and uses existing project UI primitives only; no realtime telemetry or predictive charting is introduced.

## Future Optimization Dependencies

P44-08 establishes the measurement layer needed for future mobile optimization work, including:

- identifying high-friction offline workflows
- tracking scan conversion quality
- evaluating convention throughput
- measuring quick-sale efficiency
- comparing security policy impact over time

This phase does not add predictive analytics, AI recommendations, external BI integrations, or native mobile instrumentation.
