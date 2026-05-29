from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceOpsMetricDefinition:
    metric_key: str
    metric_group: str
    display_name: str
    metric_period: str = "current"


@dataclass(frozen=True)
class MarketplaceOpsDiagnosticDefinition:
    diagnostic_code: str
    diagnostic_category: str
    diagnostic_status: str
    display_name: str


MARKETPLACE_OPS_METRIC_DEFINITIONS: tuple[MarketplaceOpsMetricDefinition, ...] = (
    MarketplaceOpsMetricDefinition("connected_marketplace_accounts", "accounts", "Connected marketplace accounts"),
    MarketplaceOpsMetricDefinition("verified_marketplace_accounts", "accounts", "Verified marketplace accounts"),
    MarketplaceOpsMetricDefinition("active_listing_drafts", "listings", "Active listing drafts"),
    MarketplaceOpsMetricDefinition("ready_listing_drafts", "listings", "Ready listing drafts"),
    MarketplaceOpsMetricDefinition("invalid_listing_drafts", "listings", "Invalid listing drafts"),
    MarketplaceOpsMetricDefinition("latest_sync_run_status", "sync", "Latest sync run status"),
    MarketplaceOpsMetricDefinition("open_sync_conflicts", "sync", "Open sync conflicts"),
    MarketplaceOpsMetricDefinition("imported_orders_count", "orders", "Imported orders"),
    MarketplaceOpsMetricDefinition("pending_orders_count", "orders", "Pending orders"),
    MarketplaceOpsMetricDefinition("completed_orders_count", "orders", "Completed orders"),
    MarketplaceOpsMetricDefinition("failed_orders_count", "orders", "Failed orders"),
    MarketplaceOpsMetricDefinition("transaction_mismatches_count", "orders", "Transaction mismatches"),
    MarketplaceOpsMetricDefinition("pending_pricing_recommendations", "pricing", "Pending pricing recommendations"),
    MarketplaceOpsMetricDefinition("received_offers_count", "pricing", "Received offers"),
    MarketplaceOpsMetricDefinition("unprocessed_events_count", "events", "Unprocessed events"),
    MarketplaceOpsMetricDefinition("failed_event_processing_runs_count", "events", "Failed event processing runs"),
    MarketplaceOpsMetricDefinition("active_live_sale_sessions", "live_sales", "Active live-sale sessions"),
    MarketplaceOpsMetricDefinition("live_sale_claims_count", "live_sales", "Live-sale claims"),
)


MARKETPLACE_OPS_DIAGNOSTIC_DEFINITIONS: tuple[MarketplaceOpsDiagnosticDefinition, ...] = (
    MarketplaceOpsDiagnosticDefinition(
        "no_marketplace_accounts_connected",
        "account",
        "error",
        "No marketplace accounts are connected.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "listing_validation_failures_present",
        "listing",
        "warning",
        "Listing validation failures are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "unresolved_sync_conflicts_present",
        "sync",
        "warning",
        "Unresolved sync conflicts are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "failed_sync_runs_present",
        "sync",
        "error",
        "Failed sync runs are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "transaction_mismatches_present",
        "order",
        "warning",
        "Transaction mismatches are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "pending_offer_reviews_present",
        "pricing",
        "warning",
        "Pending offer reviews are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "failed_event_processing_runs_present",
        "event",
        "error",
        "Failed event processing runs are present.",
    ),
    MarketplaceOpsDiagnosticDefinition(
        "active_live_sale_without_queue_items",
        "live_sale",
        "warning",
        "Active live sale sessions exist without queue items.",
    ),
)


def list_marketplace_ops_metric_definitions() -> tuple[MarketplaceOpsMetricDefinition, ...]:
    return MARKETPLACE_OPS_METRIC_DEFINITIONS


def list_marketplace_ops_diagnostic_definitions() -> tuple[MarketplaceOpsDiagnosticDefinition, ...]:
    return MARKETPLACE_OPS_DIAGNOSTIC_DEFINITIONS
