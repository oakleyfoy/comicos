from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.p89_listing_draft import P89ListingDraft
from app.schemas.p89_listing_draft import (
    P89ListingDraftCreate,
    P89ListingDraftListRead,
    P89ListingDraftRead,
    P89ListingDraftUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.listing_draft_service import (
    archive_listing_draft,
    draft_display_meta,
    full_listing_text,
    generate_listing_draft,
    get_listing_draft,
    list_listing_drafts,
    mark_listing_draft_reviewed,
    update_listing_draft,
)

p89_listing_draft_router = APIRouter(tags=["Listing Drafts (P89-03)"])


def attach_p89_listing_draft_layer(app: FastAPI) -> None:
    app.include_router(p89_listing_draft_router)


def _to_read(session: Session, row: P89ListingDraft) -> P89ListingDraftRead:
    extra = draft_display_meta(session, row=row)
    return P89ListingDraftRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_copy_id=int(row.inventory_copy_id),
        sell_candidate_id=row.sell_candidate_id,
        market_price_snapshot_id=row.market_price_snapshot_id,
        marketplace=row.marketplace,  # type: ignore[arg-type]
        title=row.title,
        description=row.description,
        condition_notes=row.condition_notes,
        shipping_notes=row.shipping_notes,
        suggested_price=row.suggested_price,
        minimum_price=row.minimum_price,
        premium_price=row.premium_price,
        status=row.status,  # type: ignore[arg-type]
        comic_title=str(extra.get("comic_title") or ""),
        pricing_unavailable=bool(extra.get("pricing_unavailable")),
        full_listing_text=full_listing_text(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@p89_listing_draft_router.post("/api/v1/listing-drafts", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_listing_draft(
    payload: P89ListingDraftCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = generate_listing_draft(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=payload.inventory_copy_id,
        marketplace=payload.marketplace,
        sell_candidate_id=payload.sell_candidate_id,
        market_price_snapshot_id=payload.market_price_snapshot_id,
    )
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_draft_router.get("/api/v1/listing-drafts", response_model=ScanApiV1Envelope)
def v1_list_listing_drafts(
    status: str | None = None,
    marketplace: str | None = None,
    inventory_copy_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_listing_drafts(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        marketplace=marketplace,
        inventory_copy_id=inventory_copy_id,
        limit=limit,
        offset=offset,
    )
    body = P89ListingDraftListRead(
        items=[_to_read(session, r) for r in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p89_listing_draft_router.get("/api/v1/listing-drafts/{draft_id}", response_model=ScanApiV1Envelope)
def v1_get_listing_draft(
    draft_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_listing_draft(session, owner_user_id=int(current_user.id), draft_id=draft_id)
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_draft_router.patch("/api/v1/listing-drafts/{draft_id}", response_model=ScanApiV1Envelope)
def v1_patch_listing_draft(
    draft_id: int,
    payload: P89ListingDraftUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    fields = payload.model_dump(exclude_unset=True)
    row = update_listing_draft(session, owner_user_id=int(current_user.id), draft_id=draft_id, fields=fields)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_draft_router.post("/api/v1/listing-drafts/{draft_id}/mark-reviewed", response_model=ScanApiV1Envelope)
def v1_mark_listing_draft_reviewed(
    draft_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = mark_listing_draft_reviewed(session, owner_user_id=int(current_user.id), draft_id=draft_id)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))
