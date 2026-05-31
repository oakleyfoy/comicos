from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingPrice
from app.schemas.marketplace_listing import MarketplaceListingPriceCreate, MarketplaceListingPriceListResponse, MarketplaceListingPriceRead
from app.services.marketplace_listings import _clamp, _owner_listing_or_404, _normalize_currency


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _price_read(row: MarketplaceListingPrice) -> MarketplaceListingPriceRead:
    return MarketplaceListingPriceRead(
        id=int(row.id or 0),
        listing_id=row.listing_id,
        price_type=row.price_type,
        amount=row.amount,
        currency=row.currency,
        effective_at=row.effective_at,
        created_at=row.created_at,
    )


def set_listing_price(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    payload: MarketplaceListingPriceCreate,
) -> MarketplaceListingPriceRead:
    listing = _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    effective_at = payload.effective_at or utc_now()
    row = MarketplaceListingPrice(
        listing_id=listing_id,
        price_type=payload.price_type.strip().upper(),
        amount=payload.amount,
        currency=_normalize_currency(payload.currency),
        effective_at=effective_at,
        created_at=utc_now(),
    )
    session.add(row)
    listing.asking_price = payload.amount
    listing.currency = row.currency
    listing.updated_at = utc_now()
    session.add(listing)
    session.commit()
    session.refresh(row)
    return _price_read(row)


def get_price_history(session: Session, *, owner_id: int, listing_id: int, limit: int, offset: int) -> MarketplaceListingPriceListResponse:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceListingPrice)
        .where(MarketplaceListingPrice.listing_id == listing_id)
        .order_by(MarketplaceListingPrice.effective_at.desc(), MarketplaceListingPrice.id.desc())
    ).all()
    items = [_price_read(row) for row in rows]
    return MarketplaceListingPriceListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_current_price(session: Session, *, owner_id: int, listing_id: int) -> MarketplaceListingPriceRead | None:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = session.exec(
        select(MarketplaceListingPrice)
        .where(MarketplaceListingPrice.listing_id == listing_id)
        .order_by(MarketplaceListingPrice.effective_at.desc(), MarketplaceListingPrice.id.desc())
    ).first()
    if row is None:
        return None
    return _price_read(row)
