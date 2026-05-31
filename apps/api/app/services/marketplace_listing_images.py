from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace_listing import MarketplaceListingImage
from app.schemas.marketplace_listing import MarketplaceListingImageCreate, MarketplaceListingImageListResponse, MarketplaceListingImageRead
from app.services.marketplace_listings import _clamp, _owner_listing_or_404


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _image_read(row: MarketplaceListingImage) -> MarketplaceListingImageRead:
    return MarketplaceListingImageRead(
        id=int(row.id or 0),
        listing_id=row.listing_id,
        image_url=row.image_url,
        image_type=row.image_type,
        sort_order=row.sort_order,
        is_primary=row.is_primary,
        created_at=row.created_at,
    )


def _listing_image_rows(session: Session, *, listing_id: int) -> list[MarketplaceListingImage]:
    return session.exec(
        select(MarketplaceListingImage)
        .where(MarketplaceListingImage.listing_id == listing_id)
        .order_by(
            MarketplaceListingImage.is_primary.desc(),
            MarketplaceListingImage.sort_order.asc(),
            MarketplaceListingImage.id.asc(),
        )
    ).all()


def _listing_image_or_404(session: Session, *, listing_id: int, image_id: int) -> MarketplaceListingImage:
    row = session.get(MarketplaceListingImage, image_id)
    if row is None or row.listing_id != listing_id:
        raise HTTPException(status_code=404, detail="Marketplace listing image not found.")
    return row


def _ensure_single_primary(session: Session, *, listing_id: int, image_id: int) -> None:
    rows = _listing_image_rows(session, listing_id=listing_id)
    for row in rows:
        row.is_primary = row.id == image_id
        session.add(row)


def add_listing_image(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    payload: MarketplaceListingImageCreate,
) -> MarketplaceListingImageRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    rows = _listing_image_rows(session, listing_id=listing_id)
    row = MarketplaceListingImage(
        listing_id=listing_id,
        image_url=payload.image_url.strip(),
        image_type=payload.image_type.strip(),
        sort_order=payload.sort_order,
        is_primary=payload.is_primary or not rows,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    if row.is_primary:
        _ensure_single_primary(session, listing_id=listing_id, image_id=int(row.id or 0))
    session.commit()
    session.refresh(row)
    return _image_read(row)


def set_primary_image(session: Session, *, owner_id: int, listing_id: int, image_id: int) -> MarketplaceListingImageRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = _listing_image_or_404(session, listing_id=listing_id, image_id=image_id)
    _ensure_single_primary(session, listing_id=listing_id, image_id=image_id)
    session.commit()
    session.refresh(row)
    return _image_read(row)


def remove_listing_image(session: Session, *, owner_id: int, listing_id: int, image_id: int) -> None:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = _listing_image_or_404(session, listing_id=listing_id, image_id=image_id)
    was_primary = row.is_primary
    session.delete(row)
    session.flush()
    if was_primary:
        remaining = _listing_image_rows(session, listing_id=listing_id)
        if remaining:
            replacement = remaining[0]
            replacement.is_primary = True
            session.add(replacement)
            _ensure_single_primary(session, listing_id=listing_id, image_id=int(replacement.id or 0))
    session.commit()


def list_listing_images(session: Session, *, owner_id: int, listing_id: int, limit: int, offset: int) -> MarketplaceListingImageListResponse:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    limit, offset = _clamp(limit, offset)
    rows = _listing_image_rows(session, listing_id=listing_id)
    items = [_image_read(row) for row in rows]
    return MarketplaceListingImageListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )
