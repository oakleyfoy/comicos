from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    ConventionBooth,
    ConventionInventoryStage,
    ConventionSession,
    IntakeStagingRecord,
    MobileDevice,
    MobileSession,
    OfflineInventoryRecord,
    OfflineSyncConflict,
    OfflineSyncContract,
    OfflineSyncQueue,
    QuickSale,
    QuickSalePayment,
    ScanCapture,
)
from app.models.mobile_ops_dashboard import MobileOpsDiagnostic, MobileOpsEvent, MobileOpsMetric, MobileOpsSnapshot
from app.schemas.mobile_ops_dashboard import (
    MobileOpsDashboardResponse,
    MobileOpsDiagnosticListResponse,
    MobileOpsDiagnosticResponse,
    MobileOpsEventResponse,
    MobileOpsMetricListResponse,
    MobileOpsMetricResponse,
    MobileOpsPermissionResponse,
    MobileOpsSnapshotListResponse,
    MobileOpsSnapshotResponse,
)
from app.services.convention_registry import BOOTH_STATUS_ACTIVE, SESSION_STATUS_ACTIVE as CONVENTION_SESSION_STATUS_ACTIVE, STAGE_STATUS_REMOVED
from app.services.mobile_ops_diagnostics import (
    evaluate_mobile_ops_diagnostics,
    list_mobile_ops_diagnostic_definitions,
    summarize_mobile_ops_diagnostics,
)
from app.services.mobile_ops_metric_registry import list_mobile_ops_metric_definitions
from app.services.mobile_permissions import resolve_mobile_permissions
from app.services.mobile_scan_registry import STAGING_STATUS_APPROVED, STAGING_STATUS_PENDING
from app.services.offline_runtime_registry import DEVICE_STATUS_ACTIVE, DEVICE_STATUS_INACTIVE, SESSION_STATUS_ACTIVE
from app.services.offline_sync_registry import CONFLICT_STATUS_OPEN, QUEUE_STATUS_PENDING
from app.services.quick_sale_registry import PAYMENT_METHOD_CASH, PAYMENT_STATUS_RECORDED, SALE_STATUS_COMPLETED, SALE_STATUS_VOIDED


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(can_view: bool, can_manage: bool) -> MobileOpsPermissionResponse:
    return MobileOpsPermissionResponse(can_view=can_view, can_manage=can_manage)


def _metric_response(row: MobileOpsMetric) -> MobileOpsMetricResponse:
    return MobileOpsMetricResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        metric_key=row.metric_key,
        metric_value_json=dict(row.metric_value_json or {}),
        metric_period=row.metric_period,
        generated_at=row.generated_at,
    )


def _diagnostic_response(row: MobileOpsDiagnostic) -> MobileOpsDiagnosticResponse:
    return MobileOpsDiagnosticResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        diagnostic_category=row.diagnostic_category,
        diagnostic_status=row.diagnostic_status,
        diagnostic_code=row.diagnostic_code,
        diagnostic_message=row.diagnostic_message,
        diagnostic_payload_json=dict(row.diagnostic_payload_json or {}),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


def _snapshot_response(row: MobileOpsSnapshot) -> MobileOpsSnapshotResponse:
    return MobileOpsSnapshotResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        snapshot_type=row.snapshot_type,
        snapshot_payload_json=dict(row.snapshot_payload_json or {}),
        generated_at=row.generated_at,
    )


def _event_response(row: MobileOpsEvent) -> MobileOpsEventResponse:
    return MobileOpsEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def create_mobile_ops_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MobileOpsEvent:
    row = MobileOpsEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _validate_visibility(session: Session, *, organization_id: int, actor_user_id: int, action: str):
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_mobile_ops_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_ops_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile ops visibility is denied for this organization.")
    return resolution


def _validate_management(session: Session, *, organization_id: int, actor_user_id: int, action: str):
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_mobile_ops_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_ops_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile ops management is denied for this organization.")
    return resolution


def _latest_rows_by_key(rows: list[Any], *, key_name: str) -> list[Any]:
    latest: dict[str, Any] = OrderedDict()
    for row in rows:
        key = getattr(row, key_name)
        if key not in latest:
            latest[key] = row
    return list(latest.values())


