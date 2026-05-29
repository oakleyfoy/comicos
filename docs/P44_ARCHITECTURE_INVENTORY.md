# P44 Architecture Inventory

This is the file-level inventory of the P44 mobile/offline architecture.

## Backend Models

- `apps/api/app/models/mobile_foundation.py`
- `apps/api/app/models/offline_inventory.py`
- `apps/api/app/models/mobile_scanning.py`
- `apps/api/app/models/convention_mode.py`
- `apps/api/app/models/quick_sales.py`
- `apps/api/app/models/mobile_ops_dashboard.py`
- `apps/api/app/models/mobile_device_security.py`
- `apps/api/app/models/mobile_analytics.py`

## Backend Schemas

- `apps/api/app/schemas/mobile_foundation.py`
- `apps/api/app/schemas/offline_inventory.py`
- `apps/api/app/schemas/mobile_scanning.py`
- `apps/api/app/schemas/convention_mode.py`
- `apps/api/app/schemas/quick_sales.py`
- `apps/api/app/schemas/mobile_ops_dashboard.py`
- `apps/api/app/schemas/mobile_device_security.py`
- `apps/api/app/schemas/mobile_analytics.py`
- `apps/api/app/schemas/scan_api_v1.py`

## Backend Services / Registries

- `apps/api/app/services/mobile_foundation_service.py`
- `apps/api/app/services/mobile_permissions.py`
- `apps/api/app/services/offline_inventory_service.py`
- `apps/api/app/services/offline_inventory_permissions.py`
- `apps/api/app/services/offline_runtime_registry.py`
- `apps/api/app/services/offline_sync_registry.py`
- `apps/api/app/services/mobile_scanning_service.py`
- `apps/api/app/services/mobile_scanning_permissions.py`
- `apps/api/app/services/mobile_scan_registry.py`
- `apps/api/app/services/mobile_scan_upc_registry.py`
- `apps/api/app/services/convention_mode_service.py`
- `apps/api/app/services/convention_mode_permissions.py`
- `apps/api/app/services/convention_registry.py`
- `apps/api/app/services/quick_sale_service.py`
- `apps/api/app/services/quick_sale_permissions.py`
- `apps/api/app/services/quick_sale_registry.py`
- `apps/api/app/services/mobile_ops_dashboard_service.py`
- `apps/api/app/services/mobile_ops_metric_registry.py`
- `apps/api/app/services/mobile_ops_diagnostics.py`
- `apps/api/app/services/mobile_device_security_service.py`
- `apps/api/app/services/mobile_device_security_registry.py`
- `apps/api/app/services/mobile_analytics_service.py`
- `apps/api/app/services/mobile_kpi_registry.py`
- `apps/api/app/services/mobile_usage_trends.py`

## Backend APIs

- `apps/api/app/api/mobile_foundation.py`
- `apps/api/app/api/offline_inventory.py`
- `apps/api/app/api/mobile_scanning.py`
- `apps/api/app/api/convention_mode.py`
- `apps/api/app/api/quick_sales.py`
- `apps/api/app/api/mobile_ops_dashboard.py`
- `apps/api/app/api/mobile_device_security.py`
- `apps/api/app/api/mobile_analytics.py`

## Migrations

- `apps/api/alembic/versions/20260713_0131_add_mobile_foundation.py`
- `apps/api/alembic/versions/20260714_0132_add_offline_inventory_engine.py`
- `apps/api/alembic/versions/20260715_0133_add_mobile_scanning.py`
- `apps/api/alembic/versions/20260716_0134_add_convention_mode.py`
- `apps/api/alembic/versions/20260717_0135_add_quick_sales.py`
- `apps/api/alembic/versions/20260718_0136_add_mobile_ops_dashboard.py`
- `apps/api/alembic/versions/20260719_0137_add_mobile_device_security.py`
- `apps/api/alembic/versions/20260720_0138_add_mobile_analytics.py`

## Backend Tests

- `apps/api/tests/test_mobile_foundation.py`
- `apps/api/tests/test_offline_inventory.py`
- `apps/api/tests/test_mobile_scanning.py`
- `apps/api/tests/test_convention_mode.py`
- `apps/api/tests/test_quick_sales.py`
- `apps/api/tests/test_mobile_ops_dashboard.py`
- `apps/api/tests/test_mobile_device_security.py`
- `apps/api/tests/test_mobile_analytics.py`
- `apps/api/tests/test_p44_regression.py`

## Frontend Pages

- `apps/web/src/pages/MobileFoundationPage.tsx`
- `apps/web/src/pages/OfflineInventoryPage.tsx`
- `apps/web/src/pages/MobileScanningPage.tsx`
- `apps/web/src/pages/ConventionModePage.tsx`
- `apps/web/src/pages/QuickSalesPage.tsx`
- `apps/web/src/pages/MobileOpsDashboardPage.tsx`
- `apps/web/src/pages/MobileDeviceSecurityPage.tsx`
- `apps/web/src/pages/MobileAnalyticsPage.tsx`

## Frontend Component Areas

- `apps/web/src/components/mobile/`
  - `offline/`
  - `quick-sales/`
  - `ops/`
  - `security/`
  - `analytics/`

## P44 Documentation

- `docs/P44_MOBILE_FOUNDATION.md`
- `docs/P44_OFFLINE_INVENTORY_ENGINE.md`
- `docs/P44_MOBILE_SCANNING.md`
- `docs/P44_CONVENTION_MODE.md`
- `docs/P44_QUICK_SALES.md`
- `docs/P44_MOBILE_OPS_DASHBOARD.md`
- `docs/P44_DEVICE_SECURITY.md`
- `docs/P44_MOBILE_ANALYTICS.md`
- `docs/P44_ARCHITECTURE_INDEX.md`
- `docs/P44_DEPENDENCY_GRAPH.md`
- `docs/P44_OPERATIONS_GUIDE.md`
- `docs/P44_API_REFERENCE.md`
- `docs/P44_DETERMINISM_GUARANTEES.md`
- `docs/P44_PRODUCTION_READINESS.md`
- `docs/P44_FUTURE_INTEGRATION_MAP.md`
- `docs/P44_ARCHITECTURE_INVENTORY.md`
- `docs/P44_CLOSEOUT_SUMMARY.md`
- `docs/P44_HARDENING_REPORT.md`
