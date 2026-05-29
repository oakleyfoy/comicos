# P43 Architecture Inventory

## Purpose

This inventory lists the principal P43 implementation files by subsystem. It is intended as the authoritative file-level map for the completed marketplace platform layer.

## Backend Models

### Marketplace Accounts

- `apps/api/app/models/marketplace_accounts.py`
- `apps/api/alembic/versions/20260703_0121_add_marketplace_account_foundation.py`

### Marketplace Listings

- `apps/api/app/models/marketplace_listings.py`
- `apps/api/alembic/versions/20260704_0122_add_marketplace_listing_engine.py`

### Inventory Sync

- `apps/api/app/models/marketplace_inventory_sync.py`
- `apps/api/alembic/versions/20260705_0123_add_marketplace_inventory_sync.py`

### Orders / Transactions

- `apps/api/app/models/marketplace_orders.py`
- `apps/api/alembic/versions/20260706_0124_add_marketplace_order_ingestion.py`

### Pricing / Offers

- `apps/api/app/models/marketplace_pricing.py`
- `apps/api/alembic/versions/20260707_0125_add_marketplace_pricing_engine.py`

### Events

- `apps/api/app/models/marketplace_events.py`
- `apps/api/alembic/versions/20260708_0126_add_marketplace_events.py`

### Live Sales

- `apps/api/app/models/live_sales.py`
- `apps/api/alembic/versions/20260709_0127_add_live_sale_workflows.py`

### Shopify Sync

- `apps/api/app/models/shopify_sync.py`
- `apps/api/alembic/versions/20260710_0128_add_shopify_sync_layer.py`

### Ops Dashboard

- `apps/api/app/models/marketplace_ops_dashboard.py`
- `apps/api/alembic/versions/20260711_0129_add_marketplace_ops_dashboard.py`

### Analytics

- `apps/api/app/models/marketplace_analytics.py`
- `apps/api/alembic/versions/20260712_0130_add_marketplace_analytics.py`

## Backend Services

### Shared Foundation

- `apps/api/app/services/marketplace_registry.py`
- `apps/api/app/services/marketplace_account_service.py`

### Listings and Validation

- `apps/api/app/services/marketplace_listing_service.py`
- `apps/api/app/services/marketplace_listing_validation.py`
- `apps/api/app/services/marketplace_listing_projection.py`

### Inventory Sync

- `apps/api/app/services/marketplace_inventory_sync_service.py`
- `apps/api/app/services/marketplace_inventory_reconciliation.py`
- `apps/api/app/services/marketplace_inventory_projection.py`

### Orders

- `apps/api/app/services/marketplace_order_service.py`
- `apps/api/app/services/marketplace_order_ingestion.py`
- `apps/api/app/services/marketplace_transaction_reconciliation.py`

### Pricing

- `apps/api/app/services/marketplace_pricing_service.py`
- `apps/api/app/services/marketplace_pricing_rules.py`
- `apps/api/app/services/marketplace_offer_service.py`

### Events

- `apps/api/app/services/marketplace_event_processing.py`
- `apps/api/app/services/marketplace_event_registry.py`
- `apps/api/app/services/marketplace_event_validation.py`

### Live Sales

- `apps/api/app/services/live_sale_workflow_service.py`
- `apps/api/app/services/live_sale_queue_service.py`
- `apps/api/app/services/live_sale_claim_service.py`

### Shopify

- `apps/api/app/services/shopify_sync_service.py`
- `apps/api/app/services/shopify_mapping_service.py`

### Ops

- `apps/api/app/services/marketplace_ops_registry.py`
- `apps/api/app/services/marketplace_ops_dashboard_service.py`
- `apps/api/app/services/marketplace_ops_diagnostics.py`

### Analytics

- `apps/api/app/services/marketplace_kpi_registry.py`
- `apps/api/app/services/marketplace_trends.py`
- `apps/api/app/services/marketplace_analytics_service.py`

## Backend APIs

- `apps/api/app/api/marketplace_accounts.py`
- `apps/api/app/api/marketplace_listings.py`
- `apps/api/app/api/marketplace_inventory_sync.py`
- `apps/api/app/api/marketplace_orders.py`
- `apps/api/app/api/marketplace_pricing.py`
- `apps/api/app/api/marketplace_events.py`
- `apps/api/app/api/live_sales.py`
- `apps/api/app/api/shopify_sync.py`
- `apps/api/app/api/marketplace_ops_dashboard.py`
- `apps/api/app/api/marketplace_analytics.py`

## Frontend Pages

