from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session, select

from app.models import (
    ConventionBooth,
    ConventionSession,
    IntakeStagingRecord,
    MobileDevice,
    OfflineSyncConflict,
    OfflineSyncQueue,
    QuickSale,
    QuickSalePayment,
)
from app.models.mobile_ops_dashboard import MobileOpsDiagnostic
from app.services.convention_registry import BOOTH_STATUS_CLOSED, SESSION_STATUS_ACTIVE as CONVENTION_SESSION_STATUS_ACTIVE
from app.services.mobile_scan_registry import STAGING_STATUS_PENDING
from app.services.offline_runtime_registry import DEVICE_STATUS_ACTIVE
from app.services.offline_sync_registry import CONFLICT_STATUS_OPEN, QUEUE_STATUS_PENDING
from app.services.quick_sale_registry import PAYMENT_STATUS_RECORDED, SALE_STATUS_COMPLETED


@dataclass(frozen=True)
class MobileOpsDiagnosticResult:
    diagnostic_category: str
    diagnostic_status: str
    diagnostic_code: str
    diagnostic_message: str
    diagnostic_payload_json: dict[str, Any]


@dataclass(frozen=True)
class MobileOpsDiagnosticDefinition:
    diagnostic_code: str
    diagnostic_category: str
    diagnostic_status: str
    display_name: str


DiagnosticBuilder = Callable[[Session, int], MobileOpsDiagnosticResult | None]


def _result(
    *,
    diagnostic_category: str,
    diagnostic_status: str,
    diagnostic_code: str,
    diagnostic_message: str,
    diagnostic_payload_json: dict[str, Any],
) -> MobileOpsDiagnosticResult:
    return MobileOpsDiagnosticResult(
        diagnostic_category=diagnostic_category,
        diagnostic_status=diagnostic_status,
        diagnostic_code=diagnostic_code,
        diagnostic_message=diagnostic_message,
        diagnostic_payload_json=dict(sorted(diagnostic_payload_json.items(), key=lambda pair: str(pair[0]))),
    )


