from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingMapping
from app.models.marketplace_sync import MarketplaceInventorySyncPlan, MarketplaceInventorySyncPlanItem
from app.schemas.marketplace_sync import (
    MarketplaceInventorySyncPlanDetail,
    MarketplaceInventorySyncPlanGenerateRequest,
    MarketplaceInventorySyncPlanItemRead,
    MarketplaceInventorySyncPlanListResponse,
    MarketplaceInventorySyncPlanRead,
)
from app.services.marketplace_inventory_availability import get_availability
from app.services.marketplace_listings import _clamp


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _plan_read(row: MarketplaceInventorySyncPlan) -> MarketplaceInventorySyncPlanRead:
    return MarketplaceInventorySyncPlanRead(
        id=int(row.id or 0),
        owner_id=row.owner_id,
        plan_uuid=row.plan_uuid,
        plan_type=row.plan_type,
        status=row.status,
        generated_at=row.generated_at,
        created_at=row.created_at,
    )


def _plan_item_read(row: MarketplaceInventorySyncPlanItem) -> MarketplaceInventorySyncPlanItemRead:
    return MarketplaceInventorySyncPlanItemRead(
        id=int(row.id or 0),
        plan_id=row.plan_id,
        listing_id=row.listing_id,
        marketplace_id=row.marketplace_id,
        marketplace_account_id=row.marketplace_account_id,
        current_available_quantity=row.current_available_quantity,
        target_available_quantity=row.target_available_quantity,
        action_type=row.action_type,
        reason=row.reason,
        created_at=row.created_at,
    )


def _plan_or_404(session: Session, *, plan_id: int) -> MarketplaceInventorySyncPlan:
    row = session.get(MarketplaceInventorySyncPlan, plan_id)
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Marketplace inventory sync plan not found.")
    return row


def _owner_plan_or_404(session: Session, *, owner_id: int, plan_id: int) -> MarketplaceInventorySyncPlan:
    row = _plan_or_404(session, plan_id=plan_id)
    if row.owner_id != owner_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Marketplace inventory sync plan not found.")
    return row


def compare_listing_availability_to_mappings(session: Session, *, owner_id: int, listing_id: int) -> list[dict]:
    availability = get_availability(session, owner_id=owner_id, listing_id=listing_id)
    mappings = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .order_by(MarketplaceListingMapping.created_at.asc(), MarketplaceListingMapping.id.asc())
    ).all()
    comparisons: list[dict] = []
    for mapping in mappings:
        current_available_quantity = availability.available_quantity
        target_available_quantity = availability.available_quantity
        if target_available_quantity <= 0:
            action_type = "PAUSE_LISTING"
            reason = "available_quantity_zero"
        elif mapping.sync_status.upper() == "PAUSED":
            action_type = "RESUME_LISTING"
            reason = "listing_has_available_quantity"
        elif mapping.external_listing_id:
            action_type = "UPDATE_QUANTITY"
            reason = "listing_quantity_changed"
        else:
            action_type = "NOOP"
            reason = "no_external_listing_id"
        comparisons.append(
            {
                "listing_id": listing_id,
                "marketplace_id": mapping.marketplace_id,
                "marketplace_account_id": mapping.marketplace_account_id,
                "current_available_quantity": current_available_quantity,
                "target_available_quantity": target_available_quantity,
                "action_type": action_type,
                "reason": reason,
            }
        )
    if not comparisons:
        comparisons.append(
            {
                "listing_id": listing_id,
                "marketplace_id": None,
                "marketplace_account_id": None,
                "current_available_quantity": availability.available_quantity,
                "target_available_quantity": availability.available_quantity,
                "action_type": "NOOP",
                "reason": "no_marketplace_mappings",
            }
        )
    return comparisons


def create_plan_items(session: Session, *, plan_id: int, comparisons: list[dict]) -> None:
    now = utc_now()
    for comparison in comparisons:
        session.add(
            MarketplaceInventorySyncPlanItem(
                plan_id=plan_id,
                listing_id=comparison["listing_id"],
                marketplace_id=comparison["marketplace_id"],
                marketplace_account_id=comparison["marketplace_account_id"],
                current_available_quantity=comparison["current_available_quantity"],
                target_available_quantity=comparison["target_available_quantity"],
                action_type=comparison["action_type"],
                reason=comparison["reason"],
                created_at=now,
            )
        )


def generate_sync_plan(
    session: Session,
    *,
    owner_id: int,
    payload: MarketplaceInventorySyncPlanGenerateRequest,
) -> MarketplaceInventorySyncPlanDetail:
    listing_query = select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_id)
    if payload.listing_ids:
        listing_query = listing_query.where(MarketplaceListing.id.in_(payload.listing_ids))
    listings = session.exec(listing_query.order_by(MarketplaceListing.created_at.asc(), MarketplaceListing.id.asc())).all()
    row = MarketplaceInventorySyncPlan(
        owner_id=owner_id,
        plan_type="AVAILABILITY_RECONCILIATION",
        status="GENERATED",
        generated_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    for listing in listings:
        comparisons = compare_listing_availability_to_mappings(session, owner_id=owner_id, listing_id=int(listing.id or 0))
        filtered = [
            comparison
            for comparison in comparisons
            if not payload.marketplace_ids or comparison["marketplace_id"] in set(payload.marketplace_ids)
        ]
        create_plan_items(session, plan_id=int(row.id or 0), comparisons=filtered)
    session.commit()
    session.refresh(row)
    return get_sync_plan(session, owner_id=owner_id, plan_id=int(row.id or 0))


def get_sync_plan(session: Session, *, owner_id: int, plan_id: int) -> MarketplaceInventorySyncPlanDetail:
    row = _owner_plan_or_404(session, owner_id=owner_id, plan_id=plan_id)
    items = session.exec(
        select(MarketplaceInventorySyncPlanItem)
        .where(MarketplaceInventorySyncPlanItem.plan_id == plan_id)
        .order_by(MarketplaceInventorySyncPlanItem.created_at.asc(), MarketplaceInventorySyncPlanItem.id.asc())
    ).all()
    return MarketplaceInventorySyncPlanDetail(
        plan=_plan_read(row),
        items=[_plan_item_read(item) for item in items],
    )


def list_sync_plans(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceInventorySyncPlanListResponse:
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceInventorySyncPlan)
        .where(MarketplaceInventorySyncPlan.owner_id == owner_id)
        .order_by(MarketplaceInventorySyncPlan.created_at.asc(), MarketplaceInventorySyncPlan.id.asc())
    ).all()
    items = [_plan_read(row) for row in rows]
    return MarketplaceInventorySyncPlanListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )
