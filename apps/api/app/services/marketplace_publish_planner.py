from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceDefinition as MarketplaceConnectorDefinition
from app.models.marketplace_listing import MarketplaceListingMapping
from app.schemas.marketplace_publish import MarketplacePublishRequest
from app.services.marketplace_listings import _owner_listing_or_404


def map_canonical_listing_to_payload(session: Session, *, owner_id: int, listing_id: int) -> dict[str, Any]:
    detail = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    return {
        "listing_uuid": detail.listing_uuid,
        "listing_title": detail.listing_title,
        "listing_description": detail.listing_description,
        "listing_type": detail.listing_type,
        "condition_label": detail.condition_label,
        "grade_label": detail.grade_label,
        "asking_price": str(detail.asking_price),
        "currency": detail.currency,
        "quantity": detail.quantity,
        "inventory_copy_id": detail.inventory_copy_id,
    }


def _mapping_for_target(
    session: Session,
    *,
    listing_id: int,
    marketplace_id: int,
    marketplace_account_id: int | None,
) -> MarketplaceListingMapping | None:
    rows = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .where(MarketplaceListingMapping.marketplace_id == marketplace_id)
        .order_by(MarketplaceListingMapping.created_at.asc(), MarketplaceListingMapping.id.asc())
    ).all()
    if marketplace_account_id is None:
        return rows[0] if rows else None
    for row in rows:
        if row.marketplace_account_id == marketplace_account_id:
            return row
    return None


def build_target_payload(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    marketplace_id: int,
    marketplace_account_id: int | None,
) -> tuple[dict[str, Any], int | None]:
    listing_payload = map_canonical_listing_to_payload(session, owner_id=owner_id, listing_id=listing_id)
    marketplace = session.get(MarketplaceConnectorDefinition, marketplace_id)
    mapping = _mapping_for_target(
        session,
        listing_id=listing_id,
        marketplace_id=marketplace_id,
        marketplace_account_id=marketplace_account_id,
    )
    payload = {
        "canonical_listing": listing_payload,
        "marketplace": {
            "marketplace_id": marketplace_id,
            "marketplace_code": marketplace.marketplace_code if marketplace else None,
            "marketplace_name": marketplace.marketplace_name if marketplace else None,
            "marketplace_account_id": marketplace_account_id,
        },
        "mapping": {
            "listing_mapping_id": int(mapping.id or 0) if mapping is not None else None,
            "external_listing_id": mapping.external_listing_id if mapping is not None else None,
            "external_url": mapping.external_url if mapping is not None else None,
            "sync_status": mapping.sync_status if mapping is not None else None,
        },
    }
    return payload, (int(mapping.id or 0) if mapping is not None else None)


def build_publish_plan(session: Session, *, owner_id: int, payload: MarketplacePublishRequest) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for target in payload.targets:
        planned_payload, listing_mapping_id = build_target_payload(
            session,
            owner_id=owner_id,
            listing_id=payload.listing_id,
            marketplace_id=target.marketplace_id,
            marketplace_account_id=target.marketplace_account_id,
        )
        plan.append(
            {
                "marketplace_id": target.marketplace_id,
                "marketplace_account_id": target.marketplace_account_id,
                "listing_mapping_id": listing_mapping_id,
                "planned_payload_json": planned_payload,
            }
        )
    return plan
