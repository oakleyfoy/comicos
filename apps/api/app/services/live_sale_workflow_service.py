from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import LiveSaleEvent, LiveSaleQueueItem, LiveSaleSession, MarketplaceAccount
from app.schemas.live_sale_workflows import (
    LiveSaleDetailResponse,
    LiveSaleEventResponse,
    LiveSalePermissionResponse,
    LiveSaleQueueItemResponse,
    LiveSaleSessionCreateRequest,
    LiveSaleSessionListResponse,
    LiveSaleSessionResponse,
    LiveSaleSessionUpdateRequest,
    LiveSaleSummaryResponse,
)
from app.services.live_sale_queue_service import (
    QUEUE_ITEM_STATUS_ACTIVE,
    QUEUE_ITEM_STATUS_PASSED,
    QUEUE_ITEM_STATUS_QUEUED,
    QUEUE_ITEM_STATUS_REMOVED,
    QUEUE_ITEM_STATUS_SOLD,
    add_item_to_live_sale_queue,
    clamp_pagination,
    list_live_sale_queue,
    resolve_next_queue_item,
    _to_queue_item_response,
    _queue_item_or_404,
    validate_queue_item_eligibility,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions

SESSION_STATUS_PLANNED = "planned"
SESSION_STATUS_LIVE = "live"
SESSION_STATUS_ENDED = "ended"
SESSION_STATUS_CANCELLED = "cancelled"
SESSION_STATUSES = {SESSION_STATUS_PLANNED, SESSION_STATUS_LIVE, SESSION_STATUS_ENDED, SESSION_STATUS_CANCELLED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


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


def _permission_response(resolution: MarketplacePermissionResolution) -> LiveSalePermissionResponse:
    return LiveSalePermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _session_or_404(session: Session, *, organization_id: int, session_id: int) -> LiveSaleSession:
    row = session.get(LiveSaleSession, session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Live-sale session not found.")
    return row


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    row = session.get(MarketplaceAccount, marketplace_account_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return row


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
    live_sale_session_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_live_sale_event(
            session,
            organization_id=organization_id,
            live_sale_session_id=live_sale_session_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_live_sale_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail=f"Live-sale visibility is denied for {action}.")
    return resolution


def _validate_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
    live_sale_session_id: int | None = None,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_live_sale_event(
            session,
            organization_id=organization_id,
            live_sale_session_id=live_sale_session_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_live_sale_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail=f"Live-sale management is denied for {action}.")
    return resolution


def create_live_sale_event(
    session: Session,
    *,
    organization_id: int,
    live_sale_session_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> LiveSaleEvent:
    row = LiveSaleEvent(
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _to_session_response(row: LiveSaleSession) -> LiveSaleSessionResponse:
    return LiveSaleSessionResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        session_name=row.session_name,
        session_status=row.session_status,
        planned_start_at=row.planned_start_at,
        planned_end_at=row.planned_end_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_queue_item_response(row: LiveSaleQueueItem) -> LiveSaleQueueItemResponse:
    return LiveSaleQueueItemResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        live_sale_session_id=row.live_sale_session_id,
        inventory_item_id=row.inventory_item_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        queue_position=row.queue_position,
        item_status=row.item_status,
        planned_price=row.planned_price,
        actual_sale_price=row.actual_sale_price,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_event_response(row: LiveSaleEvent) -> LiveSaleEventResponse:
    return LiveSaleEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        live_sale_session_id=row.live_sale_session_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _detail_response(
    session: Session,
    *,
    live_sale_session: LiveSaleSession,
    resolution: MarketplacePermissionResolution,
) -> LiveSaleDetailResponse:
    from app.services.live_sale_claim_service import list_live_sale_claims

    queue_items = list_live_sale_queue(
        session,
        organization_id=live_sale_session.organization_id,
        actor_user_id=resolution.actor_user_id,
        live_sale_session_id=int(live_sale_session.id or 0),
        limit=200,
        offset=0,
    )
    claims = list_live_sale_claims(
        session,
        organization_id=live_sale_session.organization_id,
        actor_user_id=resolution.actor_user_id,
        live_sale_session_id=int(live_sale_session.id or 0),
        limit=200,
        offset=0,
    ).items
    events = session.exec(
        select(LiveSaleEvent)
        .where(LiveSaleEvent.live_sale_session_id == live_sale_session.id)
        .order_by(LiveSaleEvent.created_at.asc(), LiveSaleEvent.id.asc())
    ).all()
    return LiveSaleDetailResponse(
        session=_to_session_response(live_sale_session),
        permissions=_permission_response(resolution),
        queue_items=[_to_queue_item_response(row) for row in queue_items.items],
        claims=claims,
        events=[_to_event_response(row) for row in events],
    )


def create_live_sale_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: LiveSaleSessionCreateRequest,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:create",
    )
    _account_or_404(session, organization_id=organization_id, marketplace_account_id=payload.marketplace_account_id)
    row = LiveSaleSession(
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        session_name=payload.session_name.strip(),
        session_status=SESSION_STATUS_PLANNED,
        planned_start_at=payload.planned_start_at,
        planned_end_at=payload.planned_end_at,
        started_at=None,
        ended_at=None,
        created_by_user_id=actor_user_id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=int(row.id or 0),
        actor_user_id=actor_user_id,
        event_type="live_sale_session_created",
        event_payload_json={"session_name": row.session_name, "session_status": row.session_status},
    )
    session.commit()
    return _detail_response(session, live_sale_session=row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def update_live_sale_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    payload: LiveSaleSessionUpdateRequest,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:update",
        live_sale_session_id=session_id,
    )
    row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    if payload.session_name is not None:
        row.session_name = payload.session_name.strip()
    if payload.planned_start_at is not None:
        row.planned_start_at = payload.planned_start_at
    if payload.planned_end_at is not None:
        row.planned_end_at = payload.planned_end_at
    if payload.session_status is not None:
        normalized = payload.session_status.strip().lower()
        if normalized not in SESSION_STATUSES:
            raise HTTPException(status_code=422, detail="Unsupported live-sale session status.")
        row.session_status = normalized
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=int(row.id or 0),
        actor_user_id=actor_user_id,
        event_type="live_sale_session_updated",
        event_payload_json={"session_status": row.session_status, "session_name": row.session_name},
    )
    session.commit()
    return _detail_response(session, live_sale_session=row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def start_live_sale_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:start",
        live_sale_session_id=session_id,
    )
    row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    if row.session_status not in {SESSION_STATUS_PLANNED, SESSION_STATUS_CANCELLED}:
        raise HTTPException(status_code=422, detail="Live-sale session cannot be started from its current status.")
    row.session_status = SESSION_STATUS_LIVE
    row.started_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=int(row.id or 0),
        actor_user_id=actor_user_id,
        event_type="live_sale_session_started",
        event_payload_json={"session_status": row.session_status},
    )
    session.commit()
    return _detail_response(session, live_sale_session=row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def end_live_sale_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:end",
        live_sale_session_id=session_id,
    )
    row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    if row.session_status not in {SESSION_STATUS_LIVE, SESSION_STATUS_PLANNED}:
        raise HTTPException(status_code=422, detail="Live-sale session cannot be ended from its current status.")
    row.session_status = SESSION_STATUS_ENDED
    row.ended_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=int(row.id or 0),
        actor_user_id=actor_user_id,
        event_type="live_sale_session_ended",
        event_payload_json={"session_status": row.session_status},
    )
    session.commit()
    return _detail_response(session, live_sale_session=row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def mark_queue_item_active(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    queue_item_id: int,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:activate",
        live_sale_session_id=session_id,
    )
    session_row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    if session_row.session_status != SESSION_STATUS_LIVE:
        raise HTTPException(status_code=422, detail="Live-sale session must be live to activate items.")
    row = _queue_item_or_404(session, organization_id=organization_id, live_sale_session_id=session_id, queue_item_id=queue_item_id)
    row.item_status = QUEUE_ITEM_STATUS_ACTIVE
    row.updated_at = utc_now()
    session.add(row)
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_item_active",
        event_payload_json={"queue_item_id": queue_item_id},
    )
    session.commit()
    return _detail_response(session, live_sale_session=session_row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def mark_queue_item_sold(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    queue_item_id: int,
    actual_sale_price: Decimal | None = None,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:sold",
        live_sale_session_id=session_id,
    )
    session_row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    row = _queue_item_or_404(session, organization_id=organization_id, live_sale_session_id=session_id, queue_item_id=queue_item_id)
    row.item_status = QUEUE_ITEM_STATUS_SOLD
    row.actual_sale_price = _normalize_decimal(actual_sale_price) if actual_sale_price is not None else row.actual_sale_price
    row.updated_at = utc_now()
    session.add(row)
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_item_sold",
        event_payload_json={"queue_item_id": queue_item_id, "actual_sale_price": str(row.actual_sale_price) if row.actual_sale_price is not None else None},
    )
    session.commit()
    return _detail_response(session, live_sale_session=session_row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def mark_queue_item_passed(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    queue_item_id: int,
) -> LiveSaleDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:passed",
        live_sale_session_id=session_id,
    )
    session_row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    row = _queue_item_or_404(session, organization_id=organization_id, live_sale_session_id=session_id, queue_item_id=queue_item_id)
    row.item_status = QUEUE_ITEM_STATUS_PASSED
    row.updated_at = utc_now()
    session.add(row)
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_item_passed",
        event_payload_json={"queue_item_id": queue_item_id},
    )
    session.commit()
    return _detail_response(session, live_sale_session=session_row, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def list_live_sale_sessions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> LiveSaleSessionListResponse:
    resolution = _validate_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:view",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(LiveSaleSession).where(LiveSaleSession.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(base.order_by(LiveSaleSession.created_at.desc(), LiveSaleSession.id.desc()).offset(offset).limit(limit)).all()
    all_rows = session.exec(base).all()
    summary = LiveSaleSummaryResponse(
        total_sessions=total,
        live_sessions=sum(1 for row in all_rows if row.session_status == SESSION_STATUS_LIVE),
        planned_sessions=sum(1 for row in all_rows if row.session_status == SESSION_STATUS_PLANNED),
        ended_sessions=sum(1 for row in all_rows if row.session_status == SESSION_STATUS_ENDED),
        cancelled_sessions=sum(1 for row in all_rows if row.session_status == SESSION_STATUS_CANCELLED),
    )
    return LiveSaleSessionListResponse(
        items=[_to_session_response(row) for row in rows],
        permissions=_permission_response(resolution),
        summary=summary,
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_live_sale_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
) -> LiveSaleDetailResponse:
    resolution = _validate_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_session:view",
        live_sale_session_id=session_id,
    )
    row = _session_or_404(session, organization_id=organization_id, session_id=session_id)
    return _detail_response(session, live_sale_session=row, resolution=resolution)
