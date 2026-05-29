from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    MarketplaceListingDraft,
    MarketplaceListingProjection,
    Publisher,
    Variant,
)
from app.services.marketplace_registry import get_marketplace_definition

PROJECTION_STATUS_CURRENT = "current"
PROJECTION_STATUS_SUPERSEDED = "superseded"


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


def normalize_listing_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _json_safe(payload)
    assert isinstance(normalized, dict)
    return normalized


def _public_inventory_snapshot(session: Session, *, inventory_item_id: int) -> dict[str, Any]:
    row = session.exec(
        select(
            InventoryCopy.id,
            ComicTitle.name,
            Publisher.name,
            ComicIssue.issue_number,
            Variant.cover_name,
            InventoryCopy.grade_status,
            InventoryCopy.release_year,
        )
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.id == inventory_item_id)
    ).first()
    if row is None:
        return {"inventory_item_id": inventory_item_id}
    return normalize_listing_payload(
        {
            "inventory_item_id": int(row[0]),
            "title": str(row[1]),
            "publisher": str(row[2]),
            "issue_number": str(row[3]),
            "cover_name": row[4],
            "grade_status": str(row[5]),
            "release_year": row[6],
        }
    )


def generate_marketplace_payload(
    session: Session,
    *,
    marketplace_type: str,
    draft: MarketplaceListingDraft,
) -> dict[str, Any]:
    marketplace_key = marketplace_type.strip().lower()
    definition = get_marketplace_definition(marketplace_key)
    display_name = definition.display_name if definition is not None else marketplace_key
    inventory = _public_inventory_snapshot(session, inventory_item_id=draft.inventory_item_id)
    price_block = normalize_listing_payload(
        {
            "amount": str(draft.listing_price) if draft.listing_price is not None else None,
            "currency": (draft.listing_currency or "USD").upper(),
        }
    )
    listing_core = normalize_listing_payload(
        {
            "title": draft.listing_title.strip(),
            "description": (draft.listing_description or "").strip(),
            "quantity": draft.listing_quantity,
            "price": price_block,
        }
    )

    if marketplace_key == "ebay":
        shell = {
            "marketplace": "ebay",
            "marketplace_display_name": display_name,
            "listing": listing_core,
            "inventory": inventory,
            "schema_version": "P43-02-ebay-shell-v1",
        }
    elif marketplace_key == "whatnot":
        shell = {
            "marketplace": "whatnot",
            "marketplace_display_name": display_name,
            "show_listing": listing_core,
            "inventory": inventory,
            "schema_version": "P43-02-whatnot-shell-v1",
        }
    elif marketplace_key == "shopify":
        shell = {
            "marketplace": "shopify",
            "marketplace_display_name": display_name,
            "product": {
                "title": listing_core["title"],
                "body_html": listing_core["description"],
                "variants": [
                    normalize_listing_payload(
                        {
                            "price": price_block["amount"],
                            "currency": price_block["currency"],
                            "inventory_quantity": listing_core["quantity"],
                        }
                    )
                ],
            },
            "inventory": inventory,
            "schema_version": "P43-02-shopify-shell-v1",
        }
    else:
        shell = {
            "marketplace": marketplace_key,
            "marketplace_display_name": display_name,
            "listing": listing_core,
            "inventory": inventory,
            "schema_version": "P43-02-generic-shell-v1",
        }
    # Stable serialization round-trip guard
    return json.loads(json.dumps(normalize_listing_payload(shell), sort_keys=True))


def list_listing_projections(
    session: Session,
    *,
    organization_id: int,
    marketplace_listing_draft_id: int,
    limit: int,
    offset: int,
) -> tuple[list[MarketplaceListingProjection], int]:
    base = (
        select(MarketplaceListingProjection)
        .where(MarketplaceListingProjection.organization_id == organization_id)
        .where(MarketplaceListingProjection.marketplace_listing_draft_id == marketplace_listing_draft_id)
    )
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(
            MarketplaceListingProjection.generated_at.desc(),
            MarketplaceListingProjection.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def generate_listing_projection(
    session: Session,
    *,
    organization_id: int,
    draft: MarketplaceListingDraft,
    marketplace_type: str,
) -> MarketplaceListingProjection:
    now = utc_now()
    for row in session.exec(
        select(MarketplaceListingProjection)
        .where(MarketplaceListingProjection.marketplace_listing_draft_id == int(draft.id or 0))
        .where(MarketplaceListingProjection.projection_status == PROJECTION_STATUS_CURRENT)
        .order_by(MarketplaceListingProjection.id.asc())
    ).all():
        row.projection_status = PROJECTION_STATUS_SUPERSEDED
        session.add(row)

    payload = generate_marketplace_payload(session, marketplace_type=marketplace_type, draft=draft)
    projection = MarketplaceListingProjection(
        organization_id=organization_id,
        marketplace_listing_draft_id=int(draft.id or 0),
        marketplace_type=marketplace_type.strip().lower(),
        projection_payload_json=payload,
        projection_status=PROJECTION_STATUS_CURRENT,
        generated_at=now,
    )
    session.add(projection)
    session.flush()
    return projection
