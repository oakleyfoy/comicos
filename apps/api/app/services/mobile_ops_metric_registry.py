from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MobileOpsMetricDefinition:
    metric_key: str
    metric_group: str
    display_name: str
    metric_period: str = "current"


MOBILE_OPS_METRIC_DEFINITIONS: tuple[MobileOpsMetricDefinition, ...] = (
    MobileOpsMetricDefinition("active_mobile_devices", "devices", "Active mobile devices"),
    MobileOpsMetricDefinition("inactive_mobile_devices", "devices", "Inactive mobile devices"),
    MobileOpsMetricDefinition("active_mobile_sessions", "devices", "Active mobile sessions"),
    MobileOpsMetricDefinition("offline_inventory_records", "offline", "Offline inventory records"),
    MobileOpsMetricDefinition("pending_sync_queue_items", "offline", "Pending sync queue items"),
    MobileOpsMetricDefinition("open_sync_conflicts", "offline", "Open sync conflicts"),
    MobileOpsMetricDefinition("scan_captures_count", "scanning", "Scan captures"),
    MobileOpsMetricDefinition("pending_intake_staging_records", "scanning", "Pending intake staging"),
    MobileOpsMetricDefinition("approved_intake_staging_records", "scanning", "Approved intake staging"),
    MobileOpsMetricDefinition("active_convention_sessions", "convention", "Active convention sessions"),
    MobileOpsMetricDefinition("staged_convention_inventory", "convention", "Staged convention inventory"),
    MobileOpsMetricDefinition("active_booths", "convention", "Active booths"),
    MobileOpsMetricDefinition("quick_sales_count", "quick_sales", "Quick sales"),
    MobileOpsMetricDefinition("completed_quick_sales_count", "quick_sales", "Completed quick sales"),
    MobileOpsMetricDefinition("quick_sales_total_amount", "quick_sales", "Quick sales total amount"),
    MobileOpsMetricDefinition("recorded_external_payments_count", "quick_sales", "Recorded external payments"),
)


def list_mobile_ops_metric_definitions() -> tuple[MobileOpsMetricDefinition, ...]:
    return MOBILE_OPS_METRIC_DEFINITIONS
