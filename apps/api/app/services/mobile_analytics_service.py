from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    ConventionInventoryStage,
    ConventionSession,
    IntakeStagingRecord,
    MobileAnalyticsEvent,
    MobileAnalyticsSnapshot,
    MobileDevice,
    MobileDeviceAccessLog,
    MobileDeviceTrustState,
    MobileOpsDiagnostic,
    MobileSession,
    MobileUsageMetric,
    MobileUsageTrend,
    OfflineInventoryRecord,
    OfflineSyncConflict,
    OfflineSyncQueue,
    QuickSale,
    QuickSalePayment,
    ScanCapture,
)
from app.schemas.mobile_analytics import (
    MobileAnalyticsDashboardResponse,
    MobileAnalyticsEventResponse,
    MobileAnalyticsPermissionResponse,
    MobileAnalyticsSnapshotListResponse,
    MobileAnalyticsSnapshotResponse,
    MobileUsageMetricListResponse,
    MobileUsageMetricResponse,
    MobileUsageTrendListResponse,
    MobileUsageTrendResponse,
)
from app.services.convention_registry import SESSION_STATUS_ACTIVE as CONVENTION_SESSION_STATUS_ACTIVE, STAGE_STATUS_REMOVED
from app.services.mobile_device_security_registry import ACCESS_RESULT_DENIED, TRUST_STATUS_SUSPENDED
from app.services.mobile_kpi_registry import list_mobile_kpi_definitions
from app.services.mobile_ops_diagnostics import list_mobile_ops_diagnostic_definitions
from app.services.mobile_permissions import resolve_mobile_permissions
from app.services.mobile_scan_registry import SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_STAGED, STAGING_STATUS_APPROVED
from app.services.mobile_usage_trends import build_mobile_usage_trends, list_mobile_usage_trend_definitions
from app.services.offline_runtime_registry import DEVICE_STATUS_ACTIVE, DEVICE_STATUS_SUSPENDED, SESSION_STATUS_ACTIVE
from app.services.offline_sync_registry import CONFLICT_STATUS_OPEN, QUEUE_STATUS_PENDING
from app.services.quick_sale_registry import PAYMENT_METHOD_CASH, PAYMENT_STATUS_RECORDED, SALE_STATUS_COMPLETED, SALE_STATUS_VOIDED


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _decimal_string(value: Decimal | int | float | str) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return _decimal_string(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(can_view: bool, can_manage: bool) -> MobileAnalyticsPermissionResponse:
    return MobileAnalyticsPermissionResponse(can_view=can_view, can_manage=can_manage)


def _snapshot_response(row: MobileAnalyticsSnapshot) -> MobileAnalyticsSnapshotResponse:
    return MobileAnalyticsSnapshotResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        snapshot_type=row.snapshot_type,
        snapshot_payload_json=dict(row.snapshot_payload_json or {}),
        generated_at=row.generated_at,
    )


def _metric_response(row: MobileUsageMetric) -> MobileUsageMetricResponse:
    return MobileUsageMetricResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        metric_key=row.metric_key,
        metric_value_json=dict(row.metric_value_json or {}),
        metric_period=row.metric_period,
        generated_at=row.generated_at,
    )


def _trend_response(row: MobileUsageTrend) -> MobileUsageTrendResponse:
    return MobileUsageTrendResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        trend_key=row.trend_key,
        trend_payload_json=dict(row.trend_payload_json or {}),
        trend_period=row.trend_period,
        generated_at=row.generated_at,
    )


