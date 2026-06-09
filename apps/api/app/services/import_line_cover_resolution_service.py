"""Persist and carry P92-07 import line cover resolutions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.p92_import_line_cover import P92ImportLineCoverResolution
from app.schemas.ai import AiDraftOrderItem
from app.services.import_cover_resolver import ImportCoverResolutionResultPayload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_verified_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def upsert_line_cover_resolution_from_item(
    session: Session,
    *,
    owner_user_id: int,
    draft_import_id: int,
    line_index: int,
    item: AiDraftOrderItem,
    cover: ImportCoverResolutionResultPayload | None = None,
) -> None:
    cover_url = item.cover_thumbnail_url or item.cover_image_url
    if cover is not None:
        cover_url = cover.cover_thumbnail_url or cover.cover_image_url or cover_url

    row = session.exec(
        select(P92ImportLineCoverResolution).where(
            P92ImportLineCoverResolution.draft_import_id == draft_import_id,
            P92ImportLineCoverResolution.line_index == line_index,
        )
    ).first()

    payload = {
        "cover_url": cover_url,
        "cover_source": item.cover_source or (cover.cover_source if cover else None),
        "cover_confidence": item.cover_confidence if item.cover_confidence is not None else (cover.cover_confidence if cover else None),
        "variant_confidence": item.variant_confidence
        if item.variant_confidence is not None
        else (cover.variant_confidence if cover else None),
        "source_url": item.cover_source_url or item.retailer_product_url or (cover.cover_source_url if cover else None),
        "source_sku": item.cover_source_sku or item.retailer_sku or (cover.cover_source_sku if cover else None),
        "verified_at": _parse_verified_at(item.cover_verified_at)
        or _parse_verified_at(cover.cover_verified_at if cover else None),
        "verified_by": item.cover_verified_by or (cover.cover_verified_by if cover else None),
        "resolution_json": {
            "cover_image_source": item.cover_image_source or (cover.cover_image_source if cover else None),
            "cover_image_source_id": item.cover_image_source_id or (cover.cover_image_source_id if cover else None),
            "cover_resolution_debug": item.cover_resolution_debug
            or (cover.cover_resolution_debug if cover else None),
        },
        "updated_at": _utc_now(),
    }

    if row is None:
        session.add(
            P92ImportLineCoverResolution(
                owner_user_id=owner_user_id,
                draft_import_id=draft_import_id,
                line_index=line_index,
                **payload,
            )
        )
    else:
        for key, value in payload.items():
            setattr(row, key, value)
        session.add(row)
    session.flush()


def persist_parse_order_line_cover_resolutions(
    session: Session,
    *,
    owner_user_id: int,
    draft_import_id: int,
    items: list[AiDraftOrderItem],
) -> None:
    for line_index, item in enumerate(items):
        upsert_line_cover_resolution_from_item(
            session,
            owner_user_id=owner_user_id,
            draft_import_id=draft_import_id,
            line_index=line_index,
            item=item,
        )


def attach_line_cover_resolutions_to_order(
    session: Session,
    *,
    draft_import_id: int,
    order_id: int,
) -> int:
    """Link each draft line resolution to the first inventory copy for that line."""
    from app.models import InventoryCopy, OrderItem

    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id.asc())
    ).all()
    if not order_items:
        return 0

    linked = 0
    for line_index, order_item in enumerate(order_items):
        if order_item.id is None:
            continue
        inventory_copy = session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.order_item_id == order_item.id)
            .order_by(InventoryCopy.copy_number.asc(), InventoryCopy.id.asc())
        ).first()
        if inventory_copy is None or inventory_copy.id is None:
            continue

        row = session.exec(
            select(P92ImportLineCoverResolution).where(
                P92ImportLineCoverResolution.draft_import_id == draft_import_id,
                P92ImportLineCoverResolution.line_index == line_index,
            )
        ).first()
        if row is None:
            continue
        row.inventory_copy_id = inventory_copy.id
        row.updated_at = _utc_now()
        session.add(row)
        linked += 1

    session.flush()
    return linked


def record_cover_resolution_health_on_confirm(
    session: Session,
    *,
    owner_user_id: int,
    draft_import_id: int,
    linked_count: int,
    item_count: int,
) -> None:
    from app.services.p92_guided_import_service import record_import_health_event

    rows = session.exec(
        select(P92ImportLineCoverResolution).where(
            P92ImportLineCoverResolution.draft_import_id == draft_import_id
        )
    ).all()
    low_confidence = sum(
        1
        for row in rows
        if (row.cover_confidence or 0) < 0.55 or (row.variant_confidence or 0) < 0.55
    )
    record_import_health_event(
        session,
        owner_user_id=owner_user_id,
        event_type="cover_resolution_confirmed",
        draft_import_id=draft_import_id,
        payload={
            "line_count": item_count,
            "linked_inventory_copies": linked_count,
            "low_confidence_line_count": low_confidence,
        },
    )
