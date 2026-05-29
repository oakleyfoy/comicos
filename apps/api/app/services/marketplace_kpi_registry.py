from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceKpiDefinition:
    metric_key: str
    metric_group: str
    display_name: str
    metric_period: str = "current"


MARKETPLACE_KPI_DEFINITIONS: tuple[MarketplaceKpiDefinition, ...] = (
    MarketplaceKpiDefinition("connected_accounts", "accounts", "Connected accounts"),
    MarketplaceKpiDefinition("total_listing_drafts", "listings", "Total listing drafts"),
    MarketplaceKpiDefinition("ready_listing_drafts", "listings", "Ready listing drafts"),
    MarketplaceKpiDefinition("listing_validation_rate", "listings", "Listing validation rate"),
    MarketplaceKpiDefinition("imported_orders", "orders", "Imported orders"),
    MarketplaceKpiDefinition("total_sales_amount", "orders", "Total sales amount"),
    MarketplaceKpiDefinition("average_order_value", "orders", "Average order value"),
    MarketplaceKpiDefinition("total_transaction_volume", "transactions", "Total transaction volume"),
    MarketplaceKpiDefinition("reconciliation_success_rate", "transactions", "Reconciliation success rate"),
    MarketplaceKpiDefinition("recommendations_generated", "pricing", "Recommendations generated"),
    MarketplaceKpiDefinition("reviewed_recommendations", "pricing", "Reviewed recommendations"),
    MarketplaceKpiDefinition("received_offers", "pricing", "Received offers"),
    MarketplaceKpiDefinition("processed_events", "events", "Processed events"),
    MarketplaceKpiDefinition("duplicate_event_rate", "events", "Duplicate event rate"),
    MarketplaceKpiDefinition("total_live_sale_sessions", "live_sales", "Total live sale sessions"),
    MarketplaceKpiDefinition("sold_live_sale_items", "live_sales", "Sold live sale items"),
    MarketplaceKpiDefinition("claim_conversion_rate", "live_sales", "Claim conversion rate"),
    MarketplaceKpiDefinition("mapped_products", "shopify", "Mapped products"),
    MarketplaceKpiDefinition("valid_product_mappings", "shopify", "Valid product mappings"),
)


def list_marketplace_kpi_definitions() -> tuple[MarketplaceKpiDefinition, ...]:
    return MARKETPLACE_KPI_DEFINITIONS
