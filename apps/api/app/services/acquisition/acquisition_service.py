"""P98-02/16 Acquisition service: CRUD, completion, validation, analytics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Acquisition, InventoryCopy
from app.models.acquisition import (
    ACQUISITION_STATUS_COMPLETE,
    ACQUISITION_STATUS_OPEN,
    ACQUISITION_STATUSES,
    ACQUISITION_TYPE_UNKNOWN,
    ACQUISITION_TYPES,
    ALLOCATION_MODES,
    utc_now,
)
from app.schemas.acquisition import (
    AcquisitionCreatePayload,
    AcquisitionInventorySummary,
    AcquisitionListItem,
    AcquisitionListResponse,
    AcquisitionRead,
    AcquisitionSourceAnalyticsResponse,
    AcquisitionSourceAnalyticsRow,
    AcquisitionUpdatePayload,
)
from app.services.acquisition.acquisition_cost_allocation_service import (
    allocation_summary,
    quantize_money,
)


def _validate_money(*values: Decimal | None) -> None:
    for value in values:
        if value is not None and value < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amounts cannot be negative")


def _validate_type(acquisition_type: str | None) -> None:
    if acquisition_type is not None and acquisition_type not in ACQUISITION_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid acquisition_type: {acquisition_type}")


def get_acquisition_or_404(session: Session, *, owner_user_id: int, acquisition_id: int) -> Acquisition:
    acquisition = session.get(Acquisition, acquisition_id)
    if acquisition is None or int(acquisition.user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition not found")
    return acquisition


def require_open(acquisition: Acquisition) -> None:
    """OPEN status is required to add/edit items (P98-02)."""
    if acquisition.status != ACQUISITION_STATUS_OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Acquisition is complete. Reopen it before editing items.",
        )


def recompute_actual_book_count(session: Session, acquisition: Acquisition) -> int:
    count = session.exec(
        select(func.count(InventoryCopy.id)).where(InventoryCopy.acquisition_id == acquisition.id)
    ).one()
    count = int(count or 0)
    acquisition.actual_book_count = count
    return count


def build_acquisition_read(session: Session, acquisition: Acquisition) -> AcquisitionRead:
    item_count = recompute_actual_book_count(session, acquisition)
    total_cost = quantize_money(acquisition.total_acquisition_cost)
    cost_per_book = quantize_money(total_cost / item_count) if item_count else Decimal("0.00")
    allocated_total, fully_allocated = allocation_summary(session, acquisition)
    needs_review = int(
        session.exec(
            select(func.count(InventoryCopy.id)).where(
                InventoryCopy.acquisition_id == acquisition.id,
                InventoryCopy.variant_status == "UNKNOWN",
            )
        ).one()
        or 0
    )
    summary = AcquisitionInventorySummary(
        allocated_total=allocated_total,
        acquisition_total=total_cost,
        unallocated=quantize_money(total_cost - allocated_total),
        fully_allocated=fully_allocated,
        needs_review_count=needs_review,
    )
    return AcquisitionRead(
        id=int(acquisition.id or 0),
        user_id=int(acquisition.user_id),
        acquisition_type=acquisition.acquisition_type,
        purchase_date=acquisition.purchase_date,
        seller_name=acquisition.seller_name,
        seller_username=acquisition.seller_username,
        total_paid=quantize_money(acquisition.total_paid),
        shipping_paid=quantize_money(acquisition.shipping_paid),
        tax_paid=quantize_money(acquisition.tax_paid),
        total_cost=total_cost,
        notes=acquisition.notes,
        expected_book_count=acquisition.expected_book_count,
        actual_book_count=acquisition.actual_book_count,
        item_count=item_count,
        cost_per_book=cost_per_book,
        status=acquisition.status,
        allocation_mode=acquisition.allocation_mode,
        created_at=acquisition.created_at,
        updated_at=acquisition.updated_at,
        inventory_summary=summary,
    )


def create_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    payload: AcquisitionCreatePayload,
) -> AcquisitionRead:
    _validate_type(payload.acquisition_type)
    _validate_money(payload.total_paid, payload.shipping_paid, payload.tax_paid)
    acquisition = Acquisition(
        user_id=owner_user_id,
        acquisition_type=payload.acquisition_type,
        purchase_date=payload.purchase_date,
        seller_name=payload.seller_name,
        seller_username=payload.seller_username,
        total_paid=quantize_money(payload.total_paid),
        shipping_paid=quantize_money(payload.shipping_paid),
        tax_paid=quantize_money(payload.tax_paid),
        notes=payload.notes,
        expected_book_count=payload.expected_book_count,
        status=ACQUISITION_STATUS_OPEN,
    )
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)
    return build_acquisition_read(session, acquisition)


def update_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: AcquisitionUpdatePayload,
) -> AcquisitionRead:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    data = payload.model_dump(exclude_unset=True)

    # A COMPLETE acquisition can only be patched to reopen it (status change).
    if acquisition.status == ACQUISITION_STATUS_COMPLETE and set(data.keys()) - {"status"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Acquisition is complete. Reopen it before editing.",
        )

    _validate_type(data.get("acquisition_type"))
    _validate_money(data.get("total_paid"), data.get("shipping_paid"), data.get("tax_paid"))

    if "status" in data and data["status"] not in ACQUISITION_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    if "allocation_mode" in data and data["allocation_mode"] not in ALLOCATION_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid allocation_mode")

    for field_name, value in data.items():
        if field_name in {"total_paid", "shipping_paid", "tax_paid"} and value is not None:
            value = quantize_money(value)
        setattr(acquisition, field_name, value)
    acquisition.updated_at = utc_now()
    session.add(acquisition)

    # Recalculate even allocation when totals change while OPEN.
    if acquisition.status == ACQUISITION_STATUS_OPEN and (
        {"total_paid", "shipping_paid", "tax_paid", "allocation_mode"} & set(data.keys())
    ):
        from app.services.acquisition.acquisition_cost_allocation_service import recalc_if_even

        recalc_if_even(session, acquisition)

    session.commit()
    session.refresh(acquisition)
    return build_acquisition_read(session, acquisition)


def complete_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
) -> AcquisitionRead:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    acquisition.status = ACQUISITION_STATUS_COMPLETE
    acquisition.updated_at = utc_now()
    recompute_actual_book_count(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)
    return build_acquisition_read(session, acquisition)


def get_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
) -> AcquisitionRead:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    return build_acquisition_read(session, acquisition)


def list_acquisitions(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_type: str | None = None,
    status_filter: str | None = None,
    seller: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AcquisitionListResponse:
    stmt = select(Acquisition).where(Acquisition.user_id == owner_user_id)
    if acquisition_type:
        stmt = stmt.where(Acquisition.acquisition_type == acquisition_type)
    if status_filter:
        stmt = stmt.where(Acquisition.status == status_filter)
    if seller:
        stmt = stmt.where(Acquisition.seller_name.ilike(f"%{seller}%"))
    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            Acquisition.seller_name.ilike(term)
            | Acquisition.seller_username.ilike(term)
            | Acquisition.notes.ilike(term)
        )
    if date_from:
        stmt = stmt.where(Acquisition.purchase_date >= date_from)
    if date_to:
        stmt = stmt.where(Acquisition.purchase_date <= date_to)
    stmt = stmt.order_by(Acquisition.created_at.desc(), Acquisition.id.desc())

    rows = list(session.exec(stmt).all())

    # Item counts per acquisition (single grouped query).
    counts: dict[int, int] = {}
    if rows:
        count_rows = session.exec(
            select(InventoryCopy.acquisition_id, func.count(InventoryCopy.id))
            .where(InventoryCopy.acquisition_id.in_([int(r.id) for r in rows]))
            .group_by(InventoryCopy.acquisition_id)
        ).all()
        counts = {int(aid): int(cnt) for aid, cnt in count_rows}

    items: list[AcquisitionListItem] = []
    for acquisition in rows:
        item_count = counts.get(int(acquisition.id or 0), 0)
        total_cost = quantize_money(acquisition.total_acquisition_cost)
        cost_per_book = quantize_money(total_cost / item_count) if item_count else Decimal("0.00")
        items.append(
            AcquisitionListItem(
                id=int(acquisition.id or 0),
                acquisition_type=acquisition.acquisition_type,
                purchase_date=acquisition.purchase_date,
                seller_name=acquisition.seller_name,
                seller_username=acquisition.seller_username,
                total_paid=quantize_money(acquisition.total_paid),
                total_cost=total_cost,
                item_count=item_count,
                cost_per_book=cost_per_book,
                status=acquisition.status,
                created_at=acquisition.created_at,
            )
        )
    return AcquisitionListResponse(items=items, total=len(items))


def backfill_legacy_inventory(session: Session, *, owner_user_id: int) -> Acquisition | None:
    """Attach a user's un-acquisitioned inventory to one Legacy/Unknown acquisition.

    Mirrors the P98-01 migration backfill; reusable for tests and ad-hoc repair.
    Returns the legacy acquisition (or None when the user has no orphan copies).
    """
    from app.models.acquisition import LEGACY_ACQUISITION_SELLER_NAME

    orphan_ids = list(
        session.exec(
            select(InventoryCopy.id).where(
                InventoryCopy.user_id == owner_user_id,
                InventoryCopy.acquisition_id.is_(None),
            )
        ).all()
    )
    if not orphan_ids:
        return None

    legacy = session.exec(
        select(Acquisition).where(
            Acquisition.user_id == owner_user_id,
            Acquisition.seller_name == LEGACY_ACQUISITION_SELLER_NAME,
        )
    ).first()
    if legacy is None:
        legacy = Acquisition(
            user_id=owner_user_id,
            acquisition_type=ACQUISITION_TYPE_UNKNOWN,
            seller_name=LEGACY_ACQUISITION_SELLER_NAME,
            status=ACQUISITION_STATUS_COMPLETE,
        )
        session.add(legacy)
        session.flush()

    for copy in session.exec(select(InventoryCopy).where(InventoryCopy.id.in_(orphan_ids))).all():
        copy.acquisition_id = legacy.id
        session.add(copy)
    recompute_actual_book_count(session, legacy)
    session.add(legacy)
    session.commit()
    session.refresh(legacy)
    return legacy


def allocate_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    mode: str,
    manual: dict[int, Decimal] | None = None,
):
    from app.models.acquisition import ALLOCATION_MODE_EVEN, ALLOCATION_MODE_MANUAL
    from app.schemas.acquisition import AllocateItem, AllocateResponse
    from app.services.acquisition.acquisition_cost_allocation_service import (
        allocation_summary,
        apply_even_allocation,
        apply_manual_allocation,
    )

    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)
    if mode not in (ALLOCATION_MODE_EVEN, ALLOCATION_MODE_MANUAL):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid allocation mode")

    acquisition.allocation_mode = mode
    if mode == ALLOCATION_MODE_EVEN:
        copies = apply_even_allocation(session, acquisition)
    else:
        copies = apply_manual_allocation(session, acquisition, manual or {})
    acquisition.updated_at = utc_now()
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)

    allocated_total, fully_allocated = allocation_summary(session, acquisition)
    items = [
        AllocateItem(inventory_copy_id=int(c.id or 0), cost_basis=quantize_money(c.acquisition_cost))
        for c in copies
    ]
    return AllocateResponse(
        mode=mode,
        allocated_total=allocated_total,
        acquisition_total=quantize_money(acquisition.total_acquisition_cost),
        fully_allocated=fully_allocated,
        items=items,
        acquisition=build_acquisition_read(session, acquisition),
    )


def acquisition_source_analytics(
    session: Session,
    *,
    owner_user_id: int,
) -> AcquisitionSourceAnalyticsResponse:
    """P98-16 spend / books / avg-cost grouped by acquisition source."""
    acquisitions = list(session.exec(select(Acquisition).where(Acquisition.user_id == owner_user_id)).all())
    if not acquisitions:
        return AcquisitionSourceAnalyticsResponse(rows=[], total_spend=Decimal("0.00"), total_books=0)

    count_rows = session.exec(
        select(InventoryCopy.acquisition_id, func.count(InventoryCopy.id))
        .where(InventoryCopy.acquisition_id.in_([int(a.id) for a in acquisitions]))
        .group_by(InventoryCopy.acquisition_id)
    ).all()
    counts = {int(aid): int(cnt) for aid, cnt in count_rows}

    by_type: dict[str, dict[str, Decimal | int]] = {}
    total_spend = Decimal("0.00")
    total_books = 0
    for acquisition in acquisitions:
        bucket = by_type.setdefault(
            acquisition.acquisition_type,
            {"acquisition_count": 0, "total_spend": Decimal("0.00"), "book_count": 0},
        )
        spend = quantize_money(acquisition.total_acquisition_cost)
        books = counts.get(int(acquisition.id or 0), 0)
        bucket["acquisition_count"] = int(bucket["acquisition_count"]) + 1
        bucket["total_spend"] = Decimal(bucket["total_spend"]) + spend
        bucket["book_count"] = int(bucket["book_count"]) + books
        total_spend += spend
        total_books += books

    rows: list[AcquisitionSourceAnalyticsRow] = []
    for acquisition_type, bucket in sorted(by_type.items(), key=lambda kv: kv[0]):
        book_count = int(bucket["book_count"])
        spend = quantize_money(Decimal(bucket["total_spend"]))
        avg = quantize_money(spend / book_count) if book_count else Decimal("0.00")
        rows.append(
            AcquisitionSourceAnalyticsRow(
                acquisition_type=acquisition_type,
                acquisition_count=int(bucket["acquisition_count"]),
                total_spend=spend,
                book_count=book_count,
                avg_cost_per_book=avg,
            )
        )
    return AcquisitionSourceAnalyticsResponse(
        rows=rows,
        total_spend=quantize_money(total_spend),
        total_books=total_books,
    )
