# P44 Determinism Guarantees

P44 was built around deterministic, replay-safe, organization-scoped behavior. This document captures the guarantees validated during closeout.

## Ordering Guarantees

P44 list and lineage reads use stable ordering rules:

- current-state tables: primary business timestamp plus `id`
- lineage tables: append order via `(created_at, id)`
- snapshots and generated aggregates: newest-first where the UI needs latest state, otherwise explicit registry order
- registry-backed rows: centralized definition order, not incidental query order

Examples:

- devices: `(created_at, id)`
- sessions: `(started_at, id)`
- offline records: `(created_at, id)`
- scan captures: `(created_at, id)`
- convention sessions: `(created_at, id)`
- quick sales: `(created_at, id)`
- access logs: `(accessed_at, id)`
- analytics metrics: KPI registry order
- analytics trends: trend registry order

## Replay-Safe Lineage

The following P44 event families are append-only and never updated in place:

- `MobileFoundationEvent`
- `OfflineInventoryEvent`
- `ScanEvent`
- `ConventionModeEvent`
- `QuickSaleEvent`
- `MobileOpsEvent`
- `MobileDeviceSecurityEvent`
- `MobileAnalyticsEvent`

Generated dashboards and analytics append rows instead of replacing history:

- `MobileOpsMetric`
- `MobileOpsDiagnostic`
- `MobileOpsSnapshot`
- `MobileUsageMetric`
- `MobileUsageTrend`
- `MobileAnalyticsSnapshot`

## Stable Serialization

JSON payloads are normalized before persistence:

- keys are stringified
- dictionary keys are sorted deterministically
- decimals are serialized consistently
- timestamps are emitted in UTC

This prevents replay drift caused by map ordering or inconsistent value formatting.

## Organization Isolation

Every P44 subsystem validates organization ownership before reads or writes. Denied attempts produce explicit unauthorized lineage events instead of silent failure.

Isolation is enforced for:

- device registry and sessions
- offline records, queue items, and conflicts
- scan captures and staging rows
- convention sessions, booths, and staged inventory
- quick sales and related rows
- mobile ops visibility
- mobile security visibility and management
- mobile analytics visibility and generation

## Security-Driven Determinism

P44-07 adds deterministic access control to device-aware write paths:

- suspended devices are denied
- trusted-device enforcement is policy-driven
- active-session enforcement is policy-driven
- access decisions write append-only logs and events

## Internal-Only Boundary

P44 determinism also depends on the absence of uncontrolled external side effects. Closeout validation confirmed no P44 runtime path introduces:

- payment gateway capture
- marketplace mutation
- shipping-provider execution
- push delivery
- native mobile SDK calls
