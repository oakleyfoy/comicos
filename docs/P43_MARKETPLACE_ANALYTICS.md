# P43-10 Marketplace Analytics

P43-10 adds deterministic marketplace analytics and performance infrastructure for ComicOS organizations.

## Scope

This phase provides:

- marketplace analytics snapshots
- KPI generation
- performance trend generation
- org-scoped analytics lineage
- deterministic reporting dependencies for future work

This phase does not:

- perform predictive analytics
- use AI forecasting
- create external reports
- integrate BI tools
- add alerting systems
- perform automatic optimization
- call marketplace APIs
- modify marketplace data

## Data Model

The analytics layer stores immutable history in four tables:

- `MarketplaceAnalyticsSnapshot`
- `MarketplaceMetric`
- `MarketplacePerformanceTrend`
- `MarketplaceAnalyticsEvent`

Snapshots capture the generated analytics payload. Metrics and trends are append-only so dashboards and reports can be replayed from history.

## KPI Registry

KPIs are defined centrally and emitted in a stable order.

Groups:

- `accounts`
- `listings`
- `orders`
- `transactions`
- `pricing`
- `events`
- `live_sales`
- `shopify`

Representative KPIs:

- `connected_accounts`
- `total_listing_drafts`
- `ready_listing_drafts`
- `listing_validation_rate`
- `imported_orders`
- `total_sales_amount`
- `average_order_value`
- `total_transaction_volume`
- `reconciliation_success_rate`
- `recommendations_generated`
- `reviewed_recommendations`
- `received_offers`
- `processed_events`
- `duplicate_event_rate`
- `total_live_sale_sessions`
- `sold_live_sale_items`
- `claim_conversion_rate`
- `mapped_products`
- `valid_product_mappings`

## Trend Engine

Trend generation is deterministic and replay-safe. Current trend groups:

- `listing_growth`
- `order_growth`
- `sales_growth`
- `recommendation_activity`
- `event_processing_activity`
- `live_sale_activity`
- `storefront_activity`

Trends use fixed time windows and stable JSON serialization. They do not forecast future outcomes.

## Lifecycle

The analytics dashboard can be read directly, and the generate action persists a snapshot alongside KPI and trend lineage. The dashboard layer records:

- `marketplace_analytics_generated`
- `marketplace_metrics_generated`
- `marketplace_trends_generated`
- `marketplace_performance_calculated`
- `marketplace_snapshot_generated`
- `unauthorized_marketplace_analytics_access_attempt`

## Future Reporting Dependencies

Later phases can build on this foundation for:

- scheduled reporting jobs
- external reporting exports
- business intelligence integrations

Those are intentionally out of scope for P43-10.
