from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MobileKpiDefinition:
    metric_key: str
    metric_group: str
    display_name: str
    metric_period: str = "current"


MOBILE_KPI_DEFINITIONS: tuple[MobileKpiDefinition, ...] = (
    MobileKpiDefinition("registered_devices", "devices", "Registered devices"),
    MobileKpiDefinition("active_devices", "devices", "Active devices"),
    MobileKpiDefinition("suspended_devices", "devices", "Suspended devices"),
    MobileKpiDefinition("active_sessions", "devices", "Active sessions"),
    MobileKpiDefinition("offline_records_created", "offline", "Offline records created"),
    MobileKpiDefinition("queued_sync_operations", "offline", "Queued sync operations"),
    MobileKpiDefinition("open_sync_conflicts", "offline", "Open sync conflicts"),
    MobileKpiDefinition("scans_captured", "scanning", "Scans captured"),
    MobileKpiDefinition("successful_lookup_rate", "scanning", "Successful lookup rate"),
    MobileKpiDefinition("staged_intake_records", "scanning", "Staged intake records"),
    MobileKpiDefinition("approved_intake_records", "scanning", "Approved intake records"),
    MobileKpiDefinition("convention_sessions_created", "convention", "Convention sessions created"),
    MobileKpiDefinition("active_convention_sessions", "convention", "Active convention sessions"),
    MobileKpiDefinition("inventory_items_staged", "convention", "Inventory items staged"),
    MobileKpiDefinition("quick_sales_created", "quick_sales", "Quick sales created"),
    MobileKpiDefinition("completed_quick_sales", "quick_sales", "Completed quick sales"),
    MobileKpiDefinition("quick_sales_total_amount", "quick_sales", "Quick sales total amount"),
    MobileKpiDefinition("average_quick_sale_value", "quick_sales", "Average quick sale value"),
    MobileKpiDefinition("denied_mobile_access_attempts", "security", "Denied mobile access attempts"),
    MobileKpiDefinition("suspended_device_count", "security", "Suspended device count"),
)


def list_mobile_kpi_definitions() -> tuple[MobileKpiDefinition, ...]:
    return MOBILE_KPI_DEFINITIONS
