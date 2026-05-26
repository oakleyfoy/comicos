"""P38-01 deterministic portfolio registry, exposure, and allocation engines."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    ComicTitle,
    ConventionEvent,
    ConventionInventoryAssignment,
    GradingCandidate,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    Order,
    OrderItem,
    Portfolio,
    PortfolioAllocationSnapshot,
    PortfolioExposureEvidence,
    PortfolioExposureSnapshot,
    PortfolioItem,
    PortfolioLifecycleEvent,
    Publisher,
    SaleRecord,
    SaleRecordLineItem,
    Variant,
)
from app.schemas.portfolio import (
    InventoryPortfolioIntelligenceTeaser,
    PortfolioAllocationGenerateResponse,
    PortfolioAllocationSnapshotListResponse,
    PortfolioAllocationSnapshotRead,
    PortfolioCreatePayload,
    PortfolioExposureEvidenceListResponse,
    PortfolioExposureEvidenceRead,
    PortfolioExposureGenerateResponse,
    PortfolioExposureSnapshotListResponse,
    PortfolioExposureSnapshotRead,
    PortfolioGenerateScopePayload,
    PortfolioIntelligenceExposureTeaser,
    PortfolioIntelligenceSummary,
    PortfolioItemCreatePayload,
    PortfolioItemListResponse,
    PortfolioItemRead,
    PortfolioListResponse,
    PortfolioMembershipRead,
    PortfolioRead,
    PortfolioUpdatePayload,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
ZERO = Decimal("0.00")

PIPELINE_STATUSES = frozenset({"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"})

SCOPE_ALL_INVENTORY = "ALL_INVENTORY"

# Deterministic exposure classification thresholds (percentage points 0–100 of portfolio basis).
TH_BALANCED_MAX = Decimal("15")
TH_WATCH_MAX = Decimal("25")
TH_CONCENTRATED_MAX = Decimal("40")

PORTFOLIO_TYPES = frozenset(
    {
        "personal_collection",
        "dealer_inventory",
        "investment_portfolio",
        "grading_pipeline",
        "convention_inventory",
        "watchlist",
    }
)


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _slug(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "unknown"
    lowered = str(value).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return (cleaned or "unknown")[:256]


def _scope_key(*, portfolio_id: int | None) -> str:
    return SCOPE_ALL_INVENTORY if portfolio_id is None else f"PORTFOLIO_{int(portfolio_id)}"


def _era_bucket(year: int | None) -> str:
    if year is None:
        return "unknown"
    if year < 1980:
        return "pre_1980"
    if year < 2000:
        return "1980_1999"
    if year < 2020:
        return "2000_2019"
    return "2020_plus"


def _value_band(fmv: Decimal | None) -> str:
    if fmv is None:
        return "unknown"
    q = _money(fmv)
    if q < Decimal("25"):
        return "under_25"
    if q < Decimal("100"):
        return "25_to_100"
    if q < Decimal("500"):
        return "100_to_500"
    return "500_plus"


def _classify_exposure(
    *,
    pct_value: Decimal | None,
    pct_count: Decimal | None,
    total_fmv: Decimal,
    total_items: int,
) -> str:
    """Classify a single exposure bucket using value % when FMV basis exists, else count %."""
    if total_items <= 0:
        return "INSUFFICIENT_DATA"
    if total_fmv > ZERO and pct_value is not None:
        basis = pct_value
        has_basis = True
    elif pct_count is not None:
        basis = pct_count
        has_basis = True
    else:
        has_basis = False
    if not has_basis or basis is None:
        return "INSUFFICIENT_DATA"
    if basis < TH_BALANCED_MAX:
        return "BALANCED"
    if basis < TH_WATCH_MAX:
        return "WATCH"
    if basis < TH_CONCENTRATED_MAX:
        return "CONCENTRATED"
    return "OVEREXPOSED"


def _emit_lifecycle_event(
    session: Session,
    *,
    portfolio_id: int,
    created_by_user_id: int,
    event_type: str,
    metadata_json: dict[str, Any] | None,
) -> None:
    session.add(
        PortfolioLifecycleEvent(
            portfolio_id=portfolio_id,
            event_type=event_type,
            metadata_json=metadata_json,
            created_by_user_id=created_by_user_id,
        )
    )


def _portfolio_for_owner(session: Session, *, owner_user_id: int, portfolio_id: int) -> Portfolio:
    row = session.get(Portfolio, portfolio_id)
    if row is None or int(row.owner_user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio not found")
    return row


def _require_active_portfolio(row: Portfolio) -> None:
    if str(row.status).upper() != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="portfolio is not active")


@dataclass
class _CopyFact:
    inventory_item_id: int
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    grade_status: str
    hold_status: str
    release_year: int | None
    publisher_key: str
    title_key: str
    acquisition_source_key: str
    liquidity_status: str | None


def _rows_for_owner_scope(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None,
) -> tuple[list[_CopyFact], dict[int, list[Listing]], dict[int, Decimal], set[int], set[int], set[int]]:
    stmt = (
        select(InventoryCopy, Order, Publisher.name, ComicTitle.name, ComicIssue.issue_number)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == owner_user_id)
    )
    if portfolio_id is not None:
        stmt = stmt.join(
            PortfolioItem,
            and_(
                PortfolioItem.inventory_item_id == InventoryCopy.id,
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.removed_at.is_(None),
            ),
        )
    stmt = stmt.order_by(col(InventoryCopy.id).asc())

    hydrated: list[_CopyFact] = []
    id_list: list[int] = []

    for inv, ord_row, publisher_name, comic_title_name, issue_number in session.exec(stmt).all():
        iid = int(inv.id or 0)
        if not iid:
            continue
        id_list.append(iid)
        src = ord_row.source_type or "unknown"
        acq_src = _slug(f"{src}:{ord_row.retailer}")
        ry = inv.release_year
        if ry is None and inv.release_date is not None:
            ry = inv.release_date.year
        hydrated.append(
            _CopyFact(
                inventory_item_id=iid,
                acquisition_cost=_money(inv.acquisition_cost),
                current_fmv=_money(inv.current_fmv) if inv.current_fmv is not None else None,
                grade_status=str(inv.grade_status or "unknown").lower(),
                hold_status=str(inv.hold_status or "unknown").lower(),
                release_year=ry,
                publisher_key=_slug(publisher_name),
                title_key=_slug(f"{comic_title_name}::{issue_number}"),
                acquisition_source_key=acq_src,
                liquidity_status=None,
            )
        )

    liquidity_map: dict[int, str | None] = {}
    if id_list:
        liq_rows = session.exec(
            select(InventoryLiquiditySnapshot)
            .where(
                InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
                col(InventoryLiquiditySnapshot.inventory_item_id).in_(id_list),
                col(InventoryLiquiditySnapshot.inventory_item_id).is_not(None),
            )
            .order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc(), col(InventoryLiquiditySnapshot.id).desc())
        ).all()
        for row in liq_rows:
            iid = int(row.inventory_item_id or 0)
            if iid and iid not in liquidity_map:
                liquidity_map[iid] = str(row.liquidity_status)

    listings_by_item: dict[int, list[Listing]] = {}
    if id_list:
        listing_rows = session.exec(
            select(Listing).where(
                Listing.owner_user_id == owner_user_id,
                col(Listing.inventory_copy_id).in_(id_list),
                Listing.archived_at.is_(None),
            )
        ).all()
        for lst in listing_rows:
            iid = int(lst.inventory_copy_id)
            listings_by_item.setdefault(iid, []).append(lst)

    sale_totals: dict[int, Decimal] = {}
    if id_list:
        sale_lines = session.exec(
            select(SaleRecordLineItem, SaleRecord)
            .join(SaleRecord, SaleRecordLineItem.sale_record_id == SaleRecord.id)
            .where(
                SaleRecord.owner_user_id == owner_user_id,
                SaleRecord.status == "RECORDED",
                col(SaleRecordLineItem.inventory_item_id).in_(id_list),
            )
        ).all()
        for line, _sale in sale_lines:
            iid = int(line.inventory_item_id or 0)
            if not iid:
                continue
            sale_totals[iid] = sale_totals.get(iid, ZERO) + _money(line.line_subtotal_amount)

    grading_ids: set[int] = set()
    if id_list:
        cand_rows = session.exec(
            select(GradingCandidate).where(
                GradingCandidate.owner_user_id == owner_user_id,
                col(GradingCandidate.inventory_item_id).in_(id_list),
                col(GradingCandidate.status).in_(PIPELINE_STATUSES),
            )
        ).all()
        grading_ids = {int(r.inventory_item_id) for r in cand_rows if r.inventory_item_id}

    convention_ids: set[int] = set()
    if id_list:
        assign_rows = session.exec(
            select(ConventionInventoryAssignment)
            .join(ConventionEvent, ConventionInventoryAssignment.convention_event_id == ConventionEvent.id)
            .where(
                ConventionEvent.owner_user_id == owner_user_id,
                col(ConventionInventoryAssignment.inventory_item_id).in_(id_list),
                ConventionInventoryAssignment.removed_at.is_(None),
            )
        ).all()
        convention_ids = {int(r.inventory_item_id) for r in assign_rows if r.inventory_item_id}

    duplicate_ids: set[int] = set()
    dup_stmt = (
        select(PortfolioItem.inventory_item_id)
        .join(Portfolio, PortfolioItem.portfolio_id == Portfolio.id)
        .where(
            Portfolio.owner_user_id == owner_user_id,
            PortfolioItem.removed_at.is_(None),
            PortfolioItem.allocation_role == "duplicate",
            col(PortfolioItem.inventory_item_id).in_(id_list),
        )
    )
    if portfolio_id is not None:
        dup_stmt = dup_stmt.where(PortfolioItem.portfolio_id == portfolio_id)
    duplicate_ids = {int(r[0]) for r in session.exec(dup_stmt).all()}

    for fact in hydrated:
        fact.liquidity_status = liquidity_map.get(fact.inventory_item_id)

    return hydrated, listings_by_item, sale_totals, grading_ids, convention_ids, duplicate_ids


def _aggregate_exposure_buckets(facts: list[_CopyFact]) -> dict[tuple[str, str], list[int]]:
    buckets: dict[tuple[str, str], list[int]] = {}
    for fact in facts:
        pairs: Iterable[tuple[str, str]] = (
            ("publisher", fact.publisher_key),
            ("title", fact.title_key),
            ("character", "unknown"),
            ("creator", "unknown"),
            ("era", _era_bucket(fact.release_year)),
            ("grade_status", fact.grade_status or "unknown"),
            ("liquidity_status", fact.liquidity_status or "unknown"),
            ("value_band", _value_band(fact.current_fmv)),
            ("acquisition_source", fact.acquisition_source_key),
        )
        for etype, ekey in pairs:
            buckets.setdefault((etype, ekey), []).append(fact.inventory_item_id)
    for key in buckets:
        buckets[key] = sorted(set(buckets[key]))
    return buckets


def serialize_portfolio(row: Portfolio) -> PortfolioRead:
    return PortfolioRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        name=row.name,
        description=row.description,
        portfolio_type=row.portfolio_type,
        status=row.status,
        replay_key=row.replay_key,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )


def create_portfolio(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioCreatePayload,
) -> tuple[PortfolioRead, bool]:
    if payload.portfolio_type not in PORTFOLIO_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid portfolio_type")

    if payload.replay_key:
        existing = session.exec(
            select(Portfolio).where(
                Portfolio.owner_user_id == owner_user_id,
                Portfolio.replay_key == payload.replay_key,
            )
        ).first()
        if existing:
            return serialize_portfolio(existing), True

    row = Portfolio(
        owner_user_id=owner_user_id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        portfolio_type=payload.portfolio_type,
        status="ACTIVE",
        replay_key=payload.replay_key,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(Portfolio).where(
                Portfolio.owner_user_id == owner_user_id,
                Portfolio.replay_key == payload.replay_key,
            )
        ).first()
        if existing:
            return serialize_portfolio(existing), True
        raise
    session.refresh(row)
    assert row.id is not None
    _emit_lifecycle_event(
        session,
        portfolio_id=int(row.id),
        created_by_user_id=owner_user_id,
        event_type="CREATED",
        metadata_json={"name": row.name, "portfolio_type": row.portfolio_type},
    )
    session.commit()
    session.refresh(row)
    return serialize_portfolio(row), False


def list_portfolios_owner(
    session: Session,
    *,
    owner_user_id: int,
    status_filter: str | None,
    limit: int,
    offset: int,
) -> PortfolioListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(Portfolio).where(Portfolio.owner_user_id == owner_user_id)
    if status_filter:
        stmt = stmt.where(Portfolio.status == status_filter.upper())
    stmt = stmt.order_by(col(Portfolio.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    count_stmt = select(func.count()).select_from(Portfolio).where(Portfolio.owner_user_id == owner_user_id)
    if status_filter:
        count_stmt = count_stmt.where(Portfolio.status == status_filter.upper())
    total = int(session.exec(count_stmt).one())
    return PortfolioListResponse(items=[serialize_portfolio(r) for r in rows], total_items=total, limit=lim, offset=off)


def list_portfolios_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    status_filter: str | None,
    limit: int,
    offset: int,
) -> PortfolioListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(Portfolio)
    if owner_user_id is not None:
        stmt = stmt.where(Portfolio.owner_user_id == owner_user_id)
    if status_filter:
        stmt = stmt.where(Portfolio.status == status_filter.upper())
    stmt = stmt.order_by(col(Portfolio.owner_user_id).asc(), col(Portfolio.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    count_stmt = select(func.count()).select_from(Portfolio)
    if owner_user_id is not None:
        count_stmt = count_stmt.where(Portfolio.owner_user_id == owner_user_id)
    if status_filter:
        count_stmt = count_stmt.where(Portfolio.status == status_filter.upper())
    total = int(session.exec(count_stmt).one())
    return PortfolioListResponse(items=[serialize_portfolio(r) for r in rows], total_items=total, limit=lim, offset=off)


def get_portfolio_owner(session: Session, *, owner_user_id: int, portfolio_id: int) -> PortfolioRead:
    row = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    return serialize_portfolio(row)


def update_portfolio_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int,
    payload: PortfolioUpdatePayload,
) -> PortfolioRead:
    row = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    _require_active_portfolio(row)
    dirty = False
    if payload.name is not None:
        row.name = payload.name.strip()
        dirty = True
    if payload.description is not None:
        row.description = payload.description.strip() or None
        dirty = True
    if payload.portfolio_type is not None:
        if payload.portfolio_type not in PORTFOLIO_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid portfolio_type")
        row.portfolio_type = payload.portfolio_type
        dirty = True
    if dirty:
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        _emit_lifecycle_event(
            session,
            portfolio_id=int(row.id),
            created_by_user_id=owner_user_id,
            event_type="UPDATED",
            metadata_json=payload.model_dump(exclude_none=True),
        )
        session.commit()
        session.refresh(row)
    return serialize_portfolio(row)


def archive_portfolio_owner(session: Session, *, owner_user_id: int, portfolio_id: int) -> PortfolioRead:
    row = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    _require_active_portfolio(row)
    row.status = "ARCHIVED"
    row.archived_at = datetime.now(timezone.utc)
    row.updated_at = row.archived_at
    session.add(row)
    _emit_lifecycle_event(
        session,
        portfolio_id=int(row.id),
        created_by_user_id=owner_user_id,
        event_type="ARCHIVED",
        metadata_json=None,
    )
    session.commit()
    session.refresh(row)
    return serialize_portfolio(row)


def _inventory_owned(session: Session, *, owner_user_id: int, inventory_item_id: int) -> InventoryCopy:
    row = session.get(InventoryCopy, inventory_item_id)
    if row is None or int(row.user_id or 0) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory copy not found")
    return row


def serialize_portfolio_item(row: PortfolioItem) -> PortfolioItemRead:
    return PortfolioItemRead(
        id=int(row.id or 0),
        portfolio_id=int(row.portfolio_id),
        inventory_item_id=int(row.inventory_item_id),
        allocation_role=row.allocation_role,
        allocated_value_amount=row.allocated_value_amount,
        allocated_value_source=row.allocated_value_source,
        added_at=row.added_at,
        removed_at=row.removed_at,
        created_at=row.created_at,
    )


def add_portfolio_item(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int,
    payload: PortfolioItemCreatePayload,
) -> PortfolioItemRead:
    pf = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    _require_active_portfolio(pf)
    _inventory_owned(session, owner_user_id=owner_user_id, inventory_item_id=payload.inventory_item_id)
    dup = session.exec(
        select(PortfolioItem).where(
            PortfolioItem.portfolio_id == portfolio_id,
            PortfolioItem.inventory_item_id == payload.inventory_item_id,
            PortfolioItem.removed_at.is_(None),
        )
    ).first()
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="inventory item already active in portfolio")
    if payload.allocated_value_amount is not None and payload.allocated_value_source is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="allocated_value_source required when allocated_value_amount is set",
        )
    row = PortfolioItem(
        portfolio_id=portfolio_id,
        inventory_item_id=payload.inventory_item_id,
        allocation_role=payload.allocation_role,
        allocated_value_amount=payload.allocated_value_amount,
        allocated_value_source=payload.allocated_value_source,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    _emit_lifecycle_event(
        session,
        portfolio_id=portfolio_id,
        created_by_user_id=owner_user_id,
        event_type="ITEM_ADDED",
        metadata_json={"inventory_item_id": payload.inventory_item_id, "allocation_role": payload.allocation_role},
    )
    session.commit()
    return serialize_portfolio_item(row)


def remove_portfolio_item(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int,
    portfolio_item_id: int,
) -> PortfolioItemRead:
    pf = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    row = session.get(PortfolioItem, portfolio_item_id)
    if row is None or int(row.portfolio_id) != int(portfolio_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio item not found")
    if row.removed_at is not None:
        return serialize_portfolio_item(row)
    row.removed_at = datetime.now(timezone.utc)
    session.add(row)
    _emit_lifecycle_event(
        session,
        portfolio_id=portfolio_id,
        created_by_user_id=owner_user_id,
        event_type="ITEM_REMOVED",
        metadata_json={"portfolio_item_id": portfolio_item_id, "inventory_item_id": int(row.inventory_item_id)},
    )
    session.commit()
    session.refresh(row)
    pf.updated_at = datetime.now(timezone.utc)
    session.add(pf)
    session.commit()
    return serialize_portfolio_item(row)


def list_portfolio_items_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int,
    include_removed: bool,
    limit: int,
    offset: int,
) -> PortfolioItemListResponse:
    _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioItem).where(PortfolioItem.portfolio_id == portfolio_id)
    if not include_removed:
        stmt = stmt.where(PortfolioItem.removed_at.is_(None))
    stmt = stmt.order_by(col(PortfolioItem.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    count_stmt = select(func.count()).select_from(PortfolioItem).where(PortfolioItem.portfolio_id == portfolio_id)
    if not include_removed:
        count_stmt = count_stmt.where(PortfolioItem.removed_at.is_(None))
    total = int(session.exec(count_stmt).one())
    return PortfolioItemListResponse(items=[serialize_portfolio_item(r) for r in rows], total_items=total, limit=lim, offset=off)


def list_portfolio_items_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    portfolio_id: int | None,
    include_removed: bool,
    limit: int,
    offset: int,
) -> PortfolioItemListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioItem).join(Portfolio, PortfolioItem.portfolio_id == Portfolio.id)
    if owner_user_id is not None:
        stmt = stmt.where(Portfolio.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(PortfolioItem.portfolio_id == portfolio_id)
    if not include_removed:
        stmt = stmt.where(PortfolioItem.removed_at.is_(None))
    stmt = stmt.order_by(col(Portfolio.owner_user_id).asc(), col(PortfolioItem.portfolio_id).asc(), col(PortfolioItem.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    count_stmt = select(func.count()).select_from(PortfolioItem).join(Portfolio, PortfolioItem.portfolio_id == Portfolio.id)
    if owner_user_id is not None:
        count_stmt = count_stmt.where(Portfolio.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        count_stmt = count_stmt.where(PortfolioItem.portfolio_id == portfolio_id)
    if not include_removed:
        count_stmt = count_stmt.where(PortfolioItem.removed_at.is_(None))
    total = int(session.exec(count_stmt).one())
    return PortfolioItemListResponse(items=[serialize_portfolio_item(r) for r in rows], total_items=total, limit=lim, offset=off)


def serialize_exposure_snapshot(row: PortfolioExposureSnapshot) -> PortfolioExposureSnapshotRead:
    return PortfolioExposureSnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        generation_scope_key=row.generation_scope_key,
        replay_key=row.replay_key,
        generation_batch_checksum=row.generation_batch_checksum,
        exposure_type=row.exposure_type,
        exposure_key=row.exposure_key,
        item_count=int(row.item_count),
        total_fmv_amount=row.total_fmv_amount,
        total_cost_basis_amount=row.total_cost_basis_amount,
        total_realized_sales_amount=row.total_realized_sales_amount,
        percentage_of_portfolio_value=row.percentage_of_portfolio_value,
        percentage_of_portfolio_count=row.percentage_of_portfolio_count,
        exposure_status=row.exposure_status,
        checksum=row.checksum,
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def serialize_allocation_snapshot(row: PortfolioAllocationSnapshot) -> PortfolioAllocationSnapshotRead:
    return PortfolioAllocationSnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        generation_scope_key=row.generation_scope_key,
        replay_key=row.replay_key,
        total_item_count=int(row.total_item_count),
        total_fmv_amount=row.total_fmv_amount,
        total_cost_basis_amount=row.total_cost_basis_amount,
        total_realized_sales_amount=row.total_realized_sales_amount,
        graded_item_count=int(row.graded_item_count),
        raw_item_count=int(row.raw_item_count),
        listed_item_count=int(row.listed_item_count),
        sold_item_count=int(row.sold_item_count),
        high_liquidity_count=int(row.high_liquidity_count),
        low_liquidity_count=int(row.low_liquidity_count),
        grading_candidate_count=int(row.grading_candidate_count),
        sale_candidate_count=int(row.sale_candidate_count),
        duplicate_count=int(row.duplicate_count),
        convention_assigned_count=int(row.convention_assigned_count),
        checksum=row.checksum,
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _attach_exposure_evidence(
    session: Session,
    *,
    snapshot_row: PortfolioExposureSnapshot,
    inventory_item_ids: list[int],
    total_fmv: Decimal,
    total_sales: Decimal,
) -> None:
    session.add(
        PortfolioExposureEvidence(
            portfolio_exposure_snapshot_id=int(snapshot_row.id or 0),
            evidence_type="INVENTORY",
            source_table="inventory_copy",
            source_id=None,
            evidence_value_json={"inventory_item_ids": inventory_item_ids, "inventory_item_count": len(inventory_item_ids)},
        )
    )
    session.add(
        PortfolioExposureEvidence(
            portfolio_exposure_snapshot_id=int(snapshot_row.id or 0),
            evidence_type="FMV",
            evidence_value_json={"total_scope_fmv": str(_money(total_fmv))},
        )
    )
    if total_sales > ZERO:
        session.add(
            PortfolioExposureEvidence(
                portfolio_exposure_snapshot_id=int(snapshot_row.id or 0),
                evidence_type="SALES_LEDGER",
                evidence_value_json={"total_realized_line_subtotal_scope": str(_money(total_sales))},
            )
        )


def generate_exposure_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioGenerateScopePayload,
) -> PortfolioExposureGenerateResponse:
    snapshot_date_value = payload.snapshot_date or utc_today()
    scope_key_val = _scope_key(portfolio_id=payload.portfolio_id)
    replay_key_val = payload.replay_key

    if replay_key_val:
        existing = list(
            session.exec(
                select(PortfolioExposureSnapshot)
                .where(
                    PortfolioExposureSnapshot.owner_user_id == owner_user_id,
                    PortfolioExposureSnapshot.generation_scope_key == scope_key_val,
                    PortfolioExposureSnapshot.snapshot_date == snapshot_date_value,
                    PortfolioExposureSnapshot.replay_key == replay_key_val,
                )
                .order_by(
                    col(PortfolioExposureSnapshot.exposure_type).asc(),
                    col(PortfolioExposureSnapshot.exposure_key).asc(),
                    col(PortfolioExposureSnapshot.id).asc(),
                )
            ).all()
        )
        if existing:
            return PortfolioExposureGenerateResponse(
                generation_batch_checksum=existing[0].generation_batch_checksum,
                snapshot_date=snapshot_date_value,
                snapshots=[serialize_exposure_snapshot(r) for r in existing],
                replayed=True,
            )

    portfolio_fk: int | None = None
    if payload.portfolio_id is not None:
        pf = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=payload.portfolio_id)
        _require_active_portfolio(pf)
        portfolio_fk = int(pf.id or 0)

    facts, _listings, sale_totals, _gc, _cc, _dup_scope = _rows_for_owner_scope(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=payload.portfolio_id,
    )
    fact_map = {f.inventory_item_id: f for f in facts}
    total_items = len(facts)
    total_fmv = _money(sum((f.current_fmv or ZERO) for f in facts))

    buckets = _aggregate_exposure_buckets(facts)
    row_payloads: list[dict[str, Any]] = []
    for (etype, ekey), ids in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        grp_fmv = _money(sum((fact_map[i].current_fmv or ZERO) for i in ids if i in fact_map))
        grp_cost = _money(sum(fact_map[i].acquisition_cost for i in ids if i in fact_map))
        grp_sales = _money(sum(sale_totals.get(i, ZERO) for i in ids))

        pct_value = _pct((grp_fmv / total_fmv) * Decimal("100")) if total_fmv > ZERO else None
        pct_count = (
            _pct((Decimal(len(ids)) / Decimal(total_items)) * Decimal("100")) if total_items > 0 else None
        )
        exposure_status_val = _classify_exposure(
            pct_value=pct_value,
            pct_count=pct_count,
            total_fmv=total_fmv,
            total_items=total_items,
        )
        row_hashes_source = {
            "exposure_type": etype,
            "exposure_key": ekey,
            "inventory_item_ids": ids,
            "item_count": len(ids),
            "total_fmv_amount": str(grp_fmv),
            "total_cost_basis_amount": str(grp_cost),
            "total_realized_sales_amount": str(grp_sales),
            "percentage_of_portfolio_value": str(pct_value) if pct_value is not None else None,
            "percentage_of_portfolio_count": str(pct_count) if pct_count is not None else None,
            "exposure_status": exposure_status_val,
            "generation_scope_key": scope_key_val,
            "snapshot_date": snapshot_date_value.isoformat(),
            "portfolio_id": portfolio_fk,
        }
        checksum = _hash_payload(row_hashes_source)
        row_payloads.append(
            {
                "exposure_type": etype,
                "exposure_key": ekey,
                "inventory_item_ids": ids,
                "item_count": len(ids),
                "total_fmv_amount": grp_fmv if grp_fmv > ZERO else None,
                "total_cost_basis_amount": grp_cost if grp_cost > ZERO else None,
                "total_realized_sales_amount": grp_sales if grp_sales > ZERO else None,
                "percentage_of_portfolio_value": pct_value,
                "percentage_of_portfolio_count": pct_count,
                "exposure_status": exposure_status_val,
                "checksum": checksum,
            }
        )

    batch_hashes = [_hash_payload({"row_checksum": p["checksum"]}) for p in row_payloads]
    batch_checksum = _hash_payload({"generation_scope_key": scope_key_val, "ordered": batch_hashes})

    saved: list[PortfolioExposureSnapshot] = []
    for body in row_payloads:
        row = PortfolioExposureSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=portfolio_fk,
            generation_scope_key=scope_key_val,
            replay_key=replay_key_val,
            generation_batch_checksum=batch_checksum,
            exposure_type=body["exposure_type"],
            exposure_key=body["exposure_key"],
            item_count=int(body["item_count"]),
            total_fmv_amount=body["total_fmv_amount"],
            total_cost_basis_amount=body["total_cost_basis_amount"],
            total_realized_sales_amount=body["total_realized_sales_amount"],
            percentage_of_portfolio_value=body["percentage_of_portfolio_value"],
            percentage_of_portfolio_count=body["percentage_of_portfolio_count"],
            exposure_status=str(body["exposure_status"]),
            checksum=str(body["checksum"]),
            snapshot_date=snapshot_date_value,
        )
        session.add(row)
        saved.append(row)
    session.flush()
    if payload.portfolio_id:
        pid = int(payload.portfolio_id)
        _emit_lifecycle_event(
            session,
            portfolio_id=pid,
            created_by_user_id=owner_user_id,
            event_type="SNAPSHOT_GENERATED",
            metadata_json={"kind": "exposure", "batch_checksum": batch_checksum, "replay_key": replay_key_val},
        )
    session.commit()

    refreshed: list[PortfolioExposureSnapshot] = []
    for row, body in zip(saved, row_payloads, strict=True):
        session.refresh(row)
        grp_sales_ev = _money(sum(sale_totals.get(i, ZERO) for i in body["inventory_item_ids"]))
        _attach_exposure_evidence(
            session,
            snapshot_row=row,
            inventory_item_ids=body["inventory_item_ids"],
            total_fmv=_money(sum((fact_map[i].current_fmv or ZERO) for i in body["inventory_item_ids"] if i in fact_map)),
            total_sales=grp_sales_ev,
        )
        refreshed.append(row)
    session.commit()

    snapshots_read = [serialize_exposure_snapshot(r) for r in refreshed]
    return PortfolioExposureGenerateResponse(
        generation_batch_checksum=batch_checksum,
        snapshot_date=snapshot_date_value,
        snapshots=snapshots_read,
        replayed=False,
    )


def generate_allocation_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioGenerateScopePayload,
) -> PortfolioAllocationGenerateResponse:
    snapshot_date_value = payload.snapshot_date or utc_today()
    scope_key_val = _scope_key(portfolio_id=payload.portfolio_id)
    replay_key_val = payload.replay_key

    if replay_key_val:
        existing = session.exec(
            select(PortfolioAllocationSnapshot).where(
                PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
                PortfolioAllocationSnapshot.generation_scope_key == scope_key_val,
                PortfolioAllocationSnapshot.snapshot_date == snapshot_date_value,
                PortfolioAllocationSnapshot.replay_key == replay_key_val,
            )
        ).first()
        if existing:
            return PortfolioAllocationGenerateResponse(
                snapshot_date=snapshot_date_value,
                allocation=serialize_allocation_snapshot(existing),
                replayed=True,
            )

    portfolio_fk: int | None = None
    if payload.portfolio_id is not None:
        pf = _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=payload.portfolio_id)
        _require_active_portfolio(pf)
        portfolio_fk = int(pf.id or 0)

    facts, listings_by_item, sale_totals, grading_ids, convention_ids, duplicate_ids = _rows_for_owner_scope(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=payload.portfolio_id,
    )

    listed = 0
    sold = 0
    for fact in facts:
        listings = listings_by_item.get(fact.inventory_item_id, [])
        if any(str(l.status) in {"READY", "ACTIVE"} for l in listings):
            listed += 1
        if any(str(l.status) == "SOLD" for l in listings) or sale_totals.get(fact.inventory_item_id, ZERO) > ZERO:
            sold += 1

    high_liq = 0
    low_liq = 0
    for fact in facts:
        liq = fact.liquidity_status
        if liq is None:
            low_liq += 1
        elif liq in {"HIGH", "MODERATE"}:
            high_liq += 1
        else:
            low_liq += 1

    grading_candidate_ct = sum(1 for fact in facts if fact.inventory_item_id in grading_ids)
    sale_candidate_ct = sum(1 for fact in facts if fact.hold_status == "sell")
    duplicate_ct = sum(1 for fact in facts if fact.inventory_item_id in duplicate_ids)
    convention_ct = sum(1 for fact in facts if fact.inventory_item_id in convention_ids)
    graded_ct = sum(1 for fact in facts if fact.grade_status != "raw")
    raw_ct = sum(1 for fact in facts if fact.grade_status == "raw")

    total_items = len(facts)
    total_fmv = _money(sum((f.current_fmv or ZERO) for f in facts))
    total_cost = _money(sum(f.acquisition_cost for f in facts))
    total_sales = _money(sum(sale_totals.get(f.inventory_item_id, ZERO) for f in facts))

    alloc_payload = {
        "generation_scope_key": scope_key_val,
        "snapshot_date": snapshot_date_value.isoformat(),
        "portfolio_id": portfolio_fk,
        "total_item_count": total_items,
        "total_fmv_amount": str(total_fmv),
        "total_cost_basis_amount": str(total_cost),
        "total_realized_sales_amount": str(total_sales),
        "graded_item_count": graded_ct,
        "raw_item_count": raw_ct,
        "listed_item_count": listed,
        "sold_item_count": sold,
        "high_liquidity_count": high_liq,
        "low_liquidity_count": low_liq,
        "grading_candidate_count": grading_candidate_ct,
        "sale_candidate_count": sale_candidate_ct,
        "duplicate_count": duplicate_ct,
        "convention_assigned_count": convention_ct,
    }
    checksum = _hash_payload(alloc_payload)
    empty_fmv_ok = total_fmv if total_fmv > ZERO else None
    alloc_row = PortfolioAllocationSnapshot(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_fk,
        generation_scope_key=scope_key_val,
        replay_key=replay_key_val,
        total_item_count=total_items,
        total_fmv_amount=empty_fmv_ok,
        total_cost_basis_amount=total_cost if total_cost > ZERO else None,
        total_realized_sales_amount=total_sales if total_sales > ZERO else None,
        graded_item_count=graded_ct,
        raw_item_count=raw_ct,
        listed_item_count=listed,
        sold_item_count=sold,
        high_liquidity_count=high_liq,
        low_liquidity_count=low_liq,
        grading_candidate_count=grading_candidate_ct,
        sale_candidate_count=sale_candidate_ct,
        duplicate_count=duplicate_ct,
        convention_assigned_count=convention_ct,
        checksum=checksum,
        snapshot_date=snapshot_date_value,
    )
    session.add(alloc_row)

    if payload.portfolio_id:
        _emit_lifecycle_event(
            session,
            portfolio_id=int(payload.portfolio_id),
            created_by_user_id=owner_user_id,
            event_type="SNAPSHOT_GENERATED",
            metadata_json={"kind": "allocation", "checksum": checksum, "replay_key": replay_key_val},
        )
    session.commit()
    session.refresh(alloc_row)

    return PortfolioAllocationGenerateResponse(
        snapshot_date=snapshot_date_value,
        allocation=serialize_allocation_snapshot(alloc_row),
        replayed=False,
    )


def _latest_exposure_batch_checksum(
    session: Session,
    *,
    owner_user_id: int,
    generation_scope_key: str,
) -> str | None:
    row = session.exec(
        select(PortfolioExposureSnapshot)
        .where(
            PortfolioExposureSnapshot.owner_user_id == owner_user_id,
            PortfolioExposureSnapshot.generation_scope_key == generation_scope_key,
        )
        .order_by(col(PortfolioExposureSnapshot.created_at).desc(), col(PortfolioExposureSnapshot.id).desc())
    ).first()
    return row.generation_batch_checksum if row else None


def list_exposure_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None,
    generation_batch_checksum: str | None,
    latest_batch: bool,
    limit: int,
    offset: int,
) -> PortfolioExposureSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    scope = _scope_key(portfolio_id=portfolio_id)

    checksum_filter = generation_batch_checksum
    if latest_batch:
        checksum_filter = checksum_filter or _latest_exposure_batch_checksum(
            session, owner_user_id=owner_user_id, generation_scope_key=scope
        )

    stmt = select(PortfolioExposureSnapshot).where(
        PortfolioExposureSnapshot.owner_user_id == owner_user_id,
        PortfolioExposureSnapshot.generation_scope_key == scope,
    )
    if portfolio_id is None:
        stmt = stmt.where(PortfolioExposureSnapshot.portfolio_id.is_(None))
    else:
        stmt = stmt.where(PortfolioExposureSnapshot.portfolio_id == portfolio_id)
    if checksum_filter:
        stmt = stmt.where(PortfolioExposureSnapshot.generation_batch_checksum == checksum_filter)
    stmt = stmt.order_by(col(PortfolioExposureSnapshot.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    count_stmt = select(func.count()).select_from(PortfolioExposureSnapshot).where(
        PortfolioExposureSnapshot.owner_user_id == owner_user_id,
        PortfolioExposureSnapshot.generation_scope_key == scope,
    )
    if portfolio_id is None:
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.portfolio_id.is_(None))
    else:
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.portfolio_id == portfolio_id)
    if checksum_filter:
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.generation_batch_checksum == checksum_filter)
    total = int(session.exec(count_stmt).one())
    return PortfolioExposureSnapshotListResponse(
        items=[serialize_exposure_snapshot(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def list_exposure_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    portfolio_id: int | None,
    generation_batch_checksum: str | None,
    latest_batch: bool,
    limit: int,
    offset: int,
) -> PortfolioExposureSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioExposureSnapshot)
    count_stmt = select(func.count()).select_from(PortfolioExposureSnapshot)

    if owner_user_id is not None:
        stmt = stmt.where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        scope = _scope_key(portfolio_id=portfolio_id)
        stmt = stmt.where(
            PortfolioExposureSnapshot.generation_scope_key == scope,
            PortfolioExposureSnapshot.portfolio_id == portfolio_id,
        )
        count_stmt = count_stmt.where(
            PortfolioExposureSnapshot.generation_scope_key == scope,
            PortfolioExposureSnapshot.portfolio_id == portfolio_id,
        )

    checksum_filter = generation_batch_checksum
    if latest_batch and owner_user_id is not None:
        if portfolio_id is None:
            checksum_filter = checksum_filter or _latest_exposure_batch_checksum(
                session, owner_user_id=owner_user_id, generation_scope_key=SCOPE_ALL_INVENTORY
            )
        else:
            checksum_filter = checksum_filter or _latest_exposure_batch_checksum(
                session, owner_user_id=owner_user_id, generation_scope_key=_scope_key(portfolio_id=portfolio_id)
            )

    if checksum_filter:
        stmt = stmt.where(PortfolioExposureSnapshot.generation_batch_checksum == checksum_filter)
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.generation_batch_checksum == checksum_filter)

    stmt = stmt.order_by(col(PortfolioExposureSnapshot.owner_user_id).asc(), col(PortfolioExposureSnapshot.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    total = int(session.exec(count_stmt).one())
    return PortfolioExposureSnapshotListResponse(
        items=[serialize_exposure_snapshot(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def serialize_evidence_row(row: PortfolioExposureEvidence) -> PortfolioExposureEvidenceRead:
    return PortfolioExposureEvidenceRead(
        id=int(row.id or 0),
        portfolio_exposure_snapshot_id=int(row.portfolio_exposure_snapshot_id),
        evidence_type=row.evidence_type,
        source_id=row.source_id,
        source_table=row.source_table,
        evidence_value_json=row.evidence_value_json,
        created_at=row.created_at,
    )


def list_exposure_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_exposure_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> PortfolioExposureEvidenceListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(PortfolioExposureEvidence)
        .join(
            PortfolioExposureSnapshot,
            PortfolioExposureEvidence.portfolio_exposure_snapshot_id == PortfolioExposureSnapshot.id,
        )
        .where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(PortfolioExposureEvidence)
        .join(
            PortfolioExposureSnapshot,
            PortfolioExposureEvidence.portfolio_exposure_snapshot_id == PortfolioExposureSnapshot.id,
        )
        .where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
    )
    if portfolio_exposure_snapshot_id is not None:
        stmt = stmt.where(PortfolioExposureEvidence.portfolio_exposure_snapshot_id == portfolio_exposure_snapshot_id)
        count_stmt = count_stmt.where(
            PortfolioExposureEvidence.portfolio_exposure_snapshot_id == portfolio_exposure_snapshot_id
        )
    stmt = stmt.order_by(col(PortfolioExposureEvidence.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    total = int(session.exec(count_stmt).one())
    return PortfolioExposureEvidenceListResponse(
        items=[serialize_evidence_row(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def list_exposure_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    portfolio_exposure_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> PortfolioExposureEvidenceListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioExposureEvidence).join(
        PortfolioExposureSnapshot,
        PortfolioExposureEvidence.portfolio_exposure_snapshot_id == PortfolioExposureSnapshot.id,
    )
    count_stmt = (
        select(func.count())
        .select_from(PortfolioExposureEvidence)
        .join(
            PortfolioExposureSnapshot,
            PortfolioExposureEvidence.portfolio_exposure_snapshot_id == PortfolioExposureSnapshot.id,
        )
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(PortfolioExposureSnapshot.owner_user_id == owner_user_id)
    if portfolio_exposure_snapshot_id is not None:
        stmt = stmt.where(PortfolioExposureEvidence.portfolio_exposure_snapshot_id == portfolio_exposure_snapshot_id)
        count_stmt = count_stmt.where(
            PortfolioExposureEvidence.portfolio_exposure_snapshot_id == portfolio_exposure_snapshot_id
        )
    stmt = stmt.order_by(col(PortfolioExposureSnapshot.owner_user_id).asc(), col(PortfolioExposureEvidence.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    total = int(session.exec(count_stmt).one())
    return PortfolioExposureEvidenceListResponse(
        items=[serialize_evidence_row(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def _latest_allocation_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    generation_scope_key: str,
) -> PortfolioAllocationSnapshot | None:
    return session.exec(
        select(PortfolioAllocationSnapshot)
        .where(
            PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
            PortfolioAllocationSnapshot.generation_scope_key == generation_scope_key,
        )
        .order_by(col(PortfolioAllocationSnapshot.created_at).desc(), col(PortfolioAllocationSnapshot.id).desc())
    ).first()


def list_allocation_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> PortfolioAllocationSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    scope = _scope_key(portfolio_id=portfolio_id)

    base_stmt = select(PortfolioAllocationSnapshot).where(
        PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
        PortfolioAllocationSnapshot.generation_scope_key == scope,
    )
    if portfolio_id is None:
        base_stmt = base_stmt.where(PortfolioAllocationSnapshot.portfolio_id.is_(None))
    else:
        base_stmt = base_stmt.where(PortfolioAllocationSnapshot.portfolio_id == portfolio_id)

    if latest_only:
        stmt = base_stmt.order_by(
            col(PortfolioAllocationSnapshot.created_at).desc(), col(PortfolioAllocationSnapshot.id).desc()
        ).limit(1)
        solo = session.exec(stmt).first()
        items_list = [serialize_allocation_snapshot(solo)] if solo else []
        total = len(items_list)
        return PortfolioAllocationSnapshotListResponse(items=items_list, total_items=total, limit=lim, offset=off)

    stmt = base_stmt.order_by(col(PortfolioAllocationSnapshot.id).asc()).offset(off).limit(lim)
    rows = list(session.exec(stmt).all())
    count_stmt = select(func.count()).select_from(PortfolioAllocationSnapshot).where(
        PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
        PortfolioAllocationSnapshot.generation_scope_key == scope,
    )
    if portfolio_id is None:
        count_stmt = count_stmt.where(PortfolioAllocationSnapshot.portfolio_id.is_(None))
    else:
        count_stmt = count_stmt.where(PortfolioAllocationSnapshot.portfolio_id == portfolio_id)
    total = int(session.exec(count_stmt).one())
    return PortfolioAllocationSnapshotListResponse(
        items=[serialize_allocation_snapshot(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def list_allocation_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    portfolio_id: int | None,
    limit: int,
    offset: int,
) -> PortfolioAllocationSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioAllocationSnapshot)
    count_stmt = select(func.count()).select_from(PortfolioAllocationSnapshot)

    if owner_user_id is not None:
        stmt = stmt.where(PortfolioAllocationSnapshot.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(PortfolioAllocationSnapshot.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        scope = _scope_key(portfolio_id=portfolio_id)
        stmt = stmt.where(
            PortfolioAllocationSnapshot.generation_scope_key == scope,
            PortfolioAllocationSnapshot.portfolio_id == portfolio_id,
        )
        count_stmt = count_stmt.where(
            PortfolioAllocationSnapshot.generation_scope_key == scope,
            PortfolioAllocationSnapshot.portfolio_id == portfolio_id,
        )

    stmt = stmt.order_by(col(PortfolioAllocationSnapshot.owner_user_id).asc(), col(PortfolioAllocationSnapshot.id).asc())
    rows = list(session.exec(stmt.offset(off).limit(lim)).all())
    total = int(session.exec(count_stmt).one())
    return PortfolioAllocationSnapshotListResponse(
        items=[serialize_allocation_snapshot(r) for r in rows], total_items=total, limit=lim, offset=off
    )


def get_portfolio_ops(session: Session, *, portfolio_id: int, owner_user_id: int | None) -> PortfolioRead:
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id)
    if owner_user_id is not None:
        stmt = stmt.where(Portfolio.owner_user_id == owner_user_id)
    row = session.exec(stmt).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio not found")
    return serialize_portfolio(row)


def portfolio_intelligence_summary(session: Session, *, owner_user_id: int) -> PortfolioIntelligenceSummary:
    scope = SCOPE_ALL_INVENTORY
    active_row = session.exec(
        select(func.count())
        .select_from(Portfolio)
        .where(Portfolio.owner_user_id == owner_user_id, Portfolio.status == "ACTIVE")
    ).one()
    active_portfolios = int(active_row or 0)
    alloc = _latest_allocation_snapshot(session, owner_user_id=owner_user_id, generation_scope_key=scope)
    latest_batch_checksum = _latest_exposure_batch_checksum(session, owner_user_id=owner_user_id, generation_scope_key=scope)
    exposure_rows = list(
        session.exec(
            select(PortfolioExposureSnapshot)
            .where(
                PortfolioExposureSnapshot.owner_user_id == owner_user_id,
                PortfolioExposureSnapshot.generation_scope_key == scope,
                PortfolioExposureSnapshot.portfolio_id.is_(None),
            )
            .order_by(col(PortfolioExposureSnapshot.created_at).desc(), col(PortfolioExposureSnapshot.id).desc())
        ).all(),
    )

    filtered_exposure = (
        [er for er in exposure_rows if latest_batch_checksum and er.generation_batch_checksum == latest_batch_checksum]
        if latest_batch_checksum
        else []
    )
    over_candidates = sorted(
        [er for er in filtered_exposure if er.exposure_status in {"CONCENTRATED", "OVEREXPOSED"}],
        key=lambda r: (
            -(
                (
                    r.percentage_of_portfolio_value
                    or r.percentage_of_portfolio_count
                    or ZERO
                )
            ),
            int(r.id or 0),
        ),
    )
    teaser = [
        PortfolioIntelligenceExposureTeaser(
            exposure_type=r.exposure_type,
            exposure_key=r.exposure_key,
            exposure_status=r.exposure_status,
            percentage_of_portfolio_value=r.percentage_of_portfolio_value or r.percentage_of_portfolio_count,
        )
        for r in over_candidates[:12]
    ]

    return PortfolioIntelligenceSummary(
        active_portfolio_count=active_portfolios,
        latest_allocation_scope_key=SCOPE_ALL_INVENTORY if alloc else None,
        latest_allocation_checksum=alloc.checksum if alloc else None,
        latest_generation_batch_checksum=latest_batch_checksum,
        total_item_count=int(alloc.total_item_count) if alloc else None,
        total_fmv_amount=alloc.total_fmv_amount if alloc else None,
        total_cost_basis_amount=alloc.total_cost_basis_amount if alloc else None,
        graded_item_count=int(alloc.graded_item_count) if alloc else None,
        raw_item_count=int(alloc.raw_item_count) if alloc else None,
        low_liquidity_count=int(alloc.low_liquidity_count) if alloc else None,
        high_liquidity_count=int(alloc.high_liquidity_count) if alloc else None,
        overexposed_rows=teaser,
    )


def inventory_portfolio_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    publisher_display_name: str,
) -> InventoryPortfolioIntelligenceTeaser:
    member_rows = list(
        session.exec(
            select(PortfolioItem, Portfolio)
            .join(Portfolio, PortfolioItem.portfolio_id == Portfolio.id)
            .where(
                Portfolio.owner_user_id == owner_user_id,
                PortfolioItem.inventory_item_id == inventory_copy_id,
                PortfolioItem.removed_at.is_(None),
            )
            .order_by(col(Portfolio.id).asc())
        ).all(),
    )
    memberships = [
        PortfolioMembershipRead(
            portfolio_id=int(pf.id or 0),
            portfolio_name=pf.name,
            portfolio_type=pf.portfolio_type,
            allocation_role=item.allocation_role,
        )
        for item, pf in member_rows
    ]
    slug = _slug(publisher_display_name)
    latest_batch = _latest_exposure_batch_checksum(session, owner_user_id=owner_user_id, generation_scope_key=SCOPE_ALL_INVENTORY)
    pub_stat: str | None = None
    pub_pct: Decimal | None = None
    if latest_batch:
        exp = session.exec(
            select(PortfolioExposureSnapshot)
            .where(
                PortfolioExposureSnapshot.owner_user_id == owner_user_id,
                PortfolioExposureSnapshot.generation_scope_key == SCOPE_ALL_INVENTORY,
                PortfolioExposureSnapshot.portfolio_id.is_(None),
                PortfolioExposureSnapshot.generation_batch_checksum == latest_batch,
                PortfolioExposureSnapshot.exposure_type == "publisher",
                PortfolioExposureSnapshot.exposure_key == slug,
            )
            .order_by(col(PortfolioExposureSnapshot.id).asc())
            .limit(1)
        ).first()
        if exp:
            pub_stat = exp.exposure_status
            pub_pct = exp.percentage_of_portfolio_value or exp.percentage_of_portfolio_count
    return InventoryPortfolioIntelligenceTeaser(
        memberships=memberships, publisher_exposure_status=pub_stat, publisher_exposure_pct_value=pub_pct
    )
