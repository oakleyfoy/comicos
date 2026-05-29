from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from app.models import (
    ConventionInventoryStage,
    ConventionSession,
    IntakeStagingRecord,
    MobileDevice,
    MobileDeviceAccessLog,
    MobileSession,
    OfflineInventoryRecord,
    OfflineSyncConflict,
    OfflineSyncQueue,
    QuickSale,
    ScanCapture,
)
from app.services.convention_registry import SESSION_STATUS_ACTIVE as CONVENTION_SESSION_STATUS_ACTIVE, STAGE_STATUS_REMOVED
from app.services.mobile_device_security_registry import ACCESS_RESULT_DENIED, TRUST_STATUS_SUSPENDED
from app.services.mobile_device_security_service import _trust_state_for_device
from app.services.mobile_scan_registry import SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_STAGED, STAGING_STATUS_APPROVED
from app.services.offline_runtime_registry import DEVICE_STATUS_ACTIVE, DEVICE_STATUS_SUSPENDED, SESSION_STATUS_ACTIVE
from app.services.offline_sync_registry import CONFLICT_STATUS_OPEN, QUEUE_STATUS_PENDING
from app.services.quick_sale_registry import SALE_STATUS_COMPLETED, SALE_STATUS_VOIDED


@dataclass(frozen=True)
class MobileUsageTrendDefinition:
    trend_key: str
    trend_group: str
    display_name: str
    trend_period: str = "current"


@dataclass(frozen=True)
class MobileUsageTrendPayload:
    trend_key: str
    trend_group: str
    trend_period: str
    trend_payload_json: dict


MOBILE_USAGE_TREND_DEFINITIONS: tuple[MobileUsageTrendDefinition, ...] = (
    MobileUsageTrendDefinition("device_activity", "devices", "Device activity"),
    MobileUsageTrendDefinition("offline_activity", "offline", "Offline activity"),
    MobileUsageTrendDefinition("scanning_activity", "scanning", "Scanning activity"),
    MobileUsageTrendDefinition("convention_activity", "convention", "Convention activity"),
    MobileUsageTrendDefinition("quick_sale_activity", "quick_sales", "Quick sale activity"),
    MobileUsageTrendDefinition("security_activity", "security", "Security activity"),
)


def list_mobile_usage_trend_definitions() -> tuple[MobileUsageTrendDefinition, ...]:
    return MOBILE_USAGE_TREND_DEFINITIONS


