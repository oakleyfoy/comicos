from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    LiveSaleClaim,
    LiveSaleQueueItem,
    LiveSaleSession,
    MarketplaceAccount,
    MarketplaceEvent,
    MarketplaceEventProcessingRun,
    MarketplaceInventoryConflict,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
    MarketplaceOffer,
    MarketplaceOrder,
    MarketplaceOrderEvent,
    MarketplacePricingEvent,
    MarketplacePriceRecommendation,
    MarketplaceTransaction,
)
from app.models.marketplace_ops_dashboard import (
    MarketplaceOpsDiagnostic,
    MarketplaceOpsEvent,
    MarketplaceOpsMetric,
    MarketplaceOpsSnapshot,
)
from app.schemas.marketplace_ops_dashboard import (
    MarketplaceOpsDashboardResponse,
    MarketplaceOpsDiagnosticListResponse,
    MarketplaceOpsDiagnosticResponse,
    MarketplaceOpsEventResponse,
    MarketplaceOpsMetricListResponse,
    MarketplaceOpsMetricResponse,
    MarketplaceOpsPermissionResponse,
    MarketplaceOpsSnapshotListResponse,
    MarketplaceOpsSnapshotResponse,
)
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED, VERIFICATION_STATUS_VERIFIED
from app.services.marketplace_event_processing import EVENT_STATUS_FAILED as EVENT_PROCESSING_STATUS_FAILED
from app.services.marketplace_event_processing import EVENT_STATUS_PROCESSED, EVENT_STATUS_RECEIVED, EVENT_STATUS_VALIDATED
from app.services.marketplace_inventory_sync_service import CONFLICT_STATUS_RESOLVED
from app.services.marketplace_listing_validation import LISTING_STATUS_ARCHIVED, LISTING_STATUS_READY, VALIDATION_STATUS_INVALID
from app.services.marketplace_order_ingestion import ORDER_STATUS_CANCELLED, ORDER_STATUS_COMPLETED, ORDER_STATUS_IMPORTED, ORDER_STATUS_PENDING, TRANSACTION_STATUS_FAILED
from app.services.marketplace_ops_diagnostics import evaluate_marketplace_ops_diagnostics, summarize_marketplace_ops_diagnostics
from app.services.marketplace_ops_registry import (
    list_marketplace_ops_diagnostic_definitions,
    list_marketplace_ops_metric_definitions,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions
from app.services.marketplace_pricing_service import RECOMMENDATION_STATUS_GENERATED
from app.services.marketplace_offer_service import OFFER_STATUS_RECEIVED
from app.services.live_sale_workflow_service import SESSION_STATUS_LIVE, SESSION_STATUS_PLANNED, SESSION_STATUS_ENDED, SESSION_STATUS_CANCELLED


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceOpsPermissionResponse:
    return MarketplaceOpsPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _metric_response(row: MarketplaceOpsMetric) -> MarketplaceOpsMetricResponse:
    return MarketplaceOpsMetricResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        metric_key=row.metric_key,
        metric_value_json=dict(row.metric_value_json or {}),
        metric_period=row.metric_period,
        generated_at=row.generated_at,
    )


def _diagnostic_response(row: MarketplaceOpsDiagnostic) -> MarketplaceOpsDiagnosticResponse:
    return MarketplaceOpsDiagnosticResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        diagnostic_category=row.diagnostic_category,
        diagnostic_status=row.diagnostic_status,
        diagnostic_code=row.diagnostic_code,
        diagnostic_message=row.diagnostic_message,
        diagnostic_payload_json=dict(row.diagnostic_payload_json or {}),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


def _snapshot_response(row: MarketplaceOpsSnapshot) -> MarketplaceOpsSnapshotResponse:
    return MarketplaceOpsSnapshotResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        snapshot_type=row.snapshot_type,
        snapshot_payload_json=dict(row.snapshot_payload_json or {}),
        generated_at=row.generated_at,
    )


def _event_response(row: MarketplaceOpsEvent) -> MarketplaceOpsEventResponse:
    return MarketplaceOpsEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_marketplace_ops_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=None,
            event_type="unauthorized_marketplace_ops_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace ops visibility is denied for this organization.")
    return resolution


def _validate_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_marketplace_ops_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=None,
            event_type="unauthorized_marketplace_ops_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace ops management is denied for this organization.")
    return resolution


