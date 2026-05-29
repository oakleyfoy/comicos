from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import LiveSaleClaim, LiveSaleQueueItem, LiveSaleSession
from app.schemas.live_sale_workflows import (
    LiveSaleClaimCreateRequest,
    LiveSaleClaimListResponse,
    LiveSaleClaimResponse,
    LiveSaleClaimSummaryResponse,
    LiveSaleClaimUpdateRequest,
    LiveSalePermissionResponse,
)
from app.services.live_sale_workflow_service import create_live_sale_event
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions

CLAIM_STATUS_CLAIMED = "claimed"
CLAIM_STATUS_CONFIRMED = "confirmed"
CLAIM_STATUS_CANCELLED = "cancelled"
CLAIM_STATUSES = {CLAIM_STATUS_CLAIMED, CLAIM_STATUS_CONFIRMED, CLAIM_STATUS_CANCELLED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


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


def _session_or_404(session: Session, *, organization_id: int, live_sale_session_id: int) -> LiveSaleSession:
    row = session.get(LiveSaleSession, live_sale_session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Live-sale session not found.")
    return row


def _queue_item_or_404(session: Session, *, organization_id: int, live_sale_queue_item_id: int, live_sale_session_id: int) -> LiveSaleQueueItem:
    row = session.get(LiveSaleQueueItem, live_sale_queue_item_id)
    if row is None or row.organization_id != organization_id or row.live_sale_session_id != live_sale_session_id:
        raise HTTPException(status_code=404, detail="Live-sale queue item not found.")
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
        from app.services.live_sale_workflow_service import create_live_sale_event

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
        from app.services.live_sale_workflow_service import create_live_sale_event

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


def detect_duplicate_claim(
    session: Session,
    *,
    live_sale_session_id: int,
    live_sale_queue_item_id: int,
    buyer_identifier: str,
) -> LiveSaleClaim | None:
    return session.exec(
        select(LiveSaleClaim)
        .where(LiveSaleClaim.live_sale_session_id == live_sale_session_id)
        .where(LiveSaleClaim.live_sale_queue_item_id == live_sale_queue_item_id)
        .where(LiveSaleClaim.buyer_identifier == buyer_identifier.strip())
        .order_by(LiveSaleClaim.id.asc())
    ).first()


def _to_claim_response(row: LiveSaleClaim) -> LiveSaleClaimResponse:
    return LiveSaleClaimResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        live_sale_session_id=row.live_sale_session_id,
        live_sale_queue_item_id=row.live_sale_queue_item_id,
        buyer_identifier=row.buyer_identifier,
        claim_status=row.claim_status,
        claimed_price=row.claimed_price,
        claimed_at=row.claimed_at,
        created_at=row.created_at,
    )


def generate_live_sale_claim_summary(session: Session, *, organization_id: int) -> LiveSaleClaimSummaryResponse:
    rows = session.exec(select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)).all()
    return LiveSaleClaimSummaryResponse(
        total_claims=len(rows),
        claimed_claims=sum(1 for row in rows if row.claim_status == CLAIM_STATUS_CLAIMED),
        confirmed_claims=sum(1 for row in rows if row.claim_status == CLAIM_STATUS_CONFIRMED),
        cancelled_claims=sum(1 for row in rows if row.claim_status == CLAIM_STATUS_CANCELLED),
    )


def create_live_sale_claim(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    payload: LiveSaleClaimCreateRequest,
) -> LiveSaleClaimResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_claim:create",
        live_sale_session_id=live_sale_session_id,
    )
    _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    queue_item = _queue_item_or_404(
        session,
        organization_id=organization_id,
        live_sale_queue_item_id=payload.live_sale_queue_item_id,
        live_sale_session_id=live_sale_session_id,
    )
    duplicate = detect_duplicate_claim(
        session,
        live_sale_session_id=live_sale_session_id,
        live_sale_queue_item_id=payload.live_sale_queue_item_id,
        buyer_identifier=payload.buyer_identifier,
    )
    if duplicate is not None:
        create_live_sale_event(
            session,
            organization_id=organization_id,
            live_sale_session_id=live_sale_session_id,
            actor_user_id=actor_user_id,
            event_type="duplicate_live_sale_claim_detected",
            event_payload_json={
                "live_sale_queue_item_id": payload.live_sale_queue_item_id,
                "buyer_identifier": payload.buyer_identifier,
            },
        )
        session.commit()
        return _to_claim_response(duplicate)

    claim_status = payload.claimed_status.strip().lower()
    if claim_status not in CLAIM_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported live-sale claim status.")
    row = LiveSaleClaim(
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        live_sale_queue_item_id=payload.live_sale_queue_item_id,
        buyer_identifier=payload.buyer_identifier.strip(),
        claim_status=claim_status,
        claimed_price=_normalize_decimal(payload.claimed_price) if payload.claimed_price is not None else None,
        claimed_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_claim_created",
        event_payload_json={
            "live_sale_queue_item_id": queue_item.id,
            "buyer_identifier": row.buyer_identifier,
            "claim_status": row.claim_status,
        },
    )
    session.commit()
    return _to_claim_response(row)


def update_claim_status(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    claim_id: int,
    payload: LiveSaleClaimUpdateRequest,
) -> LiveSaleClaimResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_claim:update",
        live_sale_session_id=live_sale_session_id,
    )
    _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    row = session.get(LiveSaleClaim, claim_id)
    if row is None or row.organization_id != organization_id or row.live_sale_session_id != live_sale_session_id:
        raise HTTPException(status_code=404, detail="Live-sale claim not found.")
    claim_status = payload.claim_status.strip().lower()
    if claim_status not in CLAIM_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported live-sale claim status.")
    row.claim_status = claim_status
    session.add(row)
    session.flush()
    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_claim_status_updated",
        event_payload_json={"claim_id": claim_id, "claim_status": row.claim_status},
    )
    session.commit()
    return _to_claim_response(row)


def list_live_sale_claims(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    limit: int,
    offset: int,
) -> LiveSaleClaimListResponse:
    resolution = _validate_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_claim:view",
        live_sale_session_id=live_sale_session_id,
    )
    _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(LiveSaleClaim).where(LiveSaleClaim.organization_id == organization_id)
    rows = session.exec(
        base.where(LiveSaleClaim.live_sale_session_id == live_sale_session_id)
        .order_by(LiveSaleClaim.created_at.asc(), LiveSaleClaim.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(session.exec(base.where(LiveSaleClaim.live_sale_session_id == live_sale_session_id)).all())
    summary = generate_live_sale_claim_summary(session, organization_id=organization_id)
    return LiveSaleClaimListResponse(
        items=[_to_claim_response(row) for row in rows],
        permissions=_permission_response(resolution),
        summary=summary,
        total_items=total,
        limit=limit,
        offset=offset,
    )