def _no_active_mobile_devices(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    row = session.exec(
        select(MobileDevice.id)
        .where(MobileDevice.organization_id == organization_id)
        .where(MobileDevice.device_status == DEVICE_STATUS_ACTIVE)
        .limit(1)
    ).first()
    if row is not None:
        return None
    return _result(
        diagnostic_category="devices",
        diagnostic_status="warning",
        diagnostic_code="no_active_mobile_devices",
        diagnostic_message="No active mobile devices are registered.",
        diagnostic_payload_json={"active_mobile_devices": 0},
    )


def _open_sync_conflicts_present(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    conflicts = session.exec(
        select(OfflineSyncConflict)
        .where(OfflineSyncConflict.organization_id == organization_id)
        .where(OfflineSyncConflict.conflict_status == CONFLICT_STATUS_OPEN)
    ).all()
    if not conflicts:
        return None
    return _result(
        diagnostic_category="offline",
        diagnostic_status="warning",
        diagnostic_code="open_sync_conflicts_present",
        diagnostic_message="Open offline sync conflicts are present.",
        diagnostic_payload_json={"open_sync_conflicts": len(conflicts)},
    )


def _pending_sync_queue_items_present(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    rows = session.exec(
        select(OfflineSyncQueue)
        .where(OfflineSyncQueue.organization_id == organization_id)
        .where(OfflineSyncQueue.queue_status == QUEUE_STATUS_PENDING)
    ).all()
    if not rows:
        return None
    return _result(
        diagnostic_category="offline",
        diagnostic_status="warning",
        diagnostic_code="pending_sync_queue_items_present",
        diagnostic_message="Pending offline sync queue items are present.",
        diagnostic_payload_json={"pending_sync_queue_items": len(rows)},
    )


def _pending_intake_records_present(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    rows = session.exec(
        select(IntakeStagingRecord)
        .where(IntakeStagingRecord.organization_id == organization_id)
        .where(IntakeStagingRecord.staging_status == STAGING_STATUS_PENDING)
    ).all()
    if not rows:
        return None
    return _result(
        diagnostic_category="scanning",
        diagnostic_status="warning",
        diagnostic_code="pending_intake_records_present",
        diagnostic_message="Pending intake staging records are present.",
        diagnostic_payload_json={"pending_intake_records": len(rows)},
    )


def _active_convention_without_booth(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    active_sessions = session.exec(
        select(ConventionSession)
        .where(ConventionSession.organization_id == organization_id)
        .where(ConventionSession.session_status == CONVENTION_SESSION_STATUS_ACTIVE)
    ).all()
    if not active_sessions:
        return None
    missing_booths = 0
    for convention_session in active_sessions:
        booth = session.exec(
            select(ConventionBooth.id)
            .where(ConventionBooth.organization_id == organization_id)
            .where(ConventionBooth.convention_session_id == int(convention_session.id or 0))
            .where(ConventionBooth.booth_status != BOOTH_STATUS_CLOSED)
            .limit(1)
        ).first()
        if booth is None:
            missing_booths += 1
    if missing_booths == 0:
        return None
    return _result(
        diagnostic_category="convention",
        diagnostic_status="warning",
        diagnostic_code="active_convention_without_booth",
        diagnostic_message="Active convention sessions exist without an open booth.",
        diagnostic_payload_json={"active_sessions_without_booth": missing_booths},
    )


def _completed_sales_without_payment_record(session: Session, organization_id: int) -> MobileOpsDiagnosticResult | None:
    completed_sales = session.exec(
        select(QuickSale)
        .where(QuickSale.organization_id == organization_id)
        .where(QuickSale.sale_status == SALE_STATUS_COMPLETED)
    ).all()
    if not completed_sales:
        return None
    missing_payments = 0
    for sale in completed_sales:
        payment = session.exec(
            select(QuickSalePayment.id)
            .where(QuickSalePayment.organization_id == organization_id)
            .where(QuickSalePayment.quick_sale_id == int(sale.id or 0))
            .where(QuickSalePayment.payment_status == PAYMENT_STATUS_RECORDED)
            .limit(1)
        ).first()
        if payment is None:
            missing_payments += 1
    if missing_payments == 0:
        return None
    return _result(
        diagnostic_category="quick_sales",
        diagnostic_status="error",
        diagnostic_code="completed_sales_without_payment_record",
        diagnostic_message="Completed quick sales exist without a recorded payment.",
        diagnostic_payload_json={"completed_sales_without_payment_record": missing_payments},
    )


MOBILE_OPS_DIAGNOSTIC_BUILDERS: tuple[DiagnosticBuilder, ...] = (
    _no_active_mobile_devices,
    _open_sync_conflicts_present,
    _pending_sync_queue_items_present,
    _pending_intake_records_present,
    _active_convention_without_booth,
    _completed_sales_without_payment_record,
)

MOBILE_OPS_DIAGNOSTIC_DEFINITIONS: tuple[MobileOpsDiagnosticDefinition, ...] = (
    MobileOpsDiagnosticDefinition("no_active_mobile_devices", "devices", "warning", "No active mobile devices"),
    MobileOpsDiagnosticDefinition("open_sync_conflicts_present", "offline", "warning", "Open sync conflicts present"),
    MobileOpsDiagnosticDefinition("pending_sync_queue_items_present", "offline", "warning", "Pending sync queue items present"),
    MobileOpsDiagnosticDefinition("pending_intake_records_present", "scanning", "warning", "Pending intake records present"),
    MobileOpsDiagnosticDefinition("active_convention_without_booth", "convention", "warning", "Active convention without booth"),
    MobileOpsDiagnosticDefinition(
        "completed_sales_without_payment_record",
        "quick_sales",
        "error",
        "Completed sales without payment record",
    ),
)


def evaluate_mobile_ops_diagnostics(session: Session, organization_id: int) -> list[MobileOpsDiagnosticResult]:
    results: list[MobileOpsDiagnosticResult] = []
    for builder in MOBILE_OPS_DIAGNOSTIC_BUILDERS:
        result = builder(session, organization_id)
        if result is not None:
            results.append(result)
    return results


def list_mobile_ops_diagnostic_definitions() -> tuple[MobileOpsDiagnosticDefinition, ...]:
    return MOBILE_OPS_DIAGNOSTIC_DEFINITIONS


def summarize_mobile_ops_diagnostics(rows: list[MobileOpsDiagnostic | MobileOpsDiagnosticResult]) -> dict[str, int]:
    summary = {"ok": 0, "warning": 0, "error": 0}
    for row in rows:
        status = getattr(row, "diagnostic_status", None)
        if status in summary:
            summary[status] += 1
    return summary