def _decimal_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_mobile_usage_trends(session: Session, *, organization_id: int) -> list[MobileUsageTrendPayload]:
    devices = session.exec(select(MobileDevice).where(MobileDevice.organization_id == organization_id)).all()
    mobile_sessions = session.exec(select(MobileSession).where(MobileSession.organization_id == organization_id)).all()
    offline_records = session.exec(select(OfflineInventoryRecord).where(OfflineInventoryRecord.organization_id == organization_id)).all()
    sync_queue = session.exec(select(OfflineSyncQueue).where(OfflineSyncQueue.organization_id == organization_id)).all()
    sync_conflicts = session.exec(select(OfflineSyncConflict).where(OfflineSyncConflict.organization_id == organization_id)).all()
    scan_captures = session.exec(select(ScanCapture).where(ScanCapture.organization_id == organization_id)).all()
    intake_records = session.exec(select(IntakeStagingRecord).where(IntakeStagingRecord.organization_id == organization_id)).all()
    convention_sessions = session.exec(select(ConventionSession).where(ConventionSession.organization_id == organization_id)).all()
    staged_inventory = session.exec(select(ConventionInventoryStage).where(ConventionInventoryStage.organization_id == organization_id)).all()
    quick_sales = session.exec(select(QuickSale).where(QuickSale.organization_id == organization_id)).all()
    access_logs = session.exec(select(MobileDeviceAccessLog).where(MobileDeviceAccessLog.organization_id == organization_id)).all()

    trusted_devices = 0
    suspended_trust_states = 0
    for device in devices:
        trust_state = _trust_state_for_device(session, organization_id=organization_id, mobile_device_id=int(device.id or 0))
        if trust_state is not None and trust_state.trust_status == TRUST_STATUS_SUSPENDED:
            suspended_trust_states += 1
        elif trust_state is not None:
            trusted_devices += 1

    lookup_complete_count = sum(1 for row in scan_captures if row.scan_status in {SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_STAGED})
    quick_sale_total_amount = sum(
        (Decimal(str(row.total_amount)) for row in quick_sales if row.sale_status != SALE_STATUS_VOIDED),
        Decimal("0.00"),
    )
    completed_quick_sales = [row for row in quick_sales if row.sale_status == SALE_STATUS_COMPLETED]
    average_quick_sale = (
        quick_sale_total_amount / Decimal(len(completed_quick_sales))
        if completed_quick_sales
        else Decimal("0.00")
    )

    payloads: dict[str, dict] = {
        "device_activity": {
            "group": "devices",
            "points": [
                {"label": "registered_devices", "value": len(devices)},
                {"label": "active_devices", "value": sum(1 for row in devices if row.device_status == DEVICE_STATUS_ACTIVE)},
                {"label": "suspended_devices", "value": sum(1 for row in devices if row.device_status == DEVICE_STATUS_SUSPENDED)},
                {"label": "active_sessions", "value": sum(1 for row in mobile_sessions if row.session_status == SESSION_STATUS_ACTIVE)},
                {"label": "trusted_devices", "value": trusted_devices},
            ],
        },
        "offline_activity": {
            "group": "offline",
            "points": [
                {"label": "offline_records_created", "value": len(offline_records)},
                {"label": "queued_sync_operations", "value": sum(1 for row in sync_queue if row.queue_status == QUEUE_STATUS_PENDING)},
                {"label": "open_sync_conflicts", "value": sum(1 for row in sync_conflicts if row.conflict_status == CONFLICT_STATUS_OPEN)},
            ],
        },
        "scanning_activity": {
            "group": "scanning",
            "points": [
                {"label": "scans_captured", "value": len(scan_captures)},
                {"label": "lookup_complete", "value": lookup_complete_count},
                {"label": "staged_intake_records", "value": len(intake_records)},
                {"label": "approved_intake_records", "value": sum(1 for row in intake_records if row.staging_status == STAGING_STATUS_APPROVED)},
            ],
        },
        "convention_activity": {
            "group": "convention",
            "points": [
                {"label": "convention_sessions_created", "value": len(convention_sessions)},
                {"label": "active_convention_sessions", "value": sum(1 for row in convention_sessions if row.session_status == CONVENTION_SESSION_STATUS_ACTIVE)},
                {"label": "inventory_items_staged", "value": sum(1 for row in staged_inventory if row.stage_status != STAGE_STATUS_REMOVED)},
            ],
        },
        "quick_sale_activity": {
            "group": "quick_sales",
            "points": [
                {"label": "quick_sales_created", "value": len(quick_sales)},
                {"label": "completed_quick_sales", "value": len(completed_quick_sales)},
                {"label": "quick_sales_total_amount", "value": _decimal_string(quick_sale_total_amount)},
                {"label": "average_quick_sale_value", "value": _decimal_string(average_quick_sale)},
            ],
        },
        "security_activity": {
            "group": "security",
            "points": [
                {"label": "denied_mobile_access_attempts", "value": sum(1 for row in access_logs if row.access_result == ACCESS_RESULT_DENIED)},
                {"label": "suspended_device_count", "value": suspended_trust_states},
            ],
        },
    }

    return [
        MobileUsageTrendPayload(
            trend_key=definition.trend_key,
            trend_group=definition.trend_group,
            trend_period=definition.trend_period,
            trend_payload_json=payloads[definition.trend_key],
        )
        for definition in MOBILE_USAGE_TREND_DEFINITIONS
    ]