def _build_metric_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    devices = session.exec(select(MobileDevice).where(MobileDevice.organization_id == organization_id)).all()
    mobile_sessions = session.exec(select(MobileSession).where(MobileSession.organization_id == organization_id)).all()
    contracts = session.exec(select(OfflineSyncContract).where(OfflineSyncContract.organization_id == organization_id)).all()
    offline_records = session.exec(select(OfflineInventoryRecord).where(OfflineInventoryRecord.organization_id == organization_id)).all()
    sync_queue = session.exec(select(OfflineSyncQueue).where(OfflineSyncQueue.organization_id == organization_id)).all()
    sync_conflicts = session.exec(select(OfflineSyncConflict).where(OfflineSyncConflict.organization_id == organization_id)).all()
    scan_captures = session.exec(select(ScanCapture).where(ScanCapture.organization_id == organization_id)).all()
    intake_records = session.exec(select(IntakeStagingRecord).where(IntakeStagingRecord.organization_id == organization_id)).all()
    convention_sessions = session.exec(select(ConventionSession).where(ConventionSession.organization_id == organization_id)).all()
    booths = session.exec(select(ConventionBooth).where(ConventionBooth.organization_id == organization_id)).all()
    staged_inventory = session.exec(select(ConventionInventoryStage).where(ConventionInventoryStage.organization_id == organization_id)).all()
    quick_sales = session.exec(select(QuickSale).where(QuickSale.organization_id == organization_id)).all()
    payments = session.exec(select(QuickSalePayment).where(QuickSalePayment.organization_id == organization_id)).all()

    quick_sales_total_amount = sum((Decimal(str(row.total_amount)) for row in quick_sales if row.sale_status != SALE_STATUS_VOIDED), Decimal("0.00"))
    return {
        "active_mobile_devices": {"count": sum(1 for row in devices if row.device_status == DEVICE_STATUS_ACTIVE)},
        "inactive_mobile_devices": {"count": sum(1 for row in devices if row.device_status == DEVICE_STATUS_INACTIVE)},
        "active_mobile_sessions": {"count": sum(1 for row in mobile_sessions if row.session_status == SESSION_STATUS_ACTIVE)},
        "offline_inventory_records": {"count": len(offline_records)},
        "pending_sync_queue_items": {"count": sum(1 for row in sync_queue if row.queue_status == QUEUE_STATUS_PENDING)},
        "open_sync_conflicts": {"count": sum(1 for row in sync_conflicts if row.conflict_status == CONFLICT_STATUS_OPEN)},
        "scan_captures_count": {"count": len(scan_captures)},
        "pending_intake_staging_records": {"count": sum(1 for row in intake_records if row.staging_status == STAGING_STATUS_PENDING)},
        "approved_intake_staging_records": {"count": sum(1 for row in intake_records if row.staging_status == STAGING_STATUS_APPROVED)},
        "active_convention_sessions": {"count": sum(1 for row in convention_sessions if row.session_status == CONVENTION_SESSION_STATUS_ACTIVE)},
        "staged_convention_inventory": {"count": sum(1 for row in staged_inventory if row.stage_status != STAGE_STATUS_REMOVED)},
        "active_booths": {"count": sum(1 for row in booths if row.booth_status == BOOTH_STATUS_ACTIVE)},
        "quick_sales_count": {"count": len(quick_sales)},
        "completed_quick_sales_count": {"count": sum(1 for row in quick_sales if row.sale_status == SALE_STATUS_COMPLETED)},
        "quick_sales_total_amount": {"amount": quick_sales_total_amount, "currency": "USD"},
        "recorded_external_payments_count": {
            "count": sum(
                1
                for row in payments
                if row.payment_status == PAYMENT_STATUS_RECORDED and row.payment_method != PAYMENT_METHOD_CASH
            )
        },
        "offline_sync_contracts": {"count": len(contracts)},
    }