- `apps/web/src/pages/MarketplaceAccountsPage.tsx`
- `apps/web/src/pages/MarketplaceListingsPage.tsx`
- `apps/web/src/pages/MarketplaceInventorySyncPage.tsx`
- `apps/web/src/pages/MarketplaceOrdersPage.tsx`
- `apps/web/src/pages/MarketplacePricingPage.tsx`
- `apps/web/src/pages/MarketplaceEventsPage.tsx`
- `apps/web/src/pages/LiveSalesPage.tsx`
- `apps/web/src/pages/ShopifySyncPage.tsx`
- `apps/web/src/pages/MarketplaceOpsDashboardPage.tsx`
- `apps/web/src/pages/MarketplaceAnalyticsPage.tsx`

## Frontend Components

### Marketplace Accounts

- `apps/web/src/components/marketplaces/MarketplaceAccountListPanel.tsx`
- `apps/web/src/components/marketplaces/MarketplaceAccountStatusBadge.tsx`
- `apps/web/src/components/marketplaces/MarketplaceConnectionShell.tsx`
- `apps/web/src/components/marketplaces/MarketplaceVerificationStatusBadge.tsx`

### Marketplace Listings

- `apps/web/src/components/marketplaces/listings/MarketplaceListingDetailPanel.tsx`
- `apps/web/src/components/marketplaces/listings/MarketplaceListingDraftForm.tsx`
- `apps/web/src/components/marketplaces/listings/MarketplaceListingDraftTable.tsx`
- `apps/web/src/components/marketplaces/listings/MarketplaceListingProjectionPreview.tsx`
- `apps/web/src/components/marketplaces/listings/MarketplaceListingStatusBadge.tsx`
- `apps/web/src/components/marketplaces/listings/MarketplaceListingValidationErrors.tsx`

### Inventory Sync

- `apps/web/src/components/organizations/inventory/OrganizationSharedInventoryListPanel.tsx`

### Ops

- `apps/web/src/components/marketplaces/ops/MarketplaceOpsStatusBadge.tsx`
- `apps/web/src/components/marketplaces/ops/MarketplaceOpsMetricCards.tsx`
- `apps/web/src/components/marketplaces/ops/MarketplaceOpsSummaryPanels.tsx`
- `apps/web/src/components/marketplaces/ops/MarketplaceOpsDiagnosticsPanel.tsx`
- `apps/web/src/components/marketplaces/ops/MarketplaceOpsSnapshotPanel.tsx`
- `apps/web/src/components/marketplaces/ops/MarketplaceOpsEventTimelineShell.tsx`

### Analytics

- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsStatusBadge.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsKpiCards.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsSummaryCards.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsTrendPanels.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsSnapshotPanel.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsEventTimelineShell.tsx`
- `apps/web/src/components/marketplaces/analytics/MarketplaceAnalyticsMetricTable.tsx`

## Tests

- `apps/api/tests/test_marketplace_accounts.py`
- `apps/api/tests/test_marketplace_listings.py`
- `apps/api/tests/test_marketplace_inventory_sync.py`
- `apps/api/tests/test_marketplace_orders.py`
- `apps/api/tests/test_marketplace_pricing.py`
- `apps/api/tests/test_marketplace_events.py`
- `apps/api/tests/test_live_sales.py`
- `apps/api/tests/test_shopify_sync.py`
- `apps/api/tests/test_marketplace_ops.py`
- `apps/api/tests/test_marketplace_analytics.py`
- `apps/api/tests/test_p43_regression.py`

## Documentation

- `docs/P43_MARKETPLACE_ACCOUNT_ARCHITECTURE.md`
- `docs/P43_MARKETPLACE_LISTING_ENGINE.md`
- `docs/P43_MARKETPLACE_INVENTORY_SYNC.md`
- `docs/P43_MARKETPLACE_ORDER_INGESTION.md`
- `docs/P43_MARKETPLACE_PRICING_ENGINE.md`
- `docs/P43_WEBHOOK_EVENT_PROCESSING.md`
- `docs/P43_WHATNOT_LIVE_SALE_WORKFLOWS.md`
- `docs/P43_SHOPIFY_SYNC_LAYER.md`
- `docs/P43_MARKETPLACE_OPS_DASHBOARD.md`
- `docs/P43_MARKETPLACE_ANALYTICS.md`
- `docs/P43_HARDENING_REPORT.md`
- `docs/P43_ARCHITECTURE_INDEX.md`
- `docs/P43_DEPENDENCY_GRAPH.md`
- `docs/P43_OPERATIONS_GUIDE.md`
- `docs/P43_API_REFERENCE.md`
- `docs/P43_DETERMINISM_GUARANTEES.md`
- `docs/P43_PRODUCTION_READINESS.md`
- `docs/P43_FUTURE_INTEGRATION_MAP.md`
- `docs/P43_CLOSEOUT_SUMMARY.md`

## Inventory Notes

- The inventory is organized by subsystem rather than by build artifact type.
- File-level references are intentionally stable and should be updated only when the underlying implementation changes.
- P43-11 hardening and the closeout docs complete the platform freeze point for the current layer.