def create_marketplace_ops_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceOpsEvent:
    row = MarketplaceOpsEvent(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _latest_rows_by_key(rows: list[Any], *, key_name: str) -> list[Any]:
    latest: dict[str, Any] = OrderedDict()
    for row in rows:
        key = getattr(row, key_name)
        if key not in latest:
            latest[key] = row
    return list(latest.values())


def _count(session: Session, statement) -> int:
    return len(session.exec(statement).all())


def _build_metric_payloads(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    connected_accounts = session.exec(
        select(MarketplaceAccount).where(MarketplaceAccount.organization_id == organization_id).where(MarketplaceAccount.account_status == ACCOUNT_STATUS_CONNECTED)
    ).all()
    verified_accounts = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.organization_id == organization_id)
        .where(MarketplaceAccount.verification_status == VERIFICATION_STATUS_VERIFIED)
    ).all()
    listing_rows = session.exec(select(MarketplaceListingDraft).where(MarketplaceListingDraft.organization_id == organization_id)).all()
    sync_runs = session.exec(select(MarketplaceInventorySyncRun).where(MarketplaceInventorySyncRun.organization_id == organization_id)).all()
    conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.organization_id == organization_id)
        .where(MarketplaceInventoryConflict.conflict_status != CONFLICT_STATUS_RESOLVED)
    ).all()
    orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.organization_id == organization_id)).all()
    transactions = session.exec(
        select(MarketplaceTransaction)
        .where(MarketplaceTransaction.organization_id == organization_id)
        .where(MarketplaceTransaction.transaction_status == TRANSACTION_STATUS_FAILED)
    ).all()
    recommendations = session.exec(
        select(MarketplacePriceRecommendation)
        .where(MarketplacePriceRecommendation.organization_id == organization_id)
        .where(MarketplacePriceRecommendation.recommendation_status == RECOMMENDATION_STATUS_GENERATED)
    ).all()
    offers = session.exec(
        select(MarketplaceOffer)
        .where(MarketplaceOffer.organization_id == organization_id)
        .where(MarketplaceOffer.offer_status == OFFER_STATUS_RECEIVED)
    ).all()
    events = session.exec(select(MarketplaceEvent).where(MarketplaceEvent.organization_id == organization_id)).all()
    event_runs = session.exec(
        select(MarketplaceEventProcessingRun)
        .where(MarketplaceEventProcessingRun.organization_id == organization_id)
        .where(MarketplaceEventProcessingRun.processing_status == EVENT_PROCESSING_STATUS_FAILED)
    ).all()
    live_sessions = session.exec(
        select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id).where(LiveSaleSession.session_status == SESSION_STATUS_LIVE)
    ).all()
    claims = session.exec(select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)).all()
    queue_items = session.exec(select(LiveSaleQueueItem).where(LiveSaleQueueItem.organization_id == organization_id)).all()
    latest_sync_run = session.exec(
        select(MarketplaceInventorySyncRun)
        .where(MarketplaceInventorySyncRun.organization_id == organization_id)
        .order_by(MarketplaceInventorySyncRun.started_at.desc(), MarketplaceInventorySyncRun.id.desc())
    ).first()

    return {
        "connected_marketplace_accounts": {"count": len(connected_accounts)},
        "verified_marketplace_accounts": {"count": len(verified_accounts)},
        "active_listing_drafts": {"count": sum(1 for row in listing_rows if row.listing_status != LISTING_STATUS_ARCHIVED)},
        "ready_listing_drafts": {"count": sum(1 for row in listing_rows if row.listing_status == LISTING_STATUS_READY)},
        "invalid_listing_drafts": {"count": sum(1 for row in listing_rows if row.validation_status == VALIDATION_STATUS_INVALID)},
        "latest_sync_run_status": {
            "status": latest_sync_run.sync_status if latest_sync_run is not None else "none",
            "sync_run_id": int(latest_sync_run.id or 0) if latest_sync_run is not None else None,
        },
        "open_sync_conflicts": {"count": len(conflicts)},
        "imported_orders_count": {"count": sum(1 for row in orders if row.order_status == ORDER_STATUS_IMPORTED)},
        "pending_orders_count": {"count": sum(1 for row in orders if row.order_status == ORDER_STATUS_PENDING)},
        "completed_orders_count": {"count": sum(1 for row in orders if row.order_status == ORDER_STATUS_COMPLETED)},
        "failed_orders_count": {"count": sum(1 for row in orders if row.order_status == ORDER_STATUS_CANCELLED)},
        "transaction_mismatches_count": {"count": len(transactions)},
        "pending_pricing_recommendations": {"count": len(recommendations)},
        "received_offers_count": {"count": len(offers)},
        "unprocessed_events_count": {"count": sum(1 for row in events if row.event_status != EVENT_STATUS_PROCESSED)},
        "failed_event_processing_runs_count": {"count": len(event_runs)},
        "active_live_sale_sessions": {"count": len(live_sessions)},
        "live_sale_claims_count": {"count": len(claims)},
        "active_live_sale_queue_items": {"count": len(queue_items)},
    }


