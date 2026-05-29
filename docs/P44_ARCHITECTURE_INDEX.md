# P44 Architecture Index

P44 establishes the ComicOS mobile and offline operations layer across nine tightly-scoped phases. This index is the top-level map for the finished architecture and points to the phase-level documents and the final closeout package.

## Phase Index

- `P44-01` Mobile foundation
  - `docs/P44_MOBILE_FOUNDATION.md`
- `P44-02` Offline inventory engine
  - `docs/P44_OFFLINE_INVENTORY_ENGINE.md`
- `P44-03` Mobile scanning
  - `docs/P44_MOBILE_SCANNING.md`
- `P44-04` Convention mode
  - `docs/P44_CONVENTION_MODE.md`
- `P44-05` Quick sales
  - `docs/P44_QUICK_SALES.md`
- `P44-06` Mobile ops dashboard
  - `docs/P44_MOBILE_OPS_DASHBOARD.md`
- `P44-07` Device management / security
  - `docs/P44_DEVICE_SECURITY.md`
- `P44-08` Mobile analytics
  - `docs/P44_MOBILE_ANALYTICS.md`
- `P44-09` Hardening / closeout
  - this document set

## Runtime Layers

### Core runtime

- `apps/api/app/api/mobile_foundation.py`
- `apps/api/app/services/mobile_foundation_service.py`
- `apps/api/app/models/mobile_foundation.py`

### Offline engine

- `apps/api/app/api/offline_inventory.py`
- `apps/api/app/services/offline_inventory_service.py`
- `apps/api/app/models/offline_inventory.py`

### Scanning

- `apps/api/app/api/mobile_scanning.py`
- `apps/api/app/services/mobile_scanning_service.py`
- `apps/api/app/models/mobile_scanning.py`

### Convention operations

- `apps/api/app/api/convention_mode.py`
- `apps/api/app/services/convention_mode_service.py`
- `apps/api/app/models/convention_mode.py`

### Transactions

- `apps/api/app/api/quick_sales.py`
- `apps/api/app/services/quick_sale_service.py`
- `apps/api/app/models/quick_sales.py`

### Visibility / control planes

- `apps/api/app/api/mobile_ops_dashboard.py`
- `apps/api/app/services/mobile_ops_dashboard_service.py`
- `apps/api/app/models/mobile_ops_dashboard.py`
- `apps/api/app/api/mobile_device_security.py`
- `apps/api/app/services/mobile_device_security_service.py`
- `apps/api/app/models/mobile_device_security.py`
- `apps/api/app/api/mobile_analytics.py`
- `apps/api/app/services/mobile_analytics_service.py`
- `apps/api/app/models/mobile_analytics.py`

## Frontend Workspaces

- `apps/web/src/pages/MobileFoundationPage.tsx`
- `apps/web/src/pages/OfflineInventoryPage.tsx`
- `apps/web/src/pages/MobileScanningPage.tsx`
- `apps/web/src/pages/ConventionModePage.tsx`
- `apps/web/src/pages/QuickSalesPage.tsx`
- `apps/web/src/pages/MobileOpsDashboardPage.tsx`
- `apps/web/src/pages/MobileDeviceSecurityPage.tsx`
- `apps/web/src/pages/MobileAnalyticsPage.tsx`

## Closeout Package

- `docs/P44_DEPENDENCY_GRAPH.md`
- `docs/P44_OPERATIONS_GUIDE.md`
- `docs/P44_API_REFERENCE.md`
- `docs/P44_DETERMINISM_GUARANTEES.md`
- `docs/P44_PRODUCTION_READINESS.md`
- `docs/P44_FUTURE_INTEGRATION_MAP.md`
- `docs/P44_ARCHITECTURE_INVENTORY.md`
- `docs/P44_CLOSEOUT_SUMMARY.md`
- `docs/P44_HARDENING_REPORT.md`

## Freeze Point

P44 is frozen as an internal-only, web-administered, backend-authoritative mobile/offline operations layer. It does not include native apps, camera integration, payment gateway processing, marketplace mutation, push delivery, or predictive analytics.