def _event_response(row: MobileAnalyticsEvent) -> MobileAnalyticsEventResponse:
    return MobileAnalyticsEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def create_mobile_analytics_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MobileAnalyticsEvent:
    row = MobileAnalyticsEvent(
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
        create_mobile_analytics_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_analytics_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile analytics visibility is denied for this organization.")
    return resolution


def _validate_management(session: Session, *, organization_id: int, actor_user_id: int, action: str):
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_mobile_analytics_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_analytics_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile analytics management is denied for this organization.")
    return resolution


def _latest_rows_by_key(rows: list[Any], *, key_name: str) -> list[Any]:
    latest: dict[str, Any] = OrderedDict()
    for row in rows:
        key = getattr(row, key_name)
        if key not in latest:
            latest[key] = row
    return list(latest.values())


def _current_mobile_ops_diagnostics(session: Session, *, organization_id: int) -> list[MobileOpsDiagnostic]:
    rows = session.exec(
        select(MobileOpsDiagnostic)
        .where(MobileOpsDiagnostic.organization_id == organization_id)
        .order_by(MobileOpsDiagnostic.created_at.desc(), MobileOpsDiagnostic.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="diagnostic_code")
    order = {definition.diagnostic_code: index for index, definition in enumerate(list_mobile_ops_diagnostic_definitions())}
    latest.sort(key=lambda row: (order.get(row.diagnostic_code, 999), row.diagnostic_code))
    return latest


def _build_metric_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    devices = session.exec(select(MobileDevice).where(MobileDevice.organization_id == organization_id)).all()
    trust_states = session.exec(select(MobileDeviceTrustState).where(MobileDeviceTrustState.organization_id == organization_id)).all()
    sessions = session.exec(select(MobileSession).where(MobileSession.organization_id == organization_id)).all()
    offline_records = session.exec(select(OfflineInventoryRecord).where(OfflineInventoryRecord.organization_id == organization_id)).all()
    sync_queue = session.exec(select(OfflineSyncQueue).where(OfflineSyncQueue.organization_id == organization_id)).all()
    sync_conflicts = session.exec(select(OfflineSyncConflict).where(OfflineSyncConflict.organization_id == organization_id)).all()
    scan_captures = session.exec(select(ScanCapture).where(ScanCapture.organization_id == organization_id)).all()
    intake_records = session.exec(select(IntakeStagingRecord).where(IntakeStagingRecord.organization_id == organization_id)).all()
    convention_sessions = session.exec(select(ConventionSession).where(ConventionSession.organization_id == organization_id)).all()
    staged_inventory = session.exec(select(ConventionInventoryStage).where(ConventionInventoryStage.organization_id == organization_id)).all()
    quick_sales = session.exec(select(QuickSale).where(QuickSale.organization_id == organization_id)).all()
    payments = session.exec(select(QuickSalePayment).where(QuickSalePayment.organization_id == organization_id)).all()
    access_logs = session.exec(select(MobileDeviceAccessLog).where(MobileDeviceAccessLog.organization_id == organization_id)).all()

    lookup_complete_count = sum(1 for row in scan_captures if row.scan_status in {SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_STAGED})
    successful_lookup_rate = (
        Decimal(lookup_complete_count) / Decimal(len(scan_captures)) * Decimal("100.00")
        if scan_captures
        else Decimal("0.00")
    )
    completed_quick_sales = [row for row in quick_sales if row.sale_status == SALE_STATUS_COMPLETED]
    quick_sales_total_amount = sum(
        (Decimal(str(row.total_amount)) for row in quick_sales if row.sale_status != SALE_STATUS_VOIDED),
        Decimal("0.00"),
    )
    average_quick_sale_value = (
        quick_sales_total_amount / Decimal(len(completed_quick_sales))
        if completed_quick_sales
        else Decimal("0.00")
    )

    return {
        "registered_devices": {"count": len(devices)},
        "active_devices": {"count": sum(1 for row in devices if row.device_status == DEVICE_STATUS_ACTIVE)},
        "suspended_devices": {"count": sum(1 for row in devices if row.device_status == DEVICE_STATUS_SUSPENDED)},
        "active_sessions": {"count": sum(1 for row in sessions if row.session_status == SESSION_STATUS_ACTIVE)},
        "offline_records_created": {"count": len(offline_records)},
        "queued_sync_operations": {"count": sum(1 for row in sync_queue if row.queue_status == QUEUE_STATUS_PENDING)},
        "open_sync_conflicts": {"count": sum(1 for row in sync_conflicts if row.conflict_status == CONFLICT_STATUS_OPEN)},
        "scans_captured": {"count": len(scan_captures)},
        "successful_lookup_rate": {
            "count": lookup_complete_count,
            "total": len(scan_captures),
            "rate": _decimal_string(successful_lookup_rate),
            "unit": "percent",
        },
        "staged_intake_records": {"count": len(intake_records)},
        "approved_intake_records": {"count": sum(1 for row in intake_records if row.staging_status == STAGING_STATUS_APPROVED)},
        "convention_sessions_created": {"count": len(convention_sessions)},
        "active_convention_sessions": {"count": sum(1 for row in convention_sessions if row.session_status == CONVENTION_SESSION_STATUS_ACTIVE)},
        "inventory_items_staged": {"count": sum(1 for row in staged_inventory if row.stage_status != STAGE_STATUS_REMOVED)},
        "quick_sales_created": {"count": len(quick_sales)},
        "completed_quick_sales": {"count": len(completed_quick_sales)},
        "quick_sales_total_amount": {"amount": _decimal_string(quick_sales_total_amount), "currency": "USD"},
        "average_quick_sale_value": {"amount": _decimal_string(average_quick_sale_value), "currency": "USD"},
        "denied_mobile_access_attempts": {"count": sum(1 for row in access_logs if row.access_result == ACCESS_RESULT_DENIED)},
        "suspended_device_count": {"count": sum(1 for row in trust_states if row.trust_status == TRUST_STATUS_SUSPENDED)},
        "recorded_external_payments": {
            "count": sum(
                1
                for row in payments
                if row.payment_status == PAYMENT_STATUS_RECORDED and row.payment_method != PAYMENT_METHOD_CASH
            )
        },
    }


def _persist_mobile_usage_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> list[MobileUsageMetric]:
    payloads = _build_metric_payloads(session, organization_id=organization_id)
    now = utc_now()
    rows: list[MobileUsageMetric] = []
    definitions = list_mobile_kpi_definitions()
    for definition in definitions:
        row = MobileUsageMetric(
            organization_id=organization_id,
            metric_key=definition.metric_key,
            metric_value_json=_json_safe(payloads[definition.metric_key]),
            metric_period=definition.metric_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_mobile_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_metrics_generated",
        event_payload_json={"metric_keys": [definition.metric_key for definition in definitions]},
    )
    return rows


def generate_mobile_usage_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileUsageMetricListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:metrics_generate")
    rows = _persist_mobile_usage_metrics(session, organization_id=organization_id, actor_user_id=actor_user_id)
    session.commit()
    return MobileUsageMetricListResponse(
        organization_id=organization_id,
        items=[_metric_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_metrics(session: Session, *, organization_id: int) -> list[MobileUsageMetricResponse]:
    rows = session.exec(
        select(MobileUsageMetric)
        .where(MobileUsageMetric.organization_id == organization_id)
        .order_by(MobileUsageMetric.generated_at.desc(), MobileUsageMetric.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="metric_key")
    order = {definition.metric_key: index for index, definition in enumerate(list_mobile_kpi_definitions())}
    latest.sort(key=lambda row: (order.get(row.metric_key, 999), row.metric_key))
    return [_metric_response(row) for row in latest]


def _persist_mobile_usage_trends(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> list[MobileUsageTrend]:
    payloads = build_mobile_usage_trends(session, organization_id=organization_id)
    now = utc_now()
    rows: list[MobileUsageTrend] = []
    for payload in payloads:
        row = MobileUsageTrend(
            organization_id=organization_id,
            trend_key=payload.trend_key,
            trend_payload_json=_json_safe(payload.trend_payload_json),
            trend_period=payload.trend_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_mobile_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_trends_generated",
        event_payload_json={"trend_keys": [payload.trend_key for payload in payloads]},
    )
    return rows


def generate_mobile_usage_trends(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileUsageTrendListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:trends_generate")
    rows = _persist_mobile_usage_trends(session, organization_id=organization_id, actor_user_id=actor_user_id)
    session.commit()
    return MobileUsageTrendListResponse(
        organization_id=organization_id,
        items=[_trend_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_trends(session: Session, *, organization_id: int) -> list[MobileUsageTrendResponse]:
    rows = session.exec(
        select(MobileUsageTrend)
        .where(MobileUsageTrend.organization_id == organization_id)
        .order_by(MobileUsageTrend.generated_at.desc(), MobileUsageTrend.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="trend_key")
    order = {definition.trend_key: index for index, definition in enumerate(list_mobile_usage_trend_definitions())}
    latest.sort(key=lambda row: (order.get(row.trend_key, 999), row.trend_key))
    return [_trend_response(row) for row in latest]


def resolve_mobile_analytics_summary(session: Session, *, organization_id: int) -> dict[str, Any]:
    metric_map = _build_metric_payloads(session, organization_id=organization_id)
    metric_map.update({metric.metric_key: metric.metric_value_json for metric in _build_current_metrics(session, organization_id=organization_id)})
    diagnostics = _current_mobile_ops_diagnostics(session, organization_id=organization_id)
    warning_count = sum(1 for row in diagnostics if row.diagnostic_status == "warning")
    error_count = sum(1 for row in diagnostics if row.diagnostic_status == "error")
    summary = {
        "devices": {
            "registered": metric_map.get("registered_devices", {}).get("count", 0),
            "active": metric_map.get("active_devices", {}).get("count", 0),
            "suspended": metric_map.get("suspended_devices", {}).get("count", 0),
            "active_sessions": metric_map.get("active_sessions", {}).get("count", 0),
        },
        "offline": {
            "records_created": metric_map.get("offline_records_created", {}).get("count", 0),
            "queued_sync_operations": metric_map.get("queued_sync_operations", {}).get("count", 0),
            "open_sync_conflicts": metric_map.get("open_sync_conflicts", {}).get("count", 0),
        },
        "scanning": {
            "scans_captured": metric_map.get("scans_captured", {}).get("count", 0),
            "successful_lookup_rate": metric_map.get("successful_lookup_rate", {}).get("rate", "0.00"),
            "staged_intake_records": metric_map.get("staged_intake_records", {}).get("count", 0),
            "approved_intake_records": metric_map.get("approved_intake_records", {}).get("count", 0),
        },
        "convention": {
            "sessions_created": metric_map.get("convention_sessions_created", {}).get("count", 0),
            "active_sessions": metric_map.get("active_convention_sessions", {}).get("count", 0),
            "inventory_items_staged": metric_map.get("inventory_items_staged", {}).get("count", 0),
        },
        "quick_sales": {
            "sales_created": metric_map.get("quick_sales_created", {}).get("count", 0),
            "completed_sales": metric_map.get("completed_quick_sales", {}).get("count", 0),
            "total_amount": metric_map.get("quick_sales_total_amount", {}).get("amount", "0.00"),
            "currency": metric_map.get("quick_sales_total_amount", {}).get("currency", "USD"),
            "average_sale_value": metric_map.get("average_quick_sale_value", {}).get("amount", "0.00"),
            "recorded_external_payments": metric_map.get("recorded_external_payments", {}).get("count", 0),
        },
        "security": {
            "denied_mobile_access_attempts": metric_map.get("denied_mobile_access_attempts", {}).get("count", 0),
            "suspended_device_count": metric_map.get("suspended_device_count", {}).get("count", 0),
        },
        "performance": {
            "lookup_success_rate": metric_map.get("successful_lookup_rate", {}).get("rate", "0.00"),
            "average_quick_sale_value": metric_map.get("average_quick_sale_value", {}).get("amount", "0.00"),
            "mobile_ops_warning_count": warning_count,
            "mobile_ops_error_count": error_count,
        },
    }
    return _json_safe(summary)


def generate_mobile_analytics_snapshot(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    snapshot_type: str = "full_analytics_snapshot",
) -> MobileAnalyticsSnapshotResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:snapshot_generate")
    metric_rows = _persist_mobile_usage_metrics(session, organization_id=organization_id, actor_user_id=actor_user_id)
    trend_rows = _persist_mobile_usage_trends(session, organization_id=organization_id, actor_user_id=actor_user_id)
    summary = resolve_mobile_analytics_summary(session, organization_id=organization_id)
    create_mobile_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_performance_calculated",
        event_payload_json={"performance": summary.get("performance", {})},
    )
    payload = _json_safe(
        {
            "snapshot_type": snapshot_type,
            "summary": summary,
            "metrics": [_metric_response(row).model_dump(mode="json") for row in metric_rows],
            "trends": [_trend_response(row).model_dump(mode="json") for row in trend_rows],
        }
    )
    row = MobileAnalyticsSnapshot(
        organization_id=organization_id,
        snapshot_type=snapshot_type,
        snapshot_payload_json=payload,
        generated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_mobile_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_snapshot_generated",
        event_payload_json={"snapshot_type": snapshot_type, "snapshot_id": int(row.id or 0)},
    )
    create_mobile_analytics_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_analytics_generated",
        event_payload_json={
            "snapshot_id": int(row.id or 0),
            "metric_count": len(metric_rows),
            "trend_count": len(trend_rows),
        },
    )
    session.commit()
    return _snapshot_response(row)


def list_mobile_analytics_snapshots(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileAnalyticsSnapshotListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:snapshot:view")
    base = select(MobileAnalyticsSnapshot).where(MobileAnalyticsSnapshot.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(MobileAnalyticsSnapshot.generated_at.desc(), MobileAnalyticsSnapshot.id.desc()).offset(offset).limit(limit)).all()
    return MobileAnalyticsSnapshotListResponse(
        organization_id=organization_id,
        items=[_snapshot_response(row) for row in rows],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_mobile_usage_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileUsageMetricListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:metric:view")
    metrics = _build_current_metrics(session, organization_id=organization_id)
    total = len(metrics)
    return MobileUsageMetricListResponse(
        organization_id=organization_id,
        items=metrics[offset : offset + limit],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_mobile_usage_trends(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileUsageTrendListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:trend:view")
    trends = _build_current_trends(session, organization_id=organization_id)
    total = len(trends)
    return MobileUsageTrendListResponse(
        organization_id=organization_id,
        items=trends[offset : offset + limit],
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def build_mobile_analytics_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileAnalyticsDashboardResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_analytics:view")
    snapshots = list_mobile_analytics_snapshots(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=20, offset=0).items
    events = session.exec(
        select(MobileAnalyticsEvent)
        .where(MobileAnalyticsEvent.organization_id == organization_id)
        .order_by(MobileAnalyticsEvent.created_at.desc(), MobileAnalyticsEvent.id.desc())
        .limit(25)
    ).all()
    latest_snapshot = snapshots[0] if snapshots else None
    return MobileAnalyticsDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution.can_view, resolution.can_manage),
        summary=resolve_mobile_analytics_summary(session, organization_id=organization_id),
        metrics=_build_current_metrics(session, organization_id=organization_id),
        trends=_build_current_trends(session, organization_id=organization_id),
        snapshots=snapshots,
        events=[_event_response(row) for row in events],
        latest_snapshot=latest_snapshot,
    )