def generate_marketplace_ops_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceOpsMetricListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:metrics_generate")
    payloads = _build_metric_payloads(session, organization_id=organization_id)
    rows: list[MarketplaceOpsMetric] = []
    now = utc_now()
    for definition in list_marketplace_ops_metric_definitions():
        row = MarketplaceOpsMetric(
            organization_id=organization_id,
            metric_key=definition.metric_key,
            metric_value_json=_json_safe(payloads[definition.metric_key]),
            metric_period=definition.metric_period,
            generated_at=now,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    create_marketplace_ops_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        event_type="marketplace_ops_metrics_generated",
        event_payload_json={"metric_keys": [definition.metric_key for definition in list_marketplace_ops_metric_definitions()]},
    )
    session.commit()
    return MarketplaceOpsMetricListResponse(
        items=[_metric_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_metrics(session: Session, *, organization_id: int) -> list[MarketplaceOpsMetricResponse]:
    rows = session.exec(
        select(MarketplaceOpsMetric)
        .where(MarketplaceOpsMetric.organization_id == organization_id)
        .order_by(MarketplaceOpsMetric.generated_at.desc(), MarketplaceOpsMetric.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="metric_key")
    order = {definition.metric_key: index for index, definition in enumerate(list_marketplace_ops_metric_definitions())}
    latest.sort(key=lambda row: (order.get(row.metric_key, 999), row.metric_key))
    return [_metric_response(row) for row in latest]


def generate_marketplace_diagnostics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceOpsDiagnosticListResponse:
    resolution = _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:diagnostics_generate")
    evaluated = evaluate_marketplace_ops_diagnostics(session, organization_id=organization_id)
    now = utc_now()
    rows: list[MarketplaceOpsDiagnostic] = []
    for result in evaluated:
        row = MarketplaceOpsDiagnostic(
            organization_id=organization_id,
            marketplace_account_id=None,
            diagnostic_category=result.diagnostic_category,
            diagnostic_status=result.diagnostic_status,
            diagnostic_code=result.diagnostic_code,
            diagnostic_message=result.diagnostic_message,
            diagnostic_payload_json=_json_safe(result.diagnostic_payload_json),
            created_at=now,
        )
        session.add(row)
        rows.append(row)
        create_marketplace_ops_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=None,
            event_type="marketplace_ops_diagnostic_created",
            event_payload_json={
                "diagnostic_code": result.diagnostic_code,
                "diagnostic_status": result.diagnostic_status,
                "diagnostic_category": result.diagnostic_category,
            },
        )
    session.flush()
    create_marketplace_ops_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        event_type="marketplace_ops_diagnostics_generated",
        event_payload_json={"diagnostic_codes": [row.diagnostic_code for row in rows]},
    )
    session.commit()
    return MarketplaceOpsDiagnosticListResponse(
        items=[_diagnostic_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=len(rows),
        limit=len(rows),
        offset=0,
    )


def _build_current_diagnostics(session: Session, *, organization_id: int) -> list[MarketplaceOpsDiagnosticResponse]:
    rows = session.exec(
        select(MarketplaceOpsDiagnostic)
        .where(MarketplaceOpsDiagnostic.organization_id == organization_id)
        .order_by(MarketplaceOpsDiagnostic.created_at.desc(), MarketplaceOpsDiagnostic.id.desc())
    ).all()
    latest = _latest_rows_by_key(list(rows), key_name="diagnostic_code")
    order = {definition.diagnostic_code: index for index, definition in enumerate(list_marketplace_ops_diagnostic_definitions())}
    latest.sort(key=lambda row: (order.get(row.diagnostic_code, 999), row.diagnostic_code))
    return [_diagnostic_response(row) for row in latest]


def list_marketplace_ops_snapshots(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceOpsSnapshotListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:snapshot:view")
    base = select(MarketplaceOpsSnapshot).where(MarketplaceOpsSnapshot.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(MarketplaceOpsSnapshot.generated_at.desc(), MarketplaceOpsSnapshot.id.desc()).offset(offset).limit(limit)).all()
    return MarketplaceOpsSnapshotListResponse(
        items=[_snapshot_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_marketplace_ops_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceOpsMetricListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:metric:view")
    metrics = _build_current_metrics(session, organization_id=organization_id)
    total = len(metrics)
    items = metrics[offset : offset + limit]
    return MarketplaceOpsMetricListResponse(
        items=items,
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_marketplace_ops_diagnostics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceOpsDiagnosticListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:diagnostic:view")
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    total = len(diagnostics)
    items = diagnostics[offset : offset + limit]
    return MarketplaceOpsDiagnosticListResponse(
        items=items,
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def _build_summary(session: Session, *, organization_id: int) -> dict[str, Any]:
    metrics = _build_current_metrics(session, organization_id=organization_id)
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    if metrics:
        metric_map = {metric.metric_key: metric.metric_value_json for metric in metrics}
    else:
        metric_map = _build_metric_payloads(session, organization_id=organization_id)
    if diagnostics:
        diagnostic_summary = summarize_marketplace_ops_diagnostics(diagnostics)
    else:
        diagnostic_summary = summarize_marketplace_ops_diagnostics(evaluate_marketplace_ops_diagnostics(session, organization_id=organization_id))
    summary: dict[str, Any] = {
        "accounts": {},
        "listings": {},
        "sync": {},
        "orders": {},
        "pricing": {},
        "events": {},
        "live_sales": {},
        "diagnostics": diagnostic_summary,
    }
    summary["accounts"] = {
        "connected": metric_map.get("connected_marketplace_accounts", {}).get("count", 0),
        "verified": metric_map.get("verified_marketplace_accounts", {}).get("count", 0),
    }
    summary["listings"] = {
        "active": metric_map.get("active_listing_drafts", {}).get("count", 0),
        "ready": metric_map.get("ready_listing_drafts", {}).get("count", 0),
        "invalid": metric_map.get("invalid_listing_drafts", {}).get("count", 0),
    }
    summary["sync"] = {
        "latest_status": metric_map.get("latest_sync_run_status", {}).get("status", "none"),
        "open_conflicts": metric_map.get("open_sync_conflicts", {}).get("count", 0),
    }
    summary["orders"] = {
        "imported": metric_map.get("imported_orders_count", {}).get("count", 0),
        "pending": metric_map.get("pending_orders_count", {}).get("count", 0),
        "completed": metric_map.get("completed_orders_count", {}).get("count", 0),
        "failed": metric_map.get("failed_orders_count", {}).get("count", 0),
        "transaction_mismatches": metric_map.get("transaction_mismatches_count", {}).get("count", 0),
    }
    summary["pricing"] = {
        "pending_recommendations": metric_map.get("pending_pricing_recommendations", {}).get("count", 0),
        "received_offers": metric_map.get("received_offers_count", {}).get("count", 0),
    }
    summary["events"] = {
        "unprocessed_events": metric_map.get("unprocessed_events_count", {}).get("count", 0),
        "failed_processing_runs": metric_map.get("failed_event_processing_runs_count", {}).get("count", 0),
    }
    summary["live_sales"] = {
        "active_sessions": metric_map.get("active_live_sale_sessions", {}).get("count", 0),
        "claims": metric_map.get("live_sale_claims_count", {}).get("count", 0),
    }
    return _json_safe(summary)


def build_marketplace_ops_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceOpsDashboardResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:view")
    create_marketplace_ops_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        event_type="marketplace_ops_dashboard_accessed",
        event_payload_json={"action": "marketplace_ops:view"},
    )
    session.commit()
    metrics = _build_current_metrics(session, organization_id=organization_id)
    diagnostics = _build_current_diagnostics(session, organization_id=organization_id)
    snapshots = list_marketplace_ops_snapshots(session, organization_id=organization_id, actor_user_id=actor_user_id, limit=20, offset=0).items
    events = session.exec(
        select(MarketplaceOpsEvent)
        .where(MarketplaceOpsEvent.organization_id == organization_id)
        .order_by(MarketplaceOpsEvent.created_at.desc(), MarketplaceOpsEvent.id.desc())
        .limit(25)
    ).all()
    latest_snapshot = snapshots[0] if snapshots else None
    return MarketplaceOpsDashboardResponse(
        permissions=_permission_response(resolution),
        summary=_build_summary(session, organization_id=organization_id),
        metrics=metrics,
        diagnostics=diagnostics,
        snapshots=snapshots,
        events=[_event_response(row) for row in events],
        latest_snapshot=latest_snapshot,
    )


def generate_marketplace_ops_snapshot(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    snapshot_type: str = "full_dashboard_snapshot",
) -> MarketplaceOpsSnapshotResponse:
    _validate_management(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_ops:snapshot_generate")
    metric_list = generate_marketplace_ops_metrics(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    diagnostic_list = generate_marketplace_diagnostics(session, organization_id=organization_id, actor_user_id=actor_user_id).items
    payload = _json_safe(
        {
            "snapshot_type": snapshot_type,
            "summary": _build_summary(session, organization_id=organization_id),
            "metrics": [metric.model_dump(mode="json") for metric in metric_list],
            "diagnostics": [diagnostic.model_dump(mode="json") for diagnostic in diagnostic_list],
        }
    )
    row = MarketplaceOpsSnapshot(
        organization_id=organization_id,
        snapshot_type=snapshot_type,
        snapshot_payload_json=payload,
        generated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_marketplace_ops_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        event_type="marketplace_ops_snapshot_generated",
        event_payload_json={"snapshot_type": snapshot_type, "snapshot_id": int(row.id or 0)},
    )
    session.commit()
    return _snapshot_response(row)
