# P44 Operations Guide

This guide describes how to operate the completed P44 mobile/offline layer from the current web-administered surface.

## Operational Areas

### Mobile foundation

Use `MobileFoundationPage` to:

- register mobile devices
- start mobile sessions
- create offline sync contracts
- inspect recent foundation lineage

### Offline inventory

Use `OfflineInventoryPage` to:

- create offline inventory records
- inspect sync queue items
- inspect sync conflicts
- review offline lineage

### Mobile scanning

Use `MobileScanningPage` to:

- capture scans against a registered device
- inspect lookup results
- create intake staging rows
- approve or archive staging rows

### Convention mode

Use `ConventionModePage` to:

- create convention sessions
- open booths
- stage inventory for a session
- remove staged inventory

### Quick sales

Use `QuickSalesPage` to:

- create internal quick sales
- add/remove line items
- record internal payment rows
- complete or void sales

### Mobile ops

Use `MobileOpsDashboardPage` to:

- inspect current subsystem visibility
- generate fresh metrics/diagnostics/snapshots
- review latest ops lineage

### Mobile security

Use `MobileDeviceSecurityPage` to:

- assign trust state rows
- suspend and unsuspend devices
- create and toggle security policies
- inspect access logs and security events

### Mobile analytics

Use `MobileAnalyticsPage` to:

- inspect current KPI and trend state
- generate fresh analytics rows and snapshots
- review analytics lineage

## Operating Rules

- All P44 operations are organization-scoped.
- Device-aware write paths require device ownership plus any active security policy checks.
- Current-state rows may update where explicitly modeled, but lineage is append-only.
- Dashboards and analytics are generated on demand; no scheduled jobs were introduced in P44.

## Recommended Operator Flow

1. Register a device in mobile foundation.
2. Start a device session.
3. Create any needed offline sync contracts.
4. Use offline inventory, scanning, convention, or quick-sale workflows.
5. Use mobile security to enforce trust or suspension where needed.
6. Use mobile ops for operational health visibility.
7. Use mobile analytics for KPI and trend snapshots.

## Recovery / Review

- Inspect lineage tables and timeline panels before attempting corrective actions.
- Use deny-by-default errors as signals of org, session, or device-security mismatch.
- Regenerate mobile ops and mobile analytics after notable workflow changes when updated visibility is required.

## Explicit Non-Goals

This operations guide does not cover:

- native app distribution
- barcode camera integration
- external payment processing
- marketplace publishing or mutation
- push notifications
- predictive optimization
