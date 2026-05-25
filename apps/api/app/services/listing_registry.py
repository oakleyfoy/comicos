"""P36 deterministic listing registry (bounded lifecycle mutations; append-only audits)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.models import (
    ComicIssue,
    CoverImage,
    InventoryCopy,
    Listing,
    ListingImage,
    ListingInventoryLink,
    ListingLifecycleEvent,
    ListingPriceHistory,
    ScanSession,
    ScanSessionItem,
)

LISTING_CREATED_EVENT_TYPE = "CREATED"

_ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"READY"}),
    "READY": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"SOLD", "CANCELLED"}),
    "SOLD": frozenset(),
    "CANCELLED": frozenset({"ARCHIVED"}),
    "ARCHIVED": frozenset(),
}


def _utc_now():
    from app.models.listing_registry import utc_now as _utc

    return _utc()


def clamp_list_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def validate_price_couple(*, amount: Decimal | None, currency: str | None) -> None:
    if amount is not None and currency is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asking_price_currency is required when asking_price_amount is set",
        )
    if currency is not None and amount is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asking_price_amount is required when asking_price_currency is set",
        )


def assert_transition_allowed(*, prior: str | None, new: str) -> None:
    if prior is None:
        return
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(prior)
    if allowed is None or new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"illegal listing status transition {prior} -> {new}",
        )


def lifecycle_replay_match(
    session: Session,
    *,
    listing_id: int,
    replay_key: str | None,
) -> ListingLifecycleEvent | None:
    if not replay_key:
        return None
    stmt = select(ListingLifecycleEvent).where(
        ListingLifecycleEvent.listing_id == listing_id,
        ListingLifecycleEvent.replay_key == replay_key,
    )
    return session.exec(stmt).first()


def price_replay_match(
    session: Session,
    *,
    listing_id: int,
    replay_key: str | None,
) -> ListingPriceHistory | None:
    if not replay_key:
        return None
    stmt = select(ListingPriceHistory).where(
        ListingPriceHistory.listing_id == listing_id,
        ListingPriceHistory.replay_key == replay_key,
    )
    return session.exec(stmt).first()


def append_listing_event(
    session: Session,
    *,
    listing_id: int,
    event_type: str,
    prior_status: str | None,
    new_status: str | None,
    created_by_user_id: int | None,
    metadata_json: dict,
    replay_key: str | None,
) -> ListingLifecycleEvent | None:
    """Append-only lifecycle insertion with optional replay suppression."""

    if replay_key:
        dup = lifecycle_replay_match(session, listing_id=listing_id, replay_key=replay_key)
        if dup is not None:
            return dup

    evt = ListingLifecycleEvent(
        listing_id=listing_id,
        event_type=event_type,
        prior_status=prior_status,
        new_status=new_status,
        metadata_json=metadata_json,
        created_by_user_id=created_by_user_id,
        replay_key=replay_key,
    )
    session.add(evt)
    session.flush()
    return evt


def append_price_snapshot(
    session: Session,
    *,
    listing_id: int,
    prior_amount: Decimal | None,
    new_amount: Decimal,
    currency: str,
    reason: str | None,
    replay_key: str | None,
    flush: bool = True,
) -> ListingPriceHistory | None:
    """Returns None when replay matches an existing ledger row."""

    if replay_key:
        dup = price_replay_match(session, listing_id=listing_id, replay_key=replay_key)
        if dup is not None:
            return dup

    row = ListingPriceHistory(
        listing_id=listing_id,
        prior_amount=prior_amount,
        new_amount=new_amount,
        currency=currency,
        reason=reason,
        replay_key=replay_key,
    )
    session.add(row)
    if flush:
        session.flush()
    return row


def inventory_copy_owned(
    session: Session, *, inventory_copy_id: int, owner_user_id: int
) -> InventoryCopy:
    row = session.get(InventoryCopy, inventory_copy_id)
    if row is None or row.user_id != owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="inventory copy not found"
        )
    return row


def canonical_issue_exists(session: Session, comic_issue_id: int | None) -> None:
    if comic_issue_id is None:
        return
    if session.get(ComicIssue, comic_issue_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="canonical comic issue not found",
        )


def cover_owned_for_actor(session: Session, *, cover_image_id: int, owner_user_id: int) -> None:
    img = session.get(CoverImage, cover_image_id)
    if img is None or img.inventory_copy_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cover image not found")
    inv = session.get(InventoryCopy, img.inventory_copy_id)
    if inv is None or inv.user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cover image not owned")


def scan_item_owned(session: Session, *, scan_session_item_id: int, owner_user_id: int) -> None:
    item = session.get(ScanSessionItem, scan_session_item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="scan session item not found"
        )
    sess = session.get(ScanSession, item.scan_session_id)
    if sess is None or int(sess.owner_user_id) != owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="scan session item not accessible"
        )


def get_listing_owner(session: Session, *, listing_id: int, owner_user_id: int) -> Listing:
    row = session.get(Listing, listing_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return row


def create_listing(session: Session, *, owner_user_id: int, payload) -> tuple[Listing, bool]:
    from app.schemas.listing_registry import ListingCreate as ListingCreatePayload

    if not isinstance(payload, ListingCreatePayload):
        payload = ListingCreatePayload.model_validate(payload)

    inventory_copy_owned(
        session, inventory_copy_id=payload.inventory_copy_id, owner_user_id=owner_user_id
    )
    canonical_issue_exists(session, payload.canonical_comic_issue_id)
    validate_price_couple(
        amount=payload.asking_price_amount, currency=payload.asking_price_currency
    )

    if payload.replay_key:
        replay_stmt = select(Listing).where(
            Listing.owner_user_id == owner_user_id,
            Listing.replay_key == payload.replay_key,
        )
        found = session.exec(replay_stmt).first()
        if found is not None:
            session.refresh(found)
            return found, False

    now_ts = _utc_now()
    listing_row = Listing(
        owner_user_id=owner_user_id,
        replay_key=payload.replay_key,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
        inventory_copy_id=payload.inventory_copy_id,
        source_type=str(payload.source_type),
        status="DRAFT",
        title=payload.title,
        description=payload.description,
        condition_summary=payload.condition_summary,
        asking_price_amount=payload.asking_price_amount,
        asking_price_currency=(payload.asking_price_currency or "").upper()
        if payload.asking_price_currency
        else None,
        quantity=payload.quantity,
        created_at=now_ts,
        updated_at=now_ts,
    )
    session.add(listing_row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"duplicate listing replay key ({payload.replay_key})",
        ) from exc

    session.add(
        ListingInventoryLink(
            listing_id=int(listing_row.id),
            inventory_copy_id=payload.inventory_copy_id,
            quantity_allocated=payload.quantity,
        )
    )

    try:
        append_listing_event(
            session,
            listing_id=int(listing_row.id),
            event_type=LISTING_CREATED_EVENT_TYPE,
            prior_status=None,
            new_status="DRAFT",
            created_by_user_id=owner_user_id,
            metadata_json={"inventory_copy_id": payload.inventory_copy_id},
            replay_key=f"{payload.replay_key}:created_event" if payload.replay_key else None,
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="lifecycle replay collision on create",
        ) from exc

    if payload.images:
        seen_orders: set[int] = set()
        for img in sorted(
            payload.images, key=lambda r: (r.display_order, str(r.role), r.cover_image_id or 0)
        ):
            if img.display_order in seen_orders:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="duplicate display_order detected in listing.images",
                )
            seen_orders.add(img.display_order)
            cid = img.cover_image_id
            sid = img.scan_session_item_id
            if (cid is None) == (sid is None):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Exactly one of cover_image_id or scan_session_item_id must be set on "
                        "listing.images"
                    ),
                )
            if cid is not None:
                cover_owned_for_actor(session, cover_image_id=int(cid), owner_user_id=owner_user_id)
                session.add(
                    ListingImage(
                        listing_id=int(listing_row.id),
                        cover_image_id=int(cid),
                        scan_session_item_id=None,
                        display_order=img.display_order,
                        role=str(img.role),
                    )
                )
            else:
                scan_item_owned(session, scan_session_item_id=int(sid), owner_user_id=owner_user_id)
                session.add(
                    ListingImage(
                        listing_id=int(listing_row.id),
                        cover_image_id=None,
                        scan_session_item_id=int(sid),
                        display_order=img.display_order,
                        role=str(img.role),
                    )
                )

    if payload.asking_price_amount is not None and not payload.skip_initial_price_history_row:
        try:
            append_price_snapshot(
                session,
                listing_id=int(listing_row.id),
                prior_amount=None,
                new_amount=payload.asking_price_amount,
                currency=str(payload.asking_price_currency or "").upper(),
                reason="initial",
                replay_key=f"{payload.replay_key}:seed_price_event" if payload.replay_key else None,
                flush=True,
            )
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="price replay collision on create"
            ) from exc

    session.commit()
    session.refresh(listing_row)
    return listing_row, True


@dataclass
class _ListingSnapshot:
    source_type: str
    title: str
    description: str | None
    condition_summary: str | None
    asking_price_amount: Decimal | None
    asking_price_currency: str | None
    quantity: int
    canonical_comic_issue_id: int | None


def _snapshot_public_dict(snap: _ListingSnapshot) -> dict:
    """JSON-serialize snapshots for lifecycle metadata (Decimals as strings)."""
    d = vars(snap).copy()
    if d.get("asking_price_amount") is not None:
        d["asking_price_amount"] = str(d["asking_price_amount"])
    return d


def patch_listing(session: Session, *, listing_id: int, owner_user_id: int, payload) -> Listing:
    from app.schemas.listing_registry import ListingUpdate as ListingUpdatePayload

    if not isinstance(payload, ListingUpdatePayload):
        payload = ListingUpdatePayload.model_validate(payload)

    listing_row = get_listing_owner(session, listing_id=listing_id, owner_user_id=owner_user_id)

    if listing_row.status in {"SOLD", "ARCHIVED", "CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="listing state forbids PATCH (use explicit POST endpoints for recovery paths)",
        )

    prior_status = listing_row.status

    pre = _ListingSnapshot(
        source_type=listing_row.source_type,
        title=listing_row.title,
        description=listing_row.description,
        condition_summary=listing_row.condition_summary,
        asking_price_amount=listing_row.asking_price_amount,
        asking_price_currency=listing_row.asking_price_currency,
        quantity=int(listing_row.quantity),
        canonical_comic_issue_id=listing_row.canonical_comic_issue_id,
    )

    if payload.source_type is not None:
        listing_row.source_type = str(payload.source_type)
    if payload.title is not None:
        listing_row.title = payload.title
    if payload.description is not None:
        listing_row.description = payload.description
    if payload.condition_summary is not None:
        listing_row.condition_summary = payload.condition_summary
    if payload.quantity is not None:
        listing_row.quantity = payload.quantity

    canon_set = getattr(payload, "model_fields_set", set())
    if "canonical_comic_issue_id" in canon_set:
        listing_row.canonical_comic_issue_id = payload.canonical_comic_issue_id

    amt = (
        listing_row.asking_price_amount
        if payload.asking_price_amount is None
        else payload.asking_price_amount
    )
    cur_raw = (
        listing_row.asking_price_currency
        if payload.asking_price_currency is None
        else payload.asking_price_currency
    )

    listing_row.asking_price_amount = amt
    if amt is None:
        listing_row.asking_price_currency = None
    else:
        listing_row.asking_price_currency = (
            cur_raw or listing_row.asking_price_currency or ""
        ).upper()

    validate_price_couple(
        amount=listing_row.asking_price_amount, currency=listing_row.asking_price_currency
    )
    canonical_issue_exists(session, listing_row.canonical_comic_issue_id)

    if (
        pre.asking_price_amount is not None
        and listing_row.asking_price_amount is None
        and listing_row.status != "DRAFT"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="clearing asking price is only allowed while listing is in DRAFT",
        )

    price_changed_body = listing_row.asking_price_amount != pre.asking_price_amount or (
        (listing_row.asking_price_currency or None) != (pre.asking_price_currency or None)
    )

    if payload.status is not None:
        if payload.status == "ACTIVE" or payload.status in {"CANCELLED", "ARCHIVED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="use POST endpoints for READY->ACTIVE / cancel / archive lifecycle moves",
            )
        if listing_row.status == "READY" and payload.status != listing_row.status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="READY listings must activate via POST /listings/{id}/activate",
            )
        if payload.status != prior_status:
            assert_transition_allowed(prior=prior_status, new=payload.status)
            listing_row.status = str(payload.status)
            if listing_row.status == "SOLD":
                listing_row.sold_at = _utc_now()

    if payload.quantity is not None:
        link = session.exec(
            select(ListingInventoryLink).where(
                ListingInventoryLink.listing_id == int(listing_row.id)
            )
        ).first()
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="inventory link missing"
            )
        link.quantity_allocated = int(payload.quantity)

    non_price_dirty = (
        pre.source_type != listing_row.source_type
        or pre.title != listing_row.title
        or pre.description != listing_row.description
        or pre.condition_summary != listing_row.condition_summary
        or pre.quantity != int(listing_row.quantity)
        or pre.canonical_comic_issue_id != listing_row.canonical_comic_issue_id
    )

    status_dirty = prior_status != listing_row.status
    replay = payload.replay_key

    if price_changed_body and listing_row.asking_price_amount is not None:
        try:
            append_price_snapshot(
                session,
                listing_id=int(listing_row.id),
                prior_amount=pre.asking_price_amount,
                new_amount=listing_row.asking_price_amount,
                currency=str(listing_row.asking_price_currency),
                reason="manual_update",
                replay_key=replay,
                flush=False,
            )
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="duplicate price replay_key"
            ) from exc

        append_listing_event(
            session,
            listing_id=int(listing_row.id),
            event_type="PRICE_CHANGED",
            prior_status=listing_row.status,
            new_status=listing_row.status,
            created_by_user_id=owner_user_id,
            metadata_json={
                "prior_amount": str(pre.asking_price_amount)
                if pre.asking_price_amount is not None
                else None,
                "new_amount": str(listing_row.asking_price_amount)
                if listing_row.asking_price_amount is not None
                else None,
                "currency": listing_row.asking_price_currency,
            },
            replay_key=f"{replay}:price_evt" if replay else None,
        )

    if status_dirty and listing_row.status == "SOLD":
        append_listing_event(
            session,
            listing_id=int(listing_row.id),
            event_type="SOLD",
            prior_status=prior_status,
            new_status="SOLD",
            created_by_user_id=owner_user_id,
            metadata_json={
                "sold_at": listing_row.sold_at.isoformat() if listing_row.sold_at else None
            },
            replay_key=f"{replay}:sold_evt" if replay else None,
        )

    emit_general_update = (
        non_price_dirty
        or (status_dirty and prior_status == "DRAFT" and listing_row.status == "READY")
        or (
            price_changed_body
            and listing_row.asking_price_amount is None
            and listing_row.status == "DRAFT"
            and prior_status == "DRAFT"
        )
    )
    if emit_general_update:
        meta: dict = {
            "before": _snapshot_public_dict(pre),
            "after_source_type": listing_row.source_type,
            "after_quantity": listing_row.quantity,
            "after_title": listing_row.title[:120],
        }
        if status_dirty and prior_status == "DRAFT" and listing_row.status == "READY":
            meta["status_transition"] = ["DRAFT", "READY"]
        if price_changed_body and listing_row.asking_price_amount is None:
            meta["price_cleared"] = True
            meta["prior_amount"] = (
                str(pre.asking_price_amount) if pre.asking_price_amount is not None else None
            )

        append_listing_event(
            session,
            listing_id=int(listing_row.id),
            event_type="UPDATED",
            prior_status=listing_row.status,
            new_status=listing_row.status,
            created_by_user_id=owner_user_id,
            metadata_json=meta,
            replay_key=f"{replay}:updated_evt" if replay else None,
        )

    listing_row.updated_at = _utc_now()

    try:
        session.commit()
        session.refresh(listing_row)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="lifecycle integrity failure"
        ) from exc

    return listing_row


def _activate_transition(
    session: Session, listing: Listing, owner_user_id: int, replay_key: str | None
) -> Listing:
    if listing.status != "READY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"activation requires READY state (currently {listing.status})",
        )
    assert_transition_allowed(prior="READY", new="ACTIVE")
    listing.status = "ACTIVE"
    listing.updated_at = _utc_now()
    listing.activated_at = _utc_now()
    lifecycle_replay = f"{replay_key}:activated" if replay_key else None
    append_listing_event(
        session,
        listing_id=int(listing.id),
        event_type="ACTIVATED",
        prior_status="READY",
        new_status="ACTIVE",
        created_by_user_id=owner_user_id,
        metadata_json={"activated_at": listing.activated_at.isoformat()},
        replay_key=lifecycle_replay,
    )
    try:
        session.commit()
        session.refresh(listing)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="duplicate activation replay_key"
        ) from exc
    return listing


def activate_listing(
    session: Session, *, listing_id: int, owner_user_id: int, replay_key: str | None = None
) -> Listing:
    row = get_listing_owner(session, listing_id=listing_id, owner_user_id=owner_user_id)
    if row.status == "ACTIVE":
        return row
    return _activate_transition(session, row, owner_user_id, replay_key)


def cancel_listing(
    session: Session, *, listing_id: int, owner_user_id: int, replay_key: str | None = None
) -> Listing:
    row = get_listing_owner(session, listing_id=listing_id, owner_user_id=owner_user_id)
    rk = f"{replay_key}:cancelled" if replay_key else None
    if row.status == "CANCELLED":
        return row
    if row.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="cancellation requires ACTIVE state"
        )
    assert_transition_allowed(prior="ACTIVE", new="CANCELLED")
    row.status = "CANCELLED"
    row.updated_at = _utc_now()
    append_listing_event(
        session,
        listing_id=int(row.id),
        event_type="CANCELLED",
        prior_status="ACTIVE",
        new_status="CANCELLED",
        created_by_user_id=owner_user_id,
        metadata_json={},
        replay_key=rk,
    )
    try:
        session.commit()
        session.refresh(row)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="duplicate cancellation replay_key"
        ) from exc
    return row


def archive_listing(
    session: Session, *, listing_id: int, owner_user_id: int, replay_key: str | None = None
) -> Listing:
    row = get_listing_owner(session, listing_id=listing_id, owner_user_id=owner_user_id)
    rk = f"{replay_key}:archived" if replay_key else None
    if row.status == "ARCHIVED":
        return row
    if row.status != "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="archive requires CANCELLED state"
        )
    assert_transition_allowed(prior="CANCELLED", new="ARCHIVED")
    row.status = "ARCHIVED"
    row.archived_at = _utc_now()
    row.updated_at = _utc_now()
    append_listing_event(
        session,
        listing_id=int(row.id),
        event_type="ARCHIVED",
        prior_status="CANCELLED",
        new_status="ARCHIVED",
        created_by_user_id=owner_user_id,
        metadata_json={"archived_at": row.archived_at.isoformat()},
        replay_key=rk,
    )
    try:
        session.commit()
        session.refresh(row)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="duplicate archive replay_key"
        ) from exc
    return row


def list_listings_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
    status: str | None,
    inventory_copy_id: int | None,
):
    cq = select(func.count(Listing.id)).where(Listing.owner_user_id == owner_user_id)
    lq = select(Listing).where(Listing.owner_user_id == owner_user_id)
    if status:
        cq = cq.where(Listing.status == status)
        lq = lq.where(Listing.status == status)
    if inventory_copy_id is not None:
        cq = cq.where(Listing.inventory_copy_id == inventory_copy_id)
        lq = lq.where(Listing.inventory_copy_id == inventory_copy_id)

    total = int(session.exec(cq).one())
    lq = lq.order_by(Listing.updated_at.desc(), Listing.id.desc()).offset(offset).limit(limit)
    items = session.exec(lq).all()
    return items, total


def owner_dashboard_summary(session: Session, *, owner_user_id: int, recent_limit: int = 25):
    def _cnt(target_status: str) -> int:
        q = select(func.count(Listing.id)).where(
            Listing.owner_user_id == owner_user_id,
            Listing.status == target_status,
        )
        return int(session.exec(q).one())

    drafts = _cnt("DRAFT") + _cnt("READY")
    active = _cnt("ACTIVE")
    sold = _cnt("SOLD")

    stmt2 = (
        select(ListingLifecycleEvent)
        .where(
            ListingLifecycleEvent.listing_id.in_(
                select(Listing.id).where(Listing.owner_user_id == owner_user_id),
            ),
        )
        .order_by(ListingLifecycleEvent.created_at.desc(), ListingLifecycleEvent.id.desc())
        .limit(recent_limit)
    )
    tail = session.exec(stmt2).all()
    recent = list(tail)
    return drafts, active, sold, recent


def list_listing_images(session: Session, listing_id: int) -> list[ListingImage]:
    stmt = (
        select(ListingImage)
        .where(ListingImage.listing_id == listing_id)
        .order_by(ListingImage.display_order.asc(), ListingImage.id.asc())
    )
    return list(session.exec(stmt).all())


def lifecycle_tail(
    session: Session, listing_id: int, limit: int = 50
) -> list[ListingLifecycleEvent]:
    stmt = (
        select(ListingLifecycleEvent)
        .where(ListingLifecycleEvent.listing_id == listing_id)
        .order_by(ListingLifecycleEvent.created_at.desc(), ListingLifecycleEvent.id.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def price_tail(session: Session, listing_id: int, limit: int = 50) -> list[ListingPriceHistory]:
    stmt = (
        select(ListingPriceHistory)
        .where(ListingPriceHistory.listing_id == listing_id)
        .order_by(ListingPriceHistory.created_at.desc(), ListingPriceHistory.id.desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def list_listings_ops(
    session: Session,
    *,
    limit: int,
    offset: int,
    owner_user_id: int | None,
    status_filter: str | None,
):
    cq = select(func.count(Listing.id))
    lq = select(Listing)
    if owner_user_id is not None:
        cq = cq.where(Listing.owner_user_id == owner_user_id)
        lq = lq.where(Listing.owner_user_id == owner_user_id)
    if status_filter:
        cq = cq.where(Listing.status == status_filter)
        lq = lq.where(Listing.status == status_filter)

    cnt = int(session.exec(cq).one())
    rows = session.exec(
        lq.order_by(Listing.updated_at.desc(), Listing.id.desc()).offset(offset).limit(limit)
    ).all()
    return rows, cnt


def list_events_ops(
    session: Session,
    *,
    limit: int,
    offset: int,
    listing_id: int | None,
    owner_user_id_filter: int | None,
):
    cq = select(func.count(ListingLifecycleEvent.id)).join(
        Listing, ListingLifecycleEvent.listing_id == Listing.id
    )
    lq = select(ListingLifecycleEvent).join(Listing, ListingLifecycleEvent.listing_id == Listing.id)
    if listing_id is not None:
        cq = cq.where(ListingLifecycleEvent.listing_id == listing_id)
        lq = lq.where(ListingLifecycleEvent.listing_id == listing_id)
    if owner_user_id_filter is not None:
        cq = cq.where(Listing.owner_user_id == owner_user_id_filter)
        lq = lq.where(Listing.owner_user_id == owner_user_id_filter)

    counted = int(session.exec(cq).one())
    items = session.exec(
        lq.order_by(ListingLifecycleEvent.created_at.desc(), ListingLifecycleEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), counted


def list_price_hist_ops(
    session: Session,
    *,
    limit: int,
    offset: int,
    listing_id: int | None,
    owner_user_id_filter: int | None,
):
    cq = select(func.count(ListingPriceHistory.id)).join(
        Listing, ListingPriceHistory.listing_id == Listing.id
    )
    lq = select(ListingPriceHistory).join(Listing, ListingPriceHistory.listing_id == Listing.id)
    if listing_id is not None:
        cq = cq.where(ListingPriceHistory.listing_id == listing_id)
        lq = lq.where(ListingPriceHistory.listing_id == listing_id)
    if owner_user_id_filter is not None:
        cq = cq.where(Listing.owner_user_id == owner_user_id_filter)
        lq = lq.where(Listing.owner_user_id == owner_user_id_filter)

    counted = int(session.exec(cq).one())
    items = session.exec(
        lq.order_by(ListingPriceHistory.created_at.desc(), ListingPriceHistory.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), counted


def ops_status_distribution(session: Session) -> list[tuple[str, int]]:
    stmt = (
        select(Listing.status, func.count(Listing.id))
        .group_by(Listing.status)
        .order_by(Listing.status.asc())
    )
    tuples: list[tuple[str, int]] = []
    for status_name, total in session.exec(stmt).all():
        tuples.append((str(status_name), int(total)))
    return tuples


def coerce_listing_read(row: Listing):
    """ORM -> API read model (explicit import keeps SQLModel layering clean)."""

    from app.schemas.listing_registry import ListingRead as ListingReadPayload

    return ListingReadPayload.model_validate(row, from_attributes=True)


def coerce_lifecycle_read(row: ListingLifecycleEvent):
    from app.schemas.listing_registry import ListingLifecycleEventRead as Payload

    return Payload.model_validate(row, from_attributes=True)


def coerce_price_history_read(row: ListingPriceHistory):
    from app.schemas.listing_registry import ListingPriceHistoryRead as Payload

    return Payload.model_validate(row, from_attributes=True)


def coerce_listing_image_read(row: ListingImage):
    from app.schemas.listing_registry import ListingImageRead as Payload

    return Payload.model_validate(row, from_attributes=True)


def assemble_listing_detail(session: Session, listing: Listing):
    from app.schemas.listing_registry import ListingDetailRead as DetailPayload

    imgs = [coerce_listing_image_read(img) for img in list_listing_images(session, int(listing.id))]
    events = [coerce_lifecycle_read(evt) for evt in lifecycle_tail(session, int(listing.id))]
    prices = [coerce_price_history_read(row) for row in price_tail(session, int(listing.id))]
    return DetailPayload(
        listing=coerce_listing_read(listing),
        lifecycle_events_tail=events,
        price_history_tail=prices,
        images=imgs,
    )


def get_listing_ops(session: Session, *, listing_id: int) -> Listing:
    row = session.get(Listing, listing_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return row
