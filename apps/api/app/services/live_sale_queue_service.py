from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy, LiveSaleQueueItem, LiveSaleSession, MarketplaceListingDraft
from app.schemas.live_sale_workflows import (
    LiveSalePermissionResponse,
    LiveSaleQueueItemListResponse,
    LiveSaleQueueItemResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution, resolve_marketplace_permissions

QUEUE_ITEM_STATUS_QUEUED = "queued"
QUEUE_ITEM_STATUS_ACTIVE = "active"
QUEUE_ITEM_STATUS_SOLD = "sold"
QUEUE_ITEM_STATUS_PASSED = "passed"
QUEUE_ITEM_STATUS_REMOVED = "removed"
QUEUE_ITEM_STATUSES = {
    QUEUE_ITEM_STATUS_QUEUED,
    QUEUE_ITEM_STATUS_ACTIVE,
    QUEUE_ITEM_STATUS_SOLD,
    QUEUE_ITEM_STATUS_PASSED,
    QUEUE_ITEM_STATUS_REMOVED,
}


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


def _session_or_404(session: Session, *, organization_id: int, live_sale_session_id: int) -> LiveSaleSession:
    row = session.get(LiveSaleSession, live_sale_session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Live-sale session not found.")
    return row


def _queue_item_or_404(session: Session, *, organization_id: int, live_sale_session_id: int, queue_item_id: int) -> LiveSaleQueueItem:
    row = session.get(LiveSaleQueueItem, queue_item_id)
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
        raise HTTPException(status_code=403, detail=f"Marketplace visibility is denied for {action}.")
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
        raise HTTPException(status_code=403, detail=f"Marketplace management is denied for {action}.")
    return resolution


def _permission_response(resolution: MarketplacePermissionResolution) -> LiveSalePermissionResponse:
    return LiveSalePermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def validate_queue_item_eligibility(
    session: Session,
    *,
    organization_id: int,
    live_sale_session_id: int,
    inventory_item_id: int,
    marketplace_listing_draft_id: int,
) -> None:
    session_row = _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    if session_row.session_status in {"ended", "cancelled"}:
        raise HTTPException(status_code=422, detail="Live-sale session is not open for queue changes.")
    inventory = session.get(InventoryCopy, inventory_item_id)
    listing = session.get(MarketplaceListingDraft, marketplace_listing_draft_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    if listing is None or listing.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace listing draft not found.")


def add_item_to_live_sale_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    inventory_item_id: int,
    marketplace_listing_draft_id: int,
    planned_price: Decimal | None = None,
) -> LiveSaleQueueItem:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:add",
        live_sale_session_id=live_sale_session_id,
    )
    validate_queue_item_eligibility(
        session,
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        inventory_item_id=inventory_item_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
    )
    existing = session.exec(
        select(LiveSaleQueueItem)
        .where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
        .where(LiveSaleQueueItem.inventory_item_id == inventory_item_id)
        .order_by(LiveSaleQueueItem.id.asc())
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Inventory item already exists in live-sale queue.")
    max_position = session.exec(
        select(LiveSaleQueueItem.queue_position)
        .where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
        .order_by(LiveSaleQueueItem.queue_position.desc())
    ).first()
    row = LiveSaleQueueItem(
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        inventory_item_id=inventory_item_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
        queue_position=int(max_position or 0) + 1,
        item_status=QUEUE_ITEM_STATUS_QUEUED,
        planned_price=_normalize_decimal(planned_price) if planned_price is not None else None,
        actual_sale_price=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    from app.services.live_sale_workflow_service import create_live_sale_event

    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_queue_item_added",
        event_payload_json={
            "queue_item_id": int(row.id or 0),
            "inventory_item_id": inventory_item_id,
            "marketplace_listing_draft_id": marketplace_listing_draft_id,
            "queue_position": row.queue_position,
        },
    )
    session.commit()
    return row


def remove_item_from_live_sale_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    queue_item_id: int,
) -> LiveSaleQueueItem:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:remove",
        live_sale_session_id=live_sale_session_id,
    )
    row = _queue_item_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id, queue_item_id=queue_item_id)
    row.item_status = QUEUE_ITEM_STATUS_REMOVED
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    session.commit()
    return row


def reorder_live_sale_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    queue_item_ids: list[int],
) -> list[LiveSaleQueueItem]:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:reorder",
        live_sale_session_id=live_sale_session_id,
    )
    session_row = _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    if session_row.session_status in {"ended", "cancelled"}:
        raise HTTPException(status_code=422, detail="Live-sale session is not open for queue changes.")
    queue_rows = session.exec(
        select(LiveSaleQueueItem)
        .where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
        .order_by(LiveSaleQueueItem.queue_position.asc(), LiveSaleQueueItem.id.asc())
    ).all()
    queue_map = {row.id: row for row in queue_rows if row.id is not None}
    if set(queue_item_ids) != set(queue_map):
        raise HTTPException(status_code=422, detail="Queue reorder must include every live-sale queue item exactly once.")
    for position, queue_item_id in enumerate(queue_item_ids, start=1):
        row = queue_map.get(queue_item_id)
        if row is None:
            raise HTTPException(status_code=422, detail="Queue reorder contains an unknown queue item.")
        row.queue_position = position
        row.updated_at = utc_now()
        session.add(row)
    session.flush()
    from app.services.live_sale_workflow_service import create_live_sale_event

    create_live_sale_event(
        session,
        organization_id=organization_id,
        live_sale_session_id=live_sale_session_id,
        actor_user_id=actor_user_id,
        event_type="live_sale_queue_reordered",
        event_payload_json={"queue_item_ids": queue_item_ids},
    )
    session.commit()
    return list(
        session.exec(
            select(LiveSaleQueueItem)
            .where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
            .order_by(LiveSaleQueueItem.queue_position.asc(), LiveSaleQueueItem.id.asc())
        ).all()
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


def list_live_sale_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
    limit: int,
    offset: int,
) -> LiveSaleQueueItemListResponse:
    resolution = _validate_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:view",
        live_sale_session_id=live_sale_session_id,
    )
    _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(LiveSaleQueueItem).where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(LiveSaleQueueItem.queue_position.asc(), LiveSaleQueueItem.id.asc()).offset(offset).limit(limit)
    ).all()
    return LiveSaleQueueItemListResponse(
        items=[_to_queue_item_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def resolve_next_queue_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    live_sale_session_id: int,
) -> LiveSaleQueueItem | None:
    _validate_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="live_sale_queue:resolve",
        live_sale_session_id=live_sale_session_id,
    )
    _session_or_404(session, organization_id=organization_id, live_sale_session_id=live_sale_session_id)
    return session.exec(
        select(LiveSaleQueueItem)
        .where(LiveSaleQueueItem.live_sale_session_id == live_sale_session_id)
        .where(LiveSaleQueueItem.item_status == QUEUE_ITEM_STATUS_QUEUED)
        .order_by(LiveSaleQueueItem.queue_position.asc(), LiveSaleQueueItem.id.asc())
    ).first()