def generate_mobile_ops_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileOpsMetricListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:metrics_generate")
    payloads = _build_metric_payloads(session, organization_id=organization_id)
    rows: list[MobileOpsMetric] = []
    now = utc_now()
    definitions = list_mobile_ops_metric_definitions()
    for definition in definitions:
        row = MobileOpsMetric(
            organization_id=organization_id,
            metric_key=definition.metric_key,
            metric_value_json=_json_safe(payloads[definition.metric_key]),
            metric_period=definition.metric_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_mobile_ops_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_ops_metrics_generated",
        event_payload_json={"metric_keys": [definition.metric_key for definition in definitions]},
    )
    session.commit()
    return MobileOpsMetricListResponse(
        organization_id=organization_id,
        items=[_metric_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_metrics(session: Session, *, organization_id: int) -> list[MobileOpsMetricResponse]:
    rows = session.exec(
        select(MobileOpsMetric)
        .where(MobileOpsMetric.organization_id == organization_id)
        .order_by(MobileOpsMetric.generated_at.desc(), MobileOpsMetric.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="metric_key")
    order = {definition.metric_key: index for index, definition in enumerate(list_mobile_ops_metric_definitions())}
    latest.sort(key=lambda row: (order.get(row.metric_key, 999), row.metric_key))
    return [_metric_response(row) for row in latest]


def generate_mobile_ops_diagnostics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileOpsDiagnosticListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:diagnostics_generate")
    evaluated = evaluate_mobile_ops_diagnostics(session, organization_id=organization_id)
    rows: list[MobileOpsDiagnostic] = []
    now = utc_now()
    for result in evaluated:
        row = MobileOpsDiagnostic(
            organization_id=organization_id,
            diagnostic_category=result.diagnostic_category,
            diagnostic_status=result.diagnostic_status,
            diagnostic_code=result.diagnostic_code,
            diagnostic_message=result.diagnostic_message,
            diagnostic_payload_json=_json_safe(result.diagnostic_payload_json),
            created_at=now,
        )
        session.add(row)
        rows.append(row)
        create_mobile_ops_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="mobile_ops_diagnostic_created",
            event_payload_json={
                "diagnostic_code": result.diagnostic_code,
                "diagnostic_status": result.diagnostic_status,
                "diagnostic_category": result.diagnostic_category,
            },
        )
    session.flush()
    create_mobile_ops_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_ops_diagnostics_generated",
        event_payload_json={"diagnostic_codes": [row.diagnostic_code for row in rows]},
    )
    session.commit()
    return MobileOpsDiagnosticListResponse(
        organization_id=organization_id,
        items=[_diagnostic_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_diagnostics(session: Session, *, organization_id: int) -> list[MobileOpsDiagnosticResponse]:
    rows = session.exec(
        select(MobileOpsDiagnostic)
        .where(MobileOpsDiagnostic.organization_id == organization_id)
        .order_by(MobileOpsDiagnostic.created_at.desc(), MobileOpsDiagnostic.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="diagnostic_code")
    order = {definition.diagnostic_code: index for index, definition in enumerate(list_mobile_ops_diagnostic_definitions())}
    latest.sort(key=lambda row: (order.get(row.diagnostic_code, 999), row.diagnostic_code))
    return [_diagnostic_response(row) for row in latest]


def list_mobile_ops_snapshots(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileOpsSnapshotListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:snapshot:view")
    base = select(MobileOpsSnapshot).where(MobileOpsSnapshot.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(MobileOpsSnapshot.generated_at.desc(), MobileOpsSnapshot.id.desc()).offset(offset).limit(limit)).all()
    return MobileOpsSnapshotListResponse(
        organization_id=organization_id,
        items=[_snapshot_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_mobile_ops_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileOpsMetricListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:metric:view")
    metrics = _build_current_metrics(session, organization_id=organization_id)
    total = len(metrics)
    return MobileOpsMetricListResponse(
        organization_id=organization_id,
        items=metrics[offset : offset + limit],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_mobile_ops_diagnostics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileOpsDiagnosticListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:diagnostic:view")
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    total = len(diagnostics)
    return MobileOpsDiagnosticListResponse(
        organization_id=organization_id,
        items=diagnostics[offset : offset + limit],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def resolve_mobile_ops_summary(session: Session, *, organization_id: int) -> dict[str, Any]:
    metrics = _build_current_metrics(session, organization_id=organization_id)
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    metric_map = {metric.metric_key: metric.metric_value_json for metric in metrics} if metrics else _build_metric_payloads(session, organization_id=organization_id)
    diagnostic_summary = (
        summarize_mobile_ops_diagnostics(diagnostics)
        if diagnostics
        else summarize_mobile_ops_diagnostics(evaluate_mobile_ops_diagnostics(session, organization_id=organization_id))
    )
    summary = {
        "devices": {
            "active": metric_map.get("active_mobile_devices", {}).get("count", 0),
            "inactive": metric_map.get("inactive_mobile_devices", {}).get("count", 0),
            "active_sessions": metric_map.get("active_mobile_sessions", {}).get("count", 0),
        },
        "offline": {
            "records": metric_map.get("offline_inventory_records", {}).get("count", 0),
            "contracts": metric_map.get("offline_sync_contracts", {}).get("count", 0),
            "pending_queue": metric_map.get("pending_sync_queue_items", {}).get("count", 0),
            "open_conflicts": metric_map.get("open_sync_conflicts", {}).get("count", 0),
        },
        "scanning": {
            "captures": metric_map.get("scan_captures_count", {}).get("count", 0),
            "pending_intake": metric_map.get("pending_intake_staging_records", {}).get("count", 0),
            "approved_intake": metric_map.get("approved_intake_staging_records", {}).get("count", 0),
        },
        "convention": {
            "active_sessions": metric_map.get("active_convention_sessions", {}).get("count", 0),
            "staged_inventory": metric_map.get("staged_convention_inventory", {}).get("count", 0),
            "active_booths": metric_map.get("active_booths", {}).get("count", 0),
        },
        "quick_sales": {
            "total_sales": metric_map.get("quick_sales_count", {}).get("count", 0),
            "completed_sales": metric_map.get("completed_quick_sales_count", {}).get("count", 0),
            "total_amount": metric_map.get("quick_sales_total_amount", {}).get("amount", "0.00"),
            "currency": metric_map.get("quick_sales_total_amount", {}).get("currency", "USD"),
            "recorded_external_payments": metric_map.get("recorded_external_payments_count", {}).get("count", 0),
        },
        "workflow_health": {
            "diagnostics": diagnostic_summary,
        },
    }
    return _json_safe(summary)


def build_mobile_ops_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileOpsDashboardResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:view")
    create_mobile_ops_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_ops_dashboard_accessed",
        event_payload_json={"action": "mobile_ops:view"},
    )
    session.commit()
    metrics = _build_current_metrics(session, organization_id=organization_id)
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    snapshots = list_mobile_ops_snapshots(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=20, offset=0).items
    events = session.exec(
        select(MobileOpsEvent)
        .where(MobileOpsEvent.organization_id == organization_id)
        .order_by(MobileOpsEvent.created_at.desc(), MobileOpsEvent.id.desc())
        .limit(25)
    ).all()
    latest_snapshot = snapshots[0] if snapshots else None
    return MobileOpsDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        summary=resolve_mobile_ops_summary(session, organization_id=organization_id),
        metrics=metrics,
        diagnostics=diagnostics,
        snapshots=snapshots,
        events=[_event_response(row) for row in events],
        latest_snapshot=latest_snapshot,
    )


def generate_mobile_ops_snapshot(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    snapshot_type: str = "full_dashboard_snapshot",
) -> MobileOpsSnapshotResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_ops:snapshot_generate")
    metric_list = generate_mobile_ops_metrics(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    diagnostic_list = generate_mobile_ops_diagnostics(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    payload = _json_safe(
        {
            "snapshot_type": snapshot_type,
            "summary": resolve_mobile_ops_summary(session, organization_id=organization_id),
            "metrics": [metric.model_dump(mode="json") for metric in metric_list],
            "diagnostics": [diagnostic.model_dump(mode="json") for diagnostic in diagnostic_list],
        }
    )
    row = MobileOpsSnapshot(
        organization_id=organization_id,
        snapshot_type=snapshot_type,
        snapshot_payload_json=payload,
        generated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_mobile_ops_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_ops_snapshot_generated",
        event_payload_json={"snapshot_type": snapshot_type, "snapshot_id": int(row.id or 0)},
    )
    session.commit()
    return _snapshot_response(row)
