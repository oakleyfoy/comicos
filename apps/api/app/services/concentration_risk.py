"""P38-05 deterministic concentration-risk intelligence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    ComicTitle,
    ConcentrationRiskEvidence,
    ConcentrationRiskFactor,
    ConcentrationRiskHistory,
    ConcentrationRiskSnapshot,
    GradingRecommendation,
    GradingRiskSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    Order,
    OrderItem,
    Portfolio,
    PortfolioAllocationSnapshot,
    PortfolioExposureSnapshot,
    PortfolioItem,
    PortfolioLiquiditySnapshot,
    Publisher,
    SaleRecord,
    SaleRecordLineItem,
    Variant,
)
from app.schemas.concentration_risk import (
    ConcentrationRiskDetailRead,
    ConcentrationRiskEvidenceListResponse,
    ConcentrationRiskEvidenceRead,
    ConcentrationRiskFactorListResponse,
    ConcentrationRiskFactorRead,
    ConcentrationRiskGeneratePayload,
    ConcentrationRiskGenerateResponse,
    ConcentrationRiskHistoryListResponse,
    ConcentrationRiskHistoryRead,
    ConcentrationRiskListResponse,
    ConcentrationRiskSnapshotRead,
    InventoryConcentrationRiskTeaser,
)
from app.services.duplicate_consolidation import inventory_duplicate_teaser

SCOPE_ALL_INVENTORY = "ALL_INVENTORY"
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.01")
REPLAY_EMPTY = ""
EXPOSURE_SEVERITY = {
    "HEALTHY": 0,
    "WATCH": 1,
    "CONCENTRATED": 2,
    "OVEREXPOSED": 3,
    "CRITICAL": 4,
}
TYPE_MAP = {
    "publisher": "publisher",
    "character": "character",
    "title": "title",
    "creator": "creator",
    "era": "era",
    "variant_family": "variant_family",
    "grading_status": "grade_status",
    "liquidity_status": "liquidity_status",
    "acquisition_source": "acquisition_source",
}
LIQUIDITY_RISK_WEIGHTS = {
    "HIGH": Decimal("0.25"),
    "MODERATE": Decimal("0.50"),
    "MEDIUM": Decimal("0.50"),
    "LOW": Decimal("0.75"),
    "ILLIQUID": Decimal("1.00"),
    "unknown": Decimal("0.60"),
}
FACTOR_WEIGHTS = {
    "fmv_dependence": Decimal("0.35"),
    "liquidity_fragility": Decimal("0.25"),
    "duplicate_overlap": Decimal("0.15"),
    "grading_overlap": Decimal("0.10"),
    "sales_dependence": Decimal("0.10"),
    "category_fragility": Decimal("0.05"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def scope_key(portfolio_id: int | None) -> str:
    return SCOPE_ALL_INVENTORY if portfolio_id is None else f"PORTFOLIO_{int(portfolio_id)}"


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _norm_rk(value: str | None) -> str:
    return (value or "").strip()


def _money(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _score_q(value: Decimal) -> Decimal:
    return min(HUNDRED, max(ZERO, value)).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _slug(value: str | None) -> str:
    txt = (value or "").strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in txt:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif ch in {" ", "-", "_", "/", ":"} and not prev_dash:
            out.append("-")
            prev_dash = True
    cleaned = "".join(out).strip("-")
    return cleaned or "unknown"


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


def _liquidity_risk_weight(status: str | None) -> Decimal:
    if status is None:
        return LIQUIDITY_RISK_WEIGHTS["unknown"]
    return LIQUIDITY_RISK_WEIGHTS.get(status.upper(), LIQUIDITY_RISK_WEIGHTS["unknown"])


def _classify_status(
    *,
    concentration_score: Decimal,
    primary_share_pct: Decimal,
    liquidity_weighted_concentration: Decimal,
) -> str:
    if primary_share_pct >= Decimal("55") or liquidity_weighted_concentration >= Decimal("45"):
        return "CRITICAL"
    if concentration_score >= Decimal("70"):
        return "CRITICAL"
    if concentration_score >= Decimal("50"):
        return "OVEREXPOSED"
    if concentration_score >= Decimal("35"):
        return "CONCENTRATED"
    if concentration_score >= Decimal("20"):
        return "WATCH"
    return "HEALTHY"


@dataclass(frozen=True)
class _CopyFact:
    inventory_item_id: int
    canonical_comic_issue_id: int
    publisher_key: str
    title_key: str
    character_key: str
    creator_key: str
    era_key: str
    variant_family_key: str
    grading_status_key: str
    liquidity_status_key: str
    acquisition_source_key: str
    current_fmv: Decimal | None
    acquisition_cost: Decimal
    has_duplicate_overlap: bool
    has_grading_overlap: bool
    sale_total: Decimal
    listing_count: int
    listing_stale_flag: bool
    listing_intelligence_status: str | None


def _portfolio_for_owner(session: Session, *, owner_user_id: int, portfolio_id: int) -> Portfolio:
    row = session.get(Portfolio, portfolio_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found for owner")
    return row


def _latest_sale_lines(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(SaleRecordLineItem.inventory_item_id, SaleRecordLineItem.line_subtotal_amount)
        .join(SaleRecord, SaleRecordLineItem.sale_record_id == SaleRecord.id)
        .where(
            SaleRecord.owner_user_id == owner_user_id,
            SaleRecord.status == "RECORDED",
            SaleRecordLineItem.inventory_item_id.is_not(None),
            col(SaleRecordLineItem.inventory_item_id).in_(inv_ids),
        )
    ).all()
    for iid, amt in rows:
        inv_id = int(iid or 0)
        if inv_id:
            out[inv_id] = out.get(inv_id, ZERO) + _money(amt)
    return out


def _latest_liquidity_map(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> dict[int, tuple[str | None, Decimal, Decimal]]:
    out: dict[int, tuple[str | None, Decimal, Decimal]] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(
            InventoryLiquiditySnapshot.inventory_item_id,
            InventoryLiquiditySnapshot.liquidity_status,
            InventoryLiquiditySnapshot.sell_through_rate_pct,
            InventoryLiquiditySnapshot.stale_listing_rate_pct,
        )
        .where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            col(InventoryLiquiditySnapshot.inventory_item_id).in_(inv_ids),
            col(InventoryLiquiditySnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc(), col(InventoryLiquiditySnapshot.id).desc())
    ).all()
    for iid, status_val, sell, stale in rows:
        inv_id = int(iid or 0)
        if inv_id and inv_id not in out:
            out[inv_id] = (str(status_val) if status_val is not None else None, _pct(sell), _pct(stale))
    return out


def _latest_listing_map(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> dict[int, ListingIntelligenceSnapshot]:
    out: dict[int, ListingIntelligenceSnapshot] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(ListingIntelligenceSnapshot)
        .where(
            ListingIntelligenceSnapshot.owner_user_id == owner_user_id,
            col(ListingIntelligenceSnapshot.inventory_item_id).in_(inv_ids),
            col(ListingIntelligenceSnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(ListingIntelligenceSnapshot.snapshot_date).desc(), col(ListingIntelligenceSnapshot.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_grading_map(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> dict[int, tuple[GradingRecommendation | None, GradingRiskSnapshot | None]]:
    reco_map: dict[int, GradingRecommendation] = {}
    risk_map: dict[int, GradingRiskSnapshot] = {}
    if inv_ids:
        reco_rows = session.exec(
            select(GradingRecommendation)
            .where(
                GradingRecommendation.owner_user_id == owner_user_id,
                col(GradingRecommendation.inventory_item_id).in_(inv_ids),
                col(GradingRecommendation.inventory_item_id).is_not(None),
            )
            .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
        ).all()
        for row in reco_rows:
            iid = int(row.inventory_item_id or 0)
            if iid and iid not in reco_map:
                reco_map[iid] = row
        risk_rows = session.exec(
            select(GradingRiskSnapshot)
            .where(
                GradingRiskSnapshot.owner_user_id == owner_user_id,
                col(GradingRiskSnapshot.inventory_item_id).in_(inv_ids),
                col(GradingRiskSnapshot.inventory_item_id).is_not(None),
            )
            .order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
        ).all()
        for row in risk_rows:
            iid = int(row.inventory_item_id or 0)
            if iid and iid not in risk_map:
                risk_map[iid] = row
    return {iid: (reco_map.get(iid), risk_map.get(iid)) for iid in inv_ids}


def _active_listing_count(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(Listing.inventory_copy_id)
        .where(
            Listing.owner_user_id == owner_user_id,
            Listing.archived_at.is_(None),
            col(Listing.inventory_copy_id).in_(inv_ids),
        )
    ).all()
    for (iid,) in rows:
        inv_id = int(iid or 0)
        if inv_id:
            out[inv_id] = out.get(inv_id, 0) + 1
    return out


def _latest_scope_support(
    session: Session, *, owner_user_id: int, portfolio_id: int | None
) -> tuple[PortfolioAllocationSnapshot | None, PortfolioLiquiditySnapshot | None, dict[tuple[str, str], PortfolioExposureSnapshot]]:
    scope = scope_key(portfolio_id)
    alloc = session.exec(
        select(PortfolioAllocationSnapshot)
        .where(
            PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
            PortfolioAllocationSnapshot.generation_scope_key == scope,
        )
        .order_by(col(PortfolioAllocationSnapshot.created_at).desc(), col(PortfolioAllocationSnapshot.id).desc())
    ).first()
    liq = session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == scope,
        )
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    ).first()
    exposure_rows = session.exec(
        select(PortfolioExposureSnapshot)
        .where(
            PortfolioExposureSnapshot.owner_user_id == owner_user_id,
            PortfolioExposureSnapshot.generation_scope_key == scope,
            PortfolioExposureSnapshot.portfolio_id == portfolio_id,
        )
        .order_by(col(PortfolioExposureSnapshot.created_at).desc(), col(PortfolioExposureSnapshot.id).desc())
    ).all()
    latest_batch = str(exposure_rows[0].generation_batch_checksum) if exposure_rows else None
    exposure_map: dict[tuple[str, str], PortfolioExposureSnapshot] = {}
    for row in exposure_rows:
        if latest_batch and str(row.generation_batch_checksum) != latest_batch:
            continue
        key = (str(row.exposure_type), str(row.exposure_key))
        if key not in exposure_map:
            exposure_map[key] = row
    return alloc, liq, exposure_map


def _scope_inventory_rows(session: Session, *, owner_user_id: int, portfolio_id: int | None) -> list[_CopyFact]:
    stmt = (
        select(
            InventoryCopy,
            Order,
            Publisher.name,
            ComicTitle.name,
            ComicIssue.issue_number,
            ComicIssue.id,
            Variant.id,
            Variant.variant_type,
            Variant.cover_name,
            Variant.ratio,
            Variant.printing,
        )
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
    rows = session.exec(stmt).all()
    inv_ids = [int(inv.id or 0) for inv, *_rest in rows if int(inv.id or 0)]
    liquidity_map = _latest_liquidity_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    sale_map = _latest_sale_lines(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_map = _latest_listing_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_counts = _active_listing_count(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    grading_map = _latest_grading_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    duplicate_teasers = {
        inv_id: inventory_duplicate_teaser(session, owner_user_id=owner_user_id, inventory_item_id=inv_id)
        for inv_id in inv_ids
    }

    facts: list[_CopyFact] = []
    for inv, ord_row, publisher_name, title_name, issue_number, issue_id, variant_id, variant_type, cover_name, ratio, printing in rows:
        iid = int(inv.id or 0)
        if not iid:
            continue
        release_year = inv.release_year
        if release_year is None and inv.release_date is not None:
            release_year = inv.release_date.year
        liq_status, _sell, stale_rate = liquidity_map.get(iid, (None, ZERO, ZERO))
        listing = listing_map.get(iid)
        grading_reco, grading_risk = grading_map.get(iid, (None, None))
        dup = duplicate_teasers.get(iid)
        duplicate_bad = False
        if dup is not None:
            duplicate_bad = (
                getattr(dup, "worst_duplication_status", None) in {"REDUNDANT", "OVEREXPOSED"}
                or getattr(dup, "primary_consolidation_action", None) in {"SELL_DUPLICATES", "REDUCE_EXPOSURE"}
            )
        grading_overlap = bool(
            str(inv.grade_status or "").lower() != "raw"
            or grading_reco is not None
            or grading_risk is not None
        )
        variant_anchor = variant_type or cover_name or ratio or printing or f"variant-{int(variant_id or 0)}"
        facts.append(
            _CopyFact(
                inventory_item_id=iid,
                canonical_comic_issue_id=int(issue_id or 0),
                publisher_key=_slug(publisher_name),
                title_key=_slug(f"{title_name}::{issue_number}"),
                character_key="unknown",
                creator_key="unknown",
                era_key=_era_bucket(release_year),
                variant_family_key=_slug(f"{title_name}::{issue_number}::{variant_anchor}"),
                grading_status_key=_slug(str(inv.grade_status or "unknown")),
                liquidity_status_key=_slug(str(liq_status or "unknown")),
                acquisition_source_key=_slug(f"{ord_row.source_type or 'unknown'}:{ord_row.retailer}"),
                current_fmv=_money(inv.current_fmv) if inv.current_fmv is not None else None,
                acquisition_cost=_money(inv.acquisition_cost),
                has_duplicate_overlap=duplicate_bad,
                has_grading_overlap=grading_overlap,
                sale_total=sale_map.get(iid, ZERO),
                listing_count=listing_counts.get(iid, 0),
                listing_stale_flag=bool(getattr(listing, "stale_risk_flag", False) or stale_rate >= Decimal("70")),
                listing_intelligence_status=str(getattr(listing, "intelligence_status", None) or "") or None,
            )
        )
    return facts


def _bucket_pairs(fact: _CopyFact) -> tuple[tuple[str, str], ...]:
    return (
        ("publisher", fact.publisher_key),
        ("character", fact.character_key),
        ("title", fact.title_key),
        ("creator", fact.creator_key),
        ("era", fact.era_key),
        ("variant_family", fact.variant_family_key),
        ("grading_status", fact.grading_status_key),
        ("liquidity_status", fact.liquidity_status_key),
        ("acquisition_source", fact.acquisition_source_key),
    )


def _snapshot_read(row: ConcentrationRiskSnapshot) -> ConcentrationRiskSnapshotRead:
    return ConcentrationRiskSnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        concentration_type=str(row.concentration_type),
        concentration_key=str(row.concentration_key),
        total_item_count=int(row.total_item_count),
        total_fmv_amount=row.total_fmv_amount,
        percentage_of_portfolio=row.percentage_of_portfolio,
        concentration_score=row.concentration_score,
        liquidity_weighted_concentration=row.liquidity_weighted_concentration,
        exposure_status=str(row.exposure_status),
        diversification_score=row.diversification_score,
        checksum=str(row.checksum),
        replay_key=str(row.replay_key),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _evidence_read(row: ConcentrationRiskEvidence) -> ConcentrationRiskEvidenceRead:
    return ConcentrationRiskEvidenceRead(
        id=int(row.id or 0),
        concentration_risk_snapshot_id=int(row.concentration_risk_snapshot_id),
        evidence_type=str(row.evidence_type),
        source_id=row.source_id,
        source_table=row.source_table,
        evidence_value_json=dict(row.evidence_value_json or {}),
        created_at=row.created_at,
    )


def _factor_read(row: ConcentrationRiskFactor) -> ConcentrationRiskFactorRead:
    return ConcentrationRiskFactorRead(
        id=int(row.id or 0),
        concentration_risk_snapshot_id=int(row.concentration_risk_snapshot_id),
        factor_key=str(row.factor_key),
        factor_score=row.factor_score,
        weighting=row.weighting,
        created_at=row.created_at,
    )


def _history_read(row: ConcentrationRiskHistory) -> ConcentrationRiskHistoryRead:
    return ConcentrationRiskHistoryRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        portfolio_id=row.portfolio_id,
        concentration_type=str(row.concentration_type),
        concentration_key=str(row.concentration_key),
        exposure_status=str(row.exposure_status),
        concentration_score=row.concentration_score,
        diversification_score=row.diversification_score,
        checksum=str(row.checksum),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _detail_read(session: Session, row: ConcentrationRiskSnapshot) -> ConcentrationRiskDetailRead:
    sid = int(row.id or 0)
    evidence = session.exec(
        select(ConcentrationRiskEvidence)
        .where(ConcentrationRiskEvidence.concentration_risk_snapshot_id == sid)
        .order_by(col(ConcentrationRiskEvidence.id).asc())
    ).all()
    factors = session.exec(
        select(ConcentrationRiskFactor)
        .where(ConcentrationRiskFactor.concentration_risk_snapshot_id == sid)
        .order_by(col(ConcentrationRiskFactor.factor_key).asc(), col(ConcentrationRiskFactor.id).asc())
    ).all()
    history = session.exec(
        select(ConcentrationRiskHistory)
        .where(
            ConcentrationRiskHistory.owner_user_id == row.owner_user_id,
            ConcentrationRiskHistory.portfolio_id == row.portfolio_id,
            ConcentrationRiskHistory.concentration_type == row.concentration_type,
            ConcentrationRiskHistory.concentration_key == row.concentration_key,
        )
        .order_by(col(ConcentrationRiskHistory.snapshot_date).desc(), col(ConcentrationRiskHistory.id).desc())
    ).all()
    return ConcentrationRiskDetailRead(
        snapshot=_snapshot_read(row),
        evidence=[_evidence_read(item) for item in evidence],
        factors=[_factor_read(item) for item in factors],
        history=[_history_read(item) for item in history],
    )


def _append_history(session: Session, row: ConcentrationRiskSnapshot) -> bool:
    existing = session.exec(
        select(ConcentrationRiskHistory).where(
            ConcentrationRiskHistory.owner_user_id == row.owner_user_id,
            ConcentrationRiskHistory.portfolio_id == row.portfolio_id,
            ConcentrationRiskHistory.concentration_type == row.concentration_type,
            ConcentrationRiskHistory.concentration_key == row.concentration_key,
            ConcentrationRiskHistory.snapshot_date == row.snapshot_date,
            ConcentrationRiskHistory.checksum == row.checksum,
        )
    ).first()
    if existing is not None:
        return False
    session.add(
        ConcentrationRiskHistory(
            owner_user_id=row.owner_user_id,
            portfolio_id=row.portfolio_id,
            concentration_type=row.concentration_type,
            concentration_key=row.concentration_key,
            exposure_status=row.exposure_status,
            concentration_score=row.concentration_score,
            diversification_score=row.diversification_score,
            checksum=row.checksum,
            snapshot_date=row.snapshot_date,
            created_at=utc_now(),
        )
    )
    return True


def _delete_existing_scope_rows(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None,
    snapshot_date: date,
    replay_key: str,
) -> None:
    existing = session.exec(
        select(ConcentrationRiskSnapshot).where(
            ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
            ConcentrationRiskSnapshot.portfolio_id == portfolio_id,
            ConcentrationRiskSnapshot.snapshot_date == snapshot_date,
            ConcentrationRiskSnapshot.replay_key == replay_key,
        )
    ).all()
    for row in existing:
        sid = int(row.id or 0)
        for ev in session.exec(
            select(ConcentrationRiskEvidence).where(ConcentrationRiskEvidence.concentration_risk_snapshot_id == sid)
        ).all():
            session.delete(ev)
        for fac in session.exec(
            select(ConcentrationRiskFactor).where(ConcentrationRiskFactor.concentration_risk_snapshot_id == sid)
        ).all():
            session.delete(fac)
        session.delete(row)
    if existing:
        session.flush()


def generate_concentration_risk(
    session: Session,
    *,
    owner_user_id: int,
    payload: ConcentrationRiskGeneratePayload,
) -> ConcentrationRiskGenerateResponse:
    portfolio_id = payload.portfolio_id
    if portfolio_id is not None:
        _portfolio_for_owner(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    snapshot_date_value = payload.snapshot_date or date.today()
    replay_key = _norm_rk(payload.replay_key) or REPLAY_EMPTY

    existing = session.exec(
        select(ConcentrationRiskSnapshot)
        .where(
            ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
            ConcentrationRiskSnapshot.portfolio_id == portfolio_id,
            ConcentrationRiskSnapshot.snapshot_date == snapshot_date_value,
            ConcentrationRiskSnapshot.replay_key == replay_key,
        )
        .order_by(col(ConcentrationRiskSnapshot.concentration_type).asc(), col(ConcentrationRiskSnapshot.concentration_key).asc())
    ).all()

    facts = _scope_inventory_rows(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    if not facts:
        if existing:
            return ConcentrationRiskGenerateResponse(
                replayed=True,
                items=[_snapshot_read(row) for row in existing],
                total=len(existing),
                history_appended_count=0,
            )
        return ConcentrationRiskGenerateResponse(replayed=False, items=[], total=0, history_appended_count=0)

    alloc_snapshot, liquidity_snapshot, exposure_map = _latest_scope_support(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
    )
    fact_map = {fact.inventory_item_id: fact for fact in facts}
    total_items = len(facts)
    total_fmv = _money(sum((fact.current_fmv or ZERO) for fact in facts))
    total_sales = _money(sum(fact.sale_total for fact in facts))

    buckets: dict[tuple[str, str], list[int]] = {}
    for fact in facts:
        for pair in _bucket_pairs(fact):
            buckets.setdefault(pair, []).append(fact.inventory_item_id)
    for key in list(buckets):
        buckets[key] = sorted(set(buckets[key]))

    row_payloads: list[dict[str, Any]] = []
    for (ctype, ckey), inv_ids in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1])):
        rows = [fact_map[iid] for iid in inv_ids if iid in fact_map]
        category_item_count = len(rows)
        category_fmv = _money(sum((row.current_fmv or ZERO) for row in rows))
        effective_category_fmv = category_fmv if category_fmv > ZERO else _money(sum(row.acquisition_cost for row in rows))
        category_sales = _money(sum(row.sale_total for row in rows))

        if total_fmv > ZERO:
            primary_share_pct = _pct((category_fmv / total_fmv) * HUNDRED)
        else:
            primary_share_pct = _pct((Decimal(category_item_count) / Decimal(total_items)) * HUNDRED)

        low_or_illiquid_fmv = _money(
            sum(
                (row.current_fmv or row.acquisition_cost)
                for row in rows
                if row.liquidity_status_key in {"low", "illiquid", "unknown"}
            )
        )
        if effective_category_fmv > ZERO:
            liquidity_fragility = _score_q((low_or_illiquid_fmv / effective_category_fmv) * HUNDRED)
        else:
            low_count = sum(1 for row in rows if row.liquidity_status_key in {"low", "illiquid", "unknown"})
            liquidity_fragility = _score_q((Decimal(low_count) / Decimal(max(category_item_count, 1))) * HUNDRED)

        duplicate_overlap = _score_q(
            (Decimal(sum(1 for row in rows if row.has_duplicate_overlap)) / Decimal(max(category_item_count, 1))) * HUNDRED
        )
        grading_overlap = _score_q(
            (Decimal(sum(1 for row in rows if row.has_grading_overlap)) / Decimal(max(category_item_count, 1))) * HUNDRED
        )
        if total_sales > ZERO:
            sales_dependence = _score_q((category_sales / total_sales) * HUNDRED)
        else:
            sales_dependence = ZERO
        fmv_dependence = primary_share_pct
        category_fragility = _score_q((liquidity_fragility + duplicate_overlap + grading_overlap) / Decimal("3"))

        if total_fmv > ZERO:
            liquidity_weighted_concentration = _score_q(
                (
                    sum(
                        (row.current_fmv or row.acquisition_cost) * _liquidity_risk_weight(row.liquidity_status_key)
                        for row in rows
                    )
                    / total_fmv
                )
                * HUNDRED
            )
        else:
            liquidity_weighted_concentration = _score_q(
                (
                    sum(_liquidity_risk_weight(row.liquidity_status_key) for row in rows)
                    / Decimal(max(total_items, 1))
                )
                * HUNDRED
            )

        factor_scores = {
            "fmv_dependence": fmv_dependence,
            "liquidity_fragility": liquidity_fragility,
            "duplicate_overlap": duplicate_overlap,
            "grading_overlap": grading_overlap,
            "sales_dependence": sales_dependence,
            "category_fragility": category_fragility,
        }
        concentration_score = _score_q(
            sum(factor_scores[key] * FACTOR_WEIGHTS[key] for key in FACTOR_WEIGHTS)
        )
        diversification_score = _score_q(HUNDRED - concentration_score)
        exposure_status = _classify_status(
            concentration_score=concentration_score,
            primary_share_pct=primary_share_pct,
            liquidity_weighted_concentration=liquidity_weighted_concentration,
        )

        evidence_rows = [
            (
                "PORTFOLIO_REGISTRY",
                exposure_map.get((TYPE_MAP[ctype], ckey)).id if exposure_map.get((TYPE_MAP[ctype], ckey)) else None,
                "portfolio_exposure_snapshot",
                {
                    "category_item_count": category_item_count,
                    "portfolio_total_items": total_items,
                    "category_fmv": category_fmv,
                    "portfolio_total_fmv": total_fmv,
                    "percentage_of_portfolio": primary_share_pct,
                    "inventory_item_ids": inv_ids,
                },
            ),
            (
                "PORTFOLIO_LIQUIDITY",
                int(liquidity_snapshot.id) if liquidity_snapshot is not None else None,
                "portfolio_liquidity_snapshot",
                {
                    "liquidity_balance_status": liquidity_snapshot.liquidity_balance_status if liquidity_snapshot else None,
                    "liquidity_efficiency_score": liquidity_snapshot.liquidity_efficiency_score if liquidity_snapshot else None,
                    "category_low_or_illiquid_fmv": low_or_illiquid_fmv,
                    "liquidity_weighted_concentration": liquidity_weighted_concentration,
                },
            ),
            (
                "DUPLICATE_INTELLIGENCE",
                None,
                "duplicate_consolidation",
                {
                    "duplicate_overlap_count": sum(1 for row in rows if row.has_duplicate_overlap),
                    "duplicate_overlap_pct": duplicate_overlap,
                },
            ),
            (
                "SALES_LEDGER",
                None,
                "sale_record_line_item",
                {
                    "category_sales_total": category_sales,
                    "portfolio_sales_total": total_sales,
                    "sales_dependence": sales_dependence,
                },
            ),
            (
                "LIQUIDITY_ENGINE",
                None,
                "inventory_liquidity_snapshot",
                {
                    "liquidity_distribution": {
                        "high": sum(1 for row in rows if row.liquidity_status_key == "high"),
                        "moderate": sum(1 for row in rows if row.liquidity_status_key == "moderate"),
                        "low": sum(1 for row in rows if row.liquidity_status_key == "low"),
                        "illiquid": sum(1 for row in rows if row.liquidity_status_key == "illiquid"),
                        "unknown": sum(1 for row in rows if row.liquidity_status_key == "unknown"),
                    },
                    "liquidity_fragility": liquidity_fragility,
                },
            ),
            (
                "GRADING_ENGINE",
                None,
                "grading_recommendation",
                {
                    "grading_overlap_count": sum(1 for row in rows if row.has_grading_overlap),
                    "grading_overlap_pct": grading_overlap,
                },
            ),
            (
                "LISTING_INTELLIGENCE",
                None,
                "listing_intelligence_snapshot",
                {
                    "active_listing_count": sum(row.listing_count for row in rows),
                    "stale_listing_count": sum(1 for row in rows if row.listing_stale_flag),
                    "strong_listing_count": sum(1 for row in rows if row.listing_intelligence_status == "STRONG"),
                },
            ),
        ]
        checksum = _hash_payload(
            {
                "portfolio_id": portfolio_id,
                "owner_user_id": owner_user_id,
                "concentration_type": ctype,
                "concentration_key": ckey,
                "inventory_item_ids": inv_ids,
                "total_item_count": category_item_count,
                "total_fmv_amount": category_fmv if category_fmv > ZERO else None,
                "percentage_of_portfolio": primary_share_pct,
                "liquidity_weighted_concentration": liquidity_weighted_concentration,
                "factor_scores": factor_scores,
                "factor_weights": FACTOR_WEIGHTS,
                "concentration_score": concentration_score,
                "diversification_score": diversification_score,
                "exposure_status": exposure_status,
                "snapshot_date": snapshot_date_value,
                "replay_key": replay_key,
            }
        )
        row_payloads.append(
            {
                "concentration_type": ctype,
                "concentration_key": ckey,
                "total_item_count": category_item_count,
                "total_fmv_amount": category_fmv if category_fmv > ZERO else None,
                "percentage_of_portfolio": primary_share_pct,
                "concentration_score": concentration_score,
                "liquidity_weighted_concentration": liquidity_weighted_concentration,
                "exposure_status": exposure_status,
                "diversification_score": diversification_score,
                "checksum": checksum,
                "factor_scores": factor_scores,
                "evidence_rows": evidence_rows,
            }
        )

    if existing:
        existing_by_key = {(row.concentration_type, row.concentration_key): row for row in existing}
        payload_by_key = {(row["concentration_type"], row["concentration_key"]): row for row in row_payloads}
        if set(existing_by_key) == set(payload_by_key) and all(
            str(existing_by_key[key].checksum) == str(payload_by_key[key]["checksum"]) for key in payload_by_key
        ):
            ordered = [existing_by_key[key] for key in sorted(existing_by_key)]
            return ConcentrationRiskGenerateResponse(
                replayed=True,
                items=[_snapshot_read(row) for row in ordered],
                total=len(ordered),
                history_appended_count=0,
            )

    _delete_existing_scope_rows(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date_value,
        replay_key=replay_key,
    )

    saved: list[ConcentrationRiskSnapshot] = []
    history_appended_count = 0
    for payload_row in row_payloads:
        snapshot = ConcentrationRiskSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=portfolio_id,
            concentration_type=payload_row["concentration_type"],
            concentration_key=payload_row["concentration_key"],
            replay_key=replay_key,
            total_item_count=payload_row["total_item_count"],
            total_fmv_amount=payload_row["total_fmv_amount"],
            percentage_of_portfolio=payload_row["percentage_of_portfolio"],
            concentration_score=payload_row["concentration_score"],
            liquidity_weighted_concentration=payload_row["liquidity_weighted_concentration"],
            exposure_status=payload_row["exposure_status"],
            diversification_score=payload_row["diversification_score"],
            checksum=payload_row["checksum"],
            snapshot_date=snapshot_date_value,
            created_at=utc_now(),
        )
        session.add(snapshot)
        session.flush()
        sid = int(snapshot.id or 0)
        for evidence_type, source_id, source_table, evidence_json in payload_row["evidence_rows"]:
            session.add(
                ConcentrationRiskEvidence(
                    concentration_risk_snapshot_id=sid,
                    evidence_type=evidence_type,
                    source_id=source_id,
                    source_table=source_table,
                    evidence_value_json=_json_safe(evidence_json),
                    created_at=utc_now(),
                )
            )
        for factor_key, factor_score in payload_row["factor_scores"].items():
            session.add(
                ConcentrationRiskFactor(
                    concentration_risk_snapshot_id=sid,
                    factor_key=factor_key,
                    factor_score=factor_score,
                    weighting=FACTOR_WEIGHTS[factor_key],
                    created_at=utc_now(),
                )
            )
        history_appended_count += 1 if _append_history(session, snapshot) else 0
        saved.append(snapshot)
    session.commit()
    return ConcentrationRiskGenerateResponse(
        replayed=False,
        items=[_snapshot_read(row) for row in saved],
        total=len(saved),
        history_appended_count=history_appended_count,
    )


def _query_snapshots(
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    concentration_type: str | None = None,
    concentration_key: str | None = None,
    exposure_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(ConcentrationRiskSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.portfolio_id == portfolio_id)
    if concentration_type is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.concentration_type == concentration_type)
    if concentration_key is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.concentration_key == concentration_key)
    if exposure_status is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.exposure_status == exposure_status)
    if date_from is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.snapshot_date <= date_to)
    return stmt


def list_concentration_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    concentration_type: str | None = None,
    concentration_key: str | None = None,
    exposure_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConcentrationRiskListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _query_snapshots(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskSnapshot.snapshot_date).desc(),
            col(ConcentrationRiskSnapshot.concentration_type).asc(),
            col(ConcentrationRiskSnapshot.concentration_key).asc(),
            col(ConcentrationRiskSnapshot.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskListResponse(items=[_snapshot_read(row) for row in rows], total=total)


def list_concentration_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    concentration_type: str | None = None,
    concentration_key: str | None = None,
    exposure_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConcentrationRiskListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _query_snapshots(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskSnapshot.owner_user_id).asc(),
            col(ConcentrationRiskSnapshot.snapshot_date).desc(),
            col(ConcentrationRiskSnapshot.concentration_type).asc(),
            col(ConcentrationRiskSnapshot.concentration_key).asc(),
            col(ConcentrationRiskSnapshot.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskListResponse(items=[_snapshot_read(row) for row in rows], total=total)


def _ensure_owner_snapshot(session: Session, *, owner_user_id: int, snapshot_id: int) -> ConcentrationRiskSnapshot:
    row = session.get(ConcentrationRiskSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concentration risk snapshot not found")
    return row


def _ensure_ops_snapshot(session: Session, *, snapshot_id: int) -> ConcentrationRiskSnapshot:
    row = session.get(ConcentrationRiskSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concentration risk snapshot not found")
    return row


def get_concentration_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> ConcentrationRiskSnapshot:
    return _ensure_owner_snapshot(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)


def get_concentration_ops(session: Session, *, snapshot_id: int) -> ConcentrationRiskSnapshot:
    return _ensure_ops_snapshot(session, snapshot_id=snapshot_id)


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    concentration_risk_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskEvidence).join(
        ConcentrationRiskSnapshot,
        ConcentrationRiskEvidence.concentration_risk_snapshot_id == ConcentrationRiskSnapshot.id,
    ).where(ConcentrationRiskSnapshot.owner_user_id == owner_user_id)
    if concentration_risk_snapshot_id is not None:
        stmt = stmt.where(ConcentrationRiskEvidence.concentration_risk_snapshot_id == concentration_risk_snapshot_id)
    if evidence_type is not None:
        stmt = stmt.where(ConcentrationRiskEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(stmt.order_by(col(ConcentrationRiskEvidence.id).asc()).offset(offset).limit(limit)).all()
    return ConcentrationRiskEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    concentration_risk_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskEvidence).join(
        ConcentrationRiskSnapshot,
        ConcentrationRiskEvidence.concentration_risk_snapshot_id == ConcentrationRiskSnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.owner_user_id == owner_user_id)
    if concentration_risk_snapshot_id is not None:
        stmt = stmt.where(ConcentrationRiskEvidence.concentration_risk_snapshot_id == concentration_risk_snapshot_id)
    if evidence_type is not None:
        stmt = stmt.where(ConcentrationRiskEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskSnapshot.owner_user_id).asc(),
            col(ConcentrationRiskEvidence.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_factors_owner(
    session: Session,
    *,
    owner_user_id: int,
    concentration_risk_snapshot_id: int | None = None,
    factor_key: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskFactorListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskFactor).join(
        ConcentrationRiskSnapshot,
        ConcentrationRiskFactor.concentration_risk_snapshot_id == ConcentrationRiskSnapshot.id,
    ).where(ConcentrationRiskSnapshot.owner_user_id == owner_user_id)
    if concentration_risk_snapshot_id is not None:
        stmt = stmt.where(ConcentrationRiskFactor.concentration_risk_snapshot_id == concentration_risk_snapshot_id)
    if factor_key is not None:
        stmt = stmt.where(ConcentrationRiskFactor.factor_key == factor_key)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(ConcentrationRiskFactor.factor_key).asc(), col(ConcentrationRiskFactor.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskFactorListResponse(items=[_factor_read(row) for row in rows], total=total)


def list_factors_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    concentration_risk_snapshot_id: int | None = None,
    factor_key: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskFactorListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskFactor).join(
        ConcentrationRiskSnapshot,
        ConcentrationRiskFactor.concentration_risk_snapshot_id == ConcentrationRiskSnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(ConcentrationRiskSnapshot.owner_user_id == owner_user_id)
    if concentration_risk_snapshot_id is not None:
        stmt = stmt.where(ConcentrationRiskFactor.concentration_risk_snapshot_id == concentration_risk_snapshot_id)
    if factor_key is not None:
        stmt = stmt.where(ConcentrationRiskFactor.factor_key == factor_key)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskSnapshot.owner_user_id).asc(),
            col(ConcentrationRiskFactor.factor_key).asc(),
            col(ConcentrationRiskFactor.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskFactorListResponse(items=[_factor_read(row) for row in rows], total=total)


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    concentration_type: str | None = None,
    concentration_key: str | None = None,
    exposure_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskHistory).where(ConcentrationRiskHistory.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(ConcentrationRiskHistory.portfolio_id == portfolio_id)
    if concentration_type is not None:
        stmt = stmt.where(ConcentrationRiskHistory.concentration_type == concentration_type)
    if concentration_key is not None:
        stmt = stmt.where(ConcentrationRiskHistory.concentration_key == concentration_key)
    if exposure_status is not None:
        stmt = stmt.where(ConcentrationRiskHistory.exposure_status == exposure_status)
    if date_from is not None:
        stmt = stmt.where(ConcentrationRiskHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ConcentrationRiskHistory.snapshot_date <= date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskHistory.snapshot_date).desc(),
            col(ConcentrationRiskHistory.concentration_type).asc(),
            col(ConcentrationRiskHistory.concentration_key).asc(),
            col(ConcentrationRiskHistory.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    concentration_type: str | None = None,
    concentration_key: str | None = None,
    exposure_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ConcentrationRiskHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(ConcentrationRiskHistory)
    if owner_user_id is not None:
        stmt = stmt.where(ConcentrationRiskHistory.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(ConcentrationRiskHistory.portfolio_id == portfolio_id)
    if concentration_type is not None:
        stmt = stmt.where(ConcentrationRiskHistory.concentration_type == concentration_type)
    if concentration_key is not None:
        stmt = stmt.where(ConcentrationRiskHistory.concentration_key == concentration_key)
    if exposure_status is not None:
        stmt = stmt.where(ConcentrationRiskHistory.exposure_status == exposure_status)
    if date_from is not None:
        stmt = stmt.where(ConcentrationRiskHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ConcentrationRiskHistory.snapshot_date <= date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(ConcentrationRiskHistory.owner_user_id).asc(),
            col(ConcentrationRiskHistory.snapshot_date).desc(),
            col(ConcentrationRiskHistory.concentration_type).asc(),
            col(ConcentrationRiskHistory.concentration_key).asc(),
            col(ConcentrationRiskHistory.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return ConcentrationRiskHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def inventory_concentration_risk_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryConcentrationRiskTeaser | None:
    facts = _scope_inventory_rows(session, owner_user_id=owner_user_id, portfolio_id=None)
    fact = next((row for row in facts if row.inventory_item_id == inventory_item_id), None)
    if fact is None:
        return None
    candidates: list[ConcentrationRiskSnapshot] = []
    for ctype, ckey in _bucket_pairs(fact):
        row = session.exec(
            select(ConcentrationRiskSnapshot)
            .where(
                ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
                ConcentrationRiskSnapshot.portfolio_id.is_(None),
                ConcentrationRiskSnapshot.concentration_type == ctype,
                ConcentrationRiskSnapshot.concentration_key == ckey,
            )
            .order_by(col(ConcentrationRiskSnapshot.snapshot_date).desc(), col(ConcentrationRiskSnapshot.id).desc())
        ).first()
        if row is not None:
            candidates.append(row)
    if not candidates:
        return None
    chosen = sorted(
        candidates,
        key=lambda row: (
            -EXPOSURE_SEVERITY.get(str(row.exposure_status), 0),
            -(row.concentration_score or ZERO),
            int(row.id or 0),
        ),
    )[0]
    return InventoryConcentrationRiskTeaser(
        concentration_type=str(chosen.concentration_type),
        concentration_key=str(chosen.concentration_key),
        exposure_status=str(chosen.exposure_status),
        concentration_score=str(chosen.concentration_score) if chosen.concentration_score is not None else None,
        diversification_score=str(chosen.diversification_score) if chosen.diversification_score is not None else None,
        percentage_of_portfolio=str(chosen.percentage_of_portfolio) if chosen.percentage_of_portfolio is not None else None,
    )
