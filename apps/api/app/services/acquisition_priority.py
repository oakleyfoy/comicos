"""P38-06 deterministic acquisition-priority intelligence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    AcquisitionPriorityEvidence,
    AcquisitionPriorityHistory,
    AcquisitionPriorityScenario,
    AcquisitionPrioritySnapshot,
    ComicIssue,
    ComicTitle,
    ConcentrationRiskSnapshot,
    GradingRecommendation,
    GradingRiskSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    Order,
    OrderItem,
    PortfolioExposureSnapshot,
    PortfolioLiquiditySnapshot,
    PortfolioRecommendation,
    Publisher,
    SaleRecord,
    SaleRecordLineItem,
    Variant,
)
from app.schemas.acquisition_priority import (
    AcquisitionPriorityDetailRead,
    AcquisitionPriorityEvidenceListResponse,
    AcquisitionPriorityEvidenceRead,
    AcquisitionPriorityGeneratePayload,
    AcquisitionPriorityGenerateResponse,
    AcquisitionPriorityHistoryListResponse,
    AcquisitionPriorityHistoryRead,
    AcquisitionPriorityListResponse,
    AcquisitionPriorityScenarioRead,
    AcquisitionPrioritySnapshotRead,
    InventoryAcquisitionPriorityTeaser,
)
from app.services.duplicate_consolidation import inventory_duplicate_teaser

SCOPE_ALL_INVENTORY = "ALL_INVENTORY"
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.01")
REPLAY_EMPTY = ""
PRIORITY_RANK = {"ELITE": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
CATEGORY_RANK = {
    "DIVERSIFICATION": 0,
    "LIQUIDITY_IMPROVEMENT": 1,
    "GRADING_OPPORTUNITY": 2,
    "KEY_ISSUE": 3,
    "PORTFOLIO_GAP": 4,
    "LOW_EXPOSURE_CATEGORY": 5,
    "CONVENTION_STOCK": 6,
    "SALES_VELOCITY": 7,
}
LIQUIDITY_OPPORTUNITY_SCORES = {
    "HIGH": Decimal("88"),
    "MODERATE": Decimal("72"),
    "MEDIUM": Decimal("72"),
    "LOW": Decimal("28"),
    "ILLIQUID": Decimal("10"),
    "UNKNOWN": Decimal("45"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _classify_priority(score: Decimal) -> str:
    if score >= Decimal("80"):
        return "ELITE"
    if score >= Decimal("60"):
        return "HIGH"
    if score >= Decimal("35"):
        return "MEDIUM"
    return "LOW"


def _classify_strength(score: Decimal) -> str:
    if score >= Decimal("85"):
        return "ELITE"
    if score >= Decimal("65"):
        return "STRONG"
    if score >= Decimal("40"):
        return "MODERATE"
    return "WEAK"


def _classify_confidence(score: Decimal) -> str:
    if score >= Decimal("75"):
        return "HIGH"
    if score >= Decimal("50"):
        return "MEDIUM"
    return "LOW"


def _classify_risk(points: int) -> str:
    if points >= 5:
        return "HIGH"
    if points >= 3:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class _IssueMember:
    inventory_item_id: int
    canonical_comic_issue_id: int
    publisher_key: str
    title_key: str
    era_key: str
    acquisition_source_key: str
    acquisition_source_label: str
    current_fmv: Decimal | None
    acquisition_cost: Decimal
    liquidity_status: str | None
    sell_through_rate_pct: Decimal
    stale_listing_rate_pct: Decimal
    listing_intelligence_status: str | None
    listing_stale_risk_flag: bool
    active_listing_count: int
    realized_sales_total: Decimal
    duplicate_bad: bool
    grade_status: str
    grading_action: str | None
    grading_strength: str | None
    grading_risk: str | None
    grading_expected_roi: Decimal | None
    grading_liquidity_adjusted_roi: Decimal | None
    recommendation_action: str | None
    recommendation_strength: str | None
    recommendation_risk: str | None


@dataclass
class _IssueAggregate:
    canonical_comic_issue_id: int
    publisher_key: str
    title_key: str
    era_key: str
    acquisition_source_key: str
    acquisition_source_label: str
    inventory_item_ids: list[int]
    item_count: int
    total_value: Decimal
    duplicate_overlap_count: int
    graded_count: int
    sell_through_rate_avg: Decimal
    stale_listing_rate_avg: Decimal
    active_listing_count: int
    realized_sales_total: Decimal
    best_liquidity_status: str | None
    best_grading_action: str | None
    best_grading_strength: str | None
    best_grading_risk: str | None
    best_grading_expected_roi: Decimal | None
    best_grading_liquidity_adjusted_roi: Decimal | None
    recommendation_actions: list[str]
    market_activity_count: int


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
    for iid, liq_status, sell, stale in rows:
        inv_id = int(iid or 0)
        if inv_id and inv_id not in out:
            out[inv_id] = (str(liq_status) if liq_status is not None else None, _pct(sell), _pct(stale))
    return out


def _latest_listing_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, ListingIntelligenceSnapshot]:
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


def _latest_sales_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, Decimal]:
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
    for iid, amount in rows:
        inv_id = int(iid or 0)
        if inv_id:
            out[inv_id] = out.get(inv_id, ZERO) + _money(amount)
    return out


def _latest_grading_map(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> dict[int, tuple[GradingRecommendation | None, GradingRiskSnapshot | None]]:
    rec_map: dict[int, GradingRecommendation] = {}
    risk_map: dict[int, GradingRiskSnapshot] = {}
    if inv_ids:
        rec_rows = session.exec(
            select(GradingRecommendation)
            .where(
                GradingRecommendation.owner_user_id == owner_user_id,
                col(GradingRecommendation.inventory_item_id).in_(inv_ids),
                col(GradingRecommendation.inventory_item_id).is_not(None),
            )
            .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
        ).all()
        for row in rec_rows:
            iid = int(row.inventory_item_id or 0)
            if iid and iid not in rec_map:
                rec_map[iid] = row
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
    return {iid: (rec_map.get(iid), risk_map.get(iid)) for iid in inv_ids}


def _latest_recommendation_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, PortfolioRecommendation]:
    out: dict[int, PortfolioRecommendation] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(PortfolioRecommendation)
        .where(
            PortfolioRecommendation.owner_user_id == owner_user_id,
            col(PortfolioRecommendation.inventory_item_id).in_(inv_ids),
            col(PortfolioRecommendation.inventory_item_id).is_not(None),
        )
        .order_by(col(PortfolioRecommendation.snapshot_date).desc(), col(PortfolioRecommendation.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_exposure_map(
    session: Session, *, owner_user_id: int, keys: set[tuple[str, str]]
) -> dict[tuple[str, str], PortfolioExposureSnapshot]:
    out: dict[tuple[str, str], PortfolioExposureSnapshot] = {}
    if not keys:
        return out
    rows = session.exec(
        select(PortfolioExposureSnapshot)
        .where(
            PortfolioExposureSnapshot.owner_user_id == owner_user_id,
            PortfolioExposureSnapshot.generation_scope_key == SCOPE_ALL_INVENTORY,
            PortfolioExposureSnapshot.portfolio_id.is_(None),
        )
        .order_by(col(PortfolioExposureSnapshot.created_at).desc(), col(PortfolioExposureSnapshot.id).desc())
    ).all()
    latest_batch = str(rows[0].generation_batch_checksum) if rows else None
    for row in rows:
        if latest_batch and str(row.generation_batch_checksum) != latest_batch:
            continue
        key = (str(row.exposure_type), str(row.exposure_key))
        if key in keys and key not in out:
            out[key] = row
    return out


def _latest_concentration_map(
    session: Session, *, owner_user_id: int, keys: set[tuple[str, str]]
) -> dict[tuple[str, str], ConcentrationRiskSnapshot]:
    out: dict[tuple[str, str], ConcentrationRiskSnapshot] = {}
    if not keys:
        return out
    rows = session.exec(
        select(ConcentrationRiskSnapshot)
        .where(
            ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
            ConcentrationRiskSnapshot.portfolio_id.is_(None),
        )
        .order_by(col(ConcentrationRiskSnapshot.snapshot_date).desc(), col(ConcentrationRiskSnapshot.id).desc())
    ).all()
    for row in rows:
        key = (str(row.concentration_type), str(row.concentration_key))
        if key in keys and key not in out:
            out[key] = row
    return out


def _latest_scope_liquidity(session: Session, *, owner_user_id: int) -> PortfolioLiquiditySnapshot | None:
    return session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == SCOPE_ALL_INVENTORY,
        )
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    ).first()


def _build_issue_members(session: Session, *, owner_user_id: int) -> list[_IssueMember]:
    stmt = (
        select(
            InventoryCopy,
            Order,
            Publisher.name,
            ComicTitle.name,
            ComicIssue.issue_number,
            ComicIssue.id,
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(col(InventoryCopy.id).asc())
    )
    rows = session.exec(stmt).all()
    inv_ids = [int(inv.id or 0) for inv, *_ in rows if int(inv.id or 0)]
    liquidity_map = _latest_liquidity_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_map = _latest_listing_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_counts = _active_listing_count(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    sales_map = _latest_sales_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    grading_map = _latest_grading_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    recommendation_map = _latest_recommendation_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    duplicate_map = {
        inv_id: inventory_duplicate_teaser(session, owner_user_id=owner_user_id, inventory_item_id=inv_id)
        for inv_id in inv_ids
    }

    members: list[_IssueMember] = []
    for inv, order_row, publisher_name, title_name, issue_number, issue_id in rows:
        inventory_item_id = int(inv.id or 0)
        if not inventory_item_id or issue_id is None:
            continue
        liq_status, sell, stale = liquidity_map.get(inventory_item_id, (None, ZERO, ZERO))
        listing = listing_map.get(inventory_item_id)
        grade_rec, grade_risk = grading_map.get(inventory_item_id, (None, None))
        recommendation = recommendation_map.get(inventory_item_id)
        dup = duplicate_map.get(inventory_item_id)
        duplicate_bad = False
        if dup is not None:
            duplicate_bad = (
                getattr(dup, "worst_duplication_status", None) in {"REDUNDANT", "OVEREXPOSED"}
                or getattr(dup, "primary_consolidation_action", None) in {"SELL_DUPLICATES", "REDUCE_EXPOSURE"}
            )
        release_year = inv.release_year
        if release_year is None and inv.release_date is not None:
            release_year = inv.release_date.year
        acquisition_source_label = f"{order_row.source_type or 'unknown'}:{order_row.retailer}"
        members.append(
            _IssueMember(
                inventory_item_id=inventory_item_id,
                canonical_comic_issue_id=int(issue_id),
                publisher_key=_slug(publisher_name),
                title_key=_slug(f"{title_name}::{issue_number}"),
                era_key=_era_bucket(release_year),
                acquisition_source_key=_slug(acquisition_source_label),
                acquisition_source_label=acquisition_source_label.lower(),
                current_fmv=_money(inv.current_fmv) if inv.current_fmv is not None else None,
                acquisition_cost=_money(inv.acquisition_cost),
                liquidity_status=str(liq_status) if liq_status else None,
                sell_through_rate_pct=_pct(sell),
                stale_listing_rate_pct=_pct(stale),
                listing_intelligence_status=str(getattr(listing, "intelligence_status", None) or "") or None,
                listing_stale_risk_flag=bool(getattr(listing, "stale_risk_flag", False)),
                active_listing_count=listing_counts.get(inventory_item_id, 0),
                realized_sales_total=sales_map.get(inventory_item_id, ZERO),
                duplicate_bad=duplicate_bad,
                grade_status=str(inv.grade_status or "unknown").lower(),
                grading_action=str(getattr(grade_rec, "recommended_action", None) or "") or None,
                grading_strength=str(getattr(grade_rec, "recommendation_strength", None) or "") or None,
                grading_risk=str(getattr(grade_risk, "overall_risk_level", None) or getattr(grade_rec, "risk_level", None) or "") or None,
                grading_expected_roi=(
                    _pct(getattr(grade_rec, "expected_roi", None) * HUNDRED)
                    if getattr(grade_rec, "expected_roi", None) is not None
                    else None
                ),
                grading_liquidity_adjusted_roi=(
                    _pct(getattr(grade_rec, "liquidity_adjusted_roi", None) * HUNDRED)
                    if getattr(grade_rec, "liquidity_adjusted_roi", None) is not None
                    else None
                ),
                recommendation_action=str(getattr(recommendation, "recommendation_action", None) or "") or None,
                recommendation_strength=str(getattr(recommendation, "recommendation_strength", None) or "") or None,
                recommendation_risk=str(getattr(recommendation, "risk_level", None) or "") or None,
            )
        )
    return members


def _aggregate_issues(members: list[_IssueMember]) -> list[_IssueAggregate]:
    issue_map: dict[int, list[_IssueMember]] = {}
    for member in members:
        issue_map.setdefault(member.canonical_comic_issue_id, []).append(member)
    aggregates: list[_IssueAggregate] = []
    liq_rank = {"HIGH": 4, "MODERATE": 3, "MEDIUM": 3, "LOW": 2, "ILLIQUID": 1}
    grade_strength_rank = {"ELITE": 4, "STRONG": 3, "MODERATE": 2, "WEAK": 1}
    for issue_id in sorted(issue_map):
        rows = issue_map[issue_id]
        total_value = _money(sum((row.current_fmv or row.acquisition_cost) for row in rows))
        best_liq = max(
            (str(row.liquidity_status or "UNKNOWN").upper() for row in rows),
            key=lambda value: liq_rank.get(value, 0),
        )
        best_grade_row = max(
            rows,
            key=lambda row: (
                grade_strength_rank.get(str(row.grading_strength or "").upper(), 0),
                row.grading_liquidity_adjusted_roi or ZERO,
                row.grading_expected_roi or ZERO,
                -row.stale_listing_rate_pct,
                -row.inventory_item_id,
            ),
        )
        aggregates.append(
            _IssueAggregate(
                canonical_comic_issue_id=issue_id,
                publisher_key=rows[0].publisher_key,
                title_key=rows[0].title_key,
                era_key=rows[0].era_key,
                acquisition_source_key=rows[0].acquisition_source_key,
                acquisition_source_label=rows[0].acquisition_source_label,
                inventory_item_ids=[row.inventory_item_id for row in rows],
                item_count=len(rows),
                total_value=total_value,
                duplicate_overlap_count=sum(1 for row in rows if row.duplicate_bad),
                graded_count=sum(1 for row in rows if row.grade_status != "raw"),
                sell_through_rate_avg=_pct(sum(row.sell_through_rate_pct for row in rows) / Decimal(len(rows))),
                stale_listing_rate_avg=_pct(sum(row.stale_listing_rate_pct for row in rows) / Decimal(len(rows))),
                active_listing_count=sum(row.active_listing_count for row in rows),
                realized_sales_total=_money(sum(row.realized_sales_total for row in rows)),
                best_liquidity_status=best_liq,
                best_grading_action=best_grade_row.grading_action,
                best_grading_strength=best_grade_row.grading_strength,
                best_grading_risk=best_grade_row.grading_risk,
                best_grading_expected_roi=best_grade_row.grading_expected_roi,
                best_grading_liquidity_adjusted_roi=best_grade_row.grading_liquidity_adjusted_roi,
                recommendation_actions=[row.recommendation_action for row in rows if row.recommendation_action],
                market_activity_count=sum(
                    1 for row in rows if row.active_listing_count > 0 or row.realized_sales_total > ZERO
                ),
            )
        )
    return aggregates


def _share_pct(row: PortfolioExposureSnapshot | None) -> Decimal:
    if row is None:
        return Decimal("50")
    return _pct(row.percentage_of_portfolio_value or row.percentage_of_portfolio_count)


def _concentration_score(row: ConcentrationRiskSnapshot | None) -> Decimal:
    if row is None or row.concentration_score is None:
        return Decimal("50")
    return _pct(row.concentration_score)


def _scope_liquidity_need(scope_liquidity: PortfolioLiquiditySnapshot | None, *, total_items: int, low_items: int) -> Decimal:
    if scope_liquidity is not None and total_items > 0:
        low = int(scope_liquidity.low_liquidity_count or 0)
        ill = int(scope_liquidity.illiquid_count or 0)
        return _score_q((Decimal(low + ill) / Decimal(total_items)) * HUNDRED)
    if total_items <= 0:
        return ZERO
    return _score_q((Decimal(low_items) / Decimal(total_items)) * HUNDRED)


def _grading_upside_score(issue: _IssueAggregate) -> Decimal:
    score = Decimal("20")
    action = str(issue.best_grading_action or "").upper()
    strength = str(issue.best_grading_strength or "").upper()
    risk = str(issue.best_grading_risk or "").upper()
    if action == "GRADE":
        score += Decimal("30")
    elif action in {"REVIEW_MANUALLY", "HOLD_RAW"}:
        score += Decimal("8")
    if strength == "ELITE":
        score += Decimal("25")
    elif strength == "STRONG":
        score += Decimal("15")
    elif strength == "MODERATE":
        score += Decimal("8")
    if issue.best_grading_expected_roi is not None:
        if issue.best_grading_expected_roi >= Decimal("75"):
            score += Decimal("20")
        elif issue.best_grading_expected_roi >= Decimal("35"):
            score += Decimal("10")
    if issue.best_grading_liquidity_adjusted_roi is not None:
        if issue.best_grading_liquidity_adjusted_roi >= Decimal("75"):
            score += Decimal("10")
        elif issue.best_grading_liquidity_adjusted_roi >= Decimal("35"):
            score += Decimal("5")
    if risk == "HIGH":
        score -= Decimal("20")
    elif risk == "MEDIUM":
        score -= Decimal("10")
    return _score_q(score)


def _liquidity_impact(issue: _IssueAggregate, *, scope_need: Decimal) -> Decimal:
    liq_score = LIQUIDITY_OPPORTUNITY_SCORES.get(str(issue.best_liquidity_status or "UNKNOWN").upper(), Decimal("45"))
    score = liq_score
    if issue.sell_through_rate_avg >= Decimal("40"):
        score += Decimal("8")
    elif issue.sell_through_rate_avg < Decimal("18"):
        score -= Decimal("10")
    if issue.stale_listing_rate_avg >= Decimal("70"):
        score -= Decimal("12")
    if issue.realized_sales_total > ZERO:
        score += Decimal("8")
    return _score_q((score + scope_need) / Decimal("2"))


def _sales_velocity_score(issue: _IssueAggregate) -> Decimal:
    score = issue.sell_through_rate_avg * Decimal("1.4")
    if issue.realized_sales_total > ZERO:
        score += Decimal("20")
    if issue.active_listing_count > 0:
        score += Decimal("10")
    if issue.stale_listing_rate_avg >= Decimal("70"):
        score -= Decimal("20")
    return _score_q(score)


def _duplication_risk(issue: _IssueAggregate) -> Decimal:
    base = _score_q((Decimal(issue.duplicate_overlap_count) / Decimal(max(issue.item_count, 1))) * HUNDRED)
    if issue.item_count > 1:
        base += Decimal("20")
    if any(action in {"SELL", "CONSOLIDATE", "REDUCE_EXPOSURE"} for action in issue.recommendation_actions):
        base += Decimal("20")
    return _score_q(base)


def _classify_category(
    *,
    issue: _IssueAggregate,
    diversification_impact: Decimal,
    liquidity_impact: Decimal,
    grading_upside_score: Decimal,
    concentration_reduction_score: Decimal,
    sales_velocity_score: Decimal,
    duplication_risk: Decimal,
) -> str:
    src = issue.acquisition_source_label
    if any(token in src for token in ("convention", "show", "booth", "vendor")) and liquidity_impact >= Decimal("60"):
        return "CONVENTION_STOCK"
    if grading_upside_score >= Decimal("75") and duplication_risk < Decimal("60"):
        return "GRADING_OPPORTUNITY"
    if diversification_impact >= Decimal("80") and concentration_reduction_score >= Decimal("60"):
        return "DIVERSIFICATION"
    if liquidity_impact >= Decimal("75"):
        return "LIQUIDITY_IMPROVEMENT"
    if sales_velocity_score >= Decimal("75") and liquidity_impact >= Decimal("60"):
        return "SALES_VELOCITY"
    if diversification_impact >= Decimal("68") and concentration_reduction_score >= Decimal("55"):
        return "LOW_EXPOSURE_CATEGORY"
    if issue.total_value >= Decimal("100") and duplication_risk < Decimal("50"):
        return "KEY_ISSUE"
    return "PORTFOLIO_GAP"


def _snapshot_read(row: AcquisitionPrioritySnapshot) -> AcquisitionPrioritySnapshotRead:
    return AcquisitionPrioritySnapshotRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        canonical_comic_issue_id=row.canonical_comic_issue_id,
        acquisition_category=str(row.acquisition_category),
        acquisition_priority=str(row.acquisition_priority),
        portfolio_impact_score=row.portfolio_impact_score,
        diversification_impact=row.diversification_impact,
        liquidity_impact=row.liquidity_impact,
        grading_upside_score=row.grading_upside_score,
        duplication_risk=row.duplication_risk,
        concentration_reduction_score=row.concentration_reduction_score,
        estimated_capital_efficiency=row.estimated_capital_efficiency,
        recommendation_strength=str(row.recommendation_strength),
        confidence_level=str(row.confidence_level),
        risk_level=str(row.risk_level),
        rationale_summary=str(row.rationale_summary),
        warning_flags_json=list(row.warning_flags_json or []),
        checksum=str(row.checksum),
        replay_key=str(row.replay_key),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _evidence_read(row: AcquisitionPriorityEvidence) -> AcquisitionPriorityEvidenceRead:
    return AcquisitionPriorityEvidenceRead(
        id=int(row.id or 0),
        acquisition_priority_snapshot_id=int(row.acquisition_priority_snapshot_id),
        evidence_type=str(row.evidence_type),
        source_id=row.source_id,
        source_table=row.source_table,
        evidence_value_json=dict(row.evidence_value_json or {}),
        created_at=row.created_at,
    )


def _scenario_read(row: AcquisitionPriorityScenario) -> AcquisitionPriorityScenarioRead:
    return AcquisitionPriorityScenarioRead(
        id=int(row.id or 0),
        acquisition_priority_snapshot_id=int(row.acquisition_priority_snapshot_id),
        scenario_name=str(row.scenario_name),
        projected_liquidity_impact=row.projected_liquidity_impact,
        projected_diversification_impact=row.projected_diversification_impact,
        projected_portfolio_efficiency=row.projected_portfolio_efficiency,
        created_at=row.created_at,
    )


def _history_read(row: AcquisitionPriorityHistory) -> AcquisitionPriorityHistoryRead:
    return AcquisitionPriorityHistoryRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        canonical_comic_issue_id=row.canonical_comic_issue_id,
        acquisition_category=str(row.acquisition_category),
        acquisition_priority=str(row.acquisition_priority),
        recommendation_strength=str(row.recommendation_strength),
        confidence_level=str(row.confidence_level),
        risk_level=str(row.risk_level),
        checksum=str(row.checksum),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _detail_read(session: Session, row: AcquisitionPrioritySnapshot) -> AcquisitionPriorityDetailRead:
    sid = int(row.id or 0)
    evidence = session.exec(
        select(AcquisitionPriorityEvidence)
        .where(AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == sid)
        .order_by(col(AcquisitionPriorityEvidence.id).asc())
    ).all()
    scenarios = session.exec(
        select(AcquisitionPriorityScenario)
        .where(AcquisitionPriorityScenario.acquisition_priority_snapshot_id == sid)
        .order_by(col(AcquisitionPriorityScenario.scenario_name).asc(), col(AcquisitionPriorityScenario.id).asc())
    ).all()
    history = session.exec(
        select(AcquisitionPriorityHistory)
        .where(
            AcquisitionPriorityHistory.owner_user_id == row.owner_user_id,
            AcquisitionPriorityHistory.canonical_comic_issue_id == row.canonical_comic_issue_id,
            AcquisitionPriorityHistory.acquisition_category == row.acquisition_category,
        )
        .order_by(col(AcquisitionPriorityHistory.snapshot_date).desc(), col(AcquisitionPriorityHistory.id).desc())
    ).all()
    return AcquisitionPriorityDetailRead(
        snapshot=_snapshot_read(row),
        evidence=[_evidence_read(item) for item in evidence],
        scenarios=[_scenario_read(item) for item in scenarios],
        history=[_history_read(item) for item in history],
    )


def _append_history(session: Session, row: AcquisitionPrioritySnapshot) -> bool:
    existing = session.exec(
        select(AcquisitionPriorityHistory).where(
            AcquisitionPriorityHistory.owner_user_id == row.owner_user_id,
            AcquisitionPriorityHistory.canonical_comic_issue_id == row.canonical_comic_issue_id,
            AcquisitionPriorityHistory.acquisition_category == row.acquisition_category,
            AcquisitionPriorityHistory.snapshot_date == row.snapshot_date,
            AcquisitionPriorityHistory.checksum == row.checksum,
        )
    ).first()
    if existing is not None:
        return False
    session.add(
        AcquisitionPriorityHistory(
            owner_user_id=row.owner_user_id,
            canonical_comic_issue_id=row.canonical_comic_issue_id,
            acquisition_category=row.acquisition_category,
            acquisition_priority=row.acquisition_priority,
            recommendation_strength=row.recommendation_strength,
            confidence_level=row.confidence_level,
            risk_level=row.risk_level,
            checksum=row.checksum,
            snapshot_date=row.snapshot_date,
            created_at=utc_now(),
        )
    )
    return True


def _delete_existing(session: Session, *, owner_user_id: int, snapshot_date: date, replay_key: str) -> None:
    existing = session.exec(
        select(AcquisitionPrioritySnapshot).where(
            AcquisitionPrioritySnapshot.owner_user_id == owner_user_id,
            AcquisitionPrioritySnapshot.snapshot_date == snapshot_date,
            AcquisitionPrioritySnapshot.replay_key == replay_key,
        )
    ).all()
    for row in existing:
        sid = int(row.id or 0)
        for ev in session.exec(
            select(AcquisitionPriorityEvidence).where(AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == sid)
        ).all():
            session.delete(ev)
        for sc in session.exec(
            select(AcquisitionPriorityScenario).where(AcquisitionPriorityScenario.acquisition_priority_snapshot_id == sid)
        ).all():
            session.delete(sc)
        session.delete(row)
    if existing:
        session.flush()


def generate_acquisition_priorities(
    session: Session,
    *,
    owner_user_id: int,
    payload: AcquisitionPriorityGeneratePayload,
) -> AcquisitionPriorityGenerateResponse:
    snapshot_date_value = payload.snapshot_date or date.today()
    replay_key = _norm_rk(payload.replay_key) or REPLAY_EMPTY
    existing = session.exec(
        select(AcquisitionPrioritySnapshot)
        .where(
            AcquisitionPrioritySnapshot.owner_user_id == owner_user_id,
            AcquisitionPrioritySnapshot.snapshot_date == snapshot_date_value,
            AcquisitionPrioritySnapshot.replay_key == replay_key,
        )
        .order_by(
            col(AcquisitionPrioritySnapshot.acquisition_category).asc(),
            col(AcquisitionPrioritySnapshot.canonical_comic_issue_id).asc().nullsfirst(),
            col(AcquisitionPrioritySnapshot.id).asc(),
        )
    ).all()

    members = _build_issue_members(session, owner_user_id=owner_user_id)
    if not members:
        if existing:
            return AcquisitionPriorityGenerateResponse(
                replayed=True,
                items=[_snapshot_read(row) for row in existing],
                total=len(existing),
                history_appended_count=0,
            )
        return AcquisitionPriorityGenerateResponse(replayed=False, items=[], total=0, history_appended_count=0)

    issues = _aggregate_issues(members)
    total_items = len(members)
    low_items = sum(1 for item in members if str(item.liquidity_status or "").upper() in {"LOW", "ILLIQUID"})
    scope_liquidity = _latest_scope_liquidity(session, owner_user_id=owner_user_id)
    scope_need = _scope_liquidity_need(scope_liquidity, total_items=total_items, low_items=low_items)

    dim_keys: set[tuple[str, str]] = set()
    for issue in issues:
        dim_keys.update(
            {
                ("publisher", issue.publisher_key),
                ("title", issue.title_key),
                ("era", issue.era_key),
                ("acquisition_source", issue.acquisition_source_key),
            }
        )
    exposure_map = _latest_exposure_map(session, owner_user_id=owner_user_id, keys=dim_keys)
    concentration_map = _latest_concentration_map(session, owner_user_id=owner_user_id, keys=dim_keys)

    row_payloads: list[dict[str, Any]] = []
    for issue in issues:
        publisher_exp = exposure_map.get(("publisher", issue.publisher_key))
        title_exp = exposure_map.get(("title", issue.title_key))
        era_exp = exposure_map.get(("era", issue.era_key))
        acq_exp = exposure_map.get(("acquisition_source", issue.acquisition_source_key))
        publisher_conc = concentration_map.get(("publisher", issue.publisher_key))
        title_conc = concentration_map.get(("title", issue.title_key))
        era_conc = concentration_map.get(("era", issue.era_key))

        diversification_impact = _score_q(
            (
                (HUNDRED - _share_pct(publisher_exp))
                + (HUNDRED - _share_pct(title_exp))
                + (HUNDRED - _share_pct(era_exp))
                + (HUNDRED - _share_pct(acq_exp))
            )
            / Decimal("4")
        )
        concentration_reduction_score = _score_q(
            (
                (HUNDRED - _concentration_score(publisher_conc))
                + (HUNDRED - _concentration_score(title_conc))
                + (HUNDRED - _concentration_score(era_conc))
            )
            / Decimal("3")
        )
        grading_upside_score = _grading_upside_score(issue)
        liquidity_impact = _liquidity_impact(issue, scope_need=scope_need)
        duplication_risk = _duplication_risk(issue)
        sales_velocity_score = _sales_velocity_score(issue)
        estimated_capital_efficiency = _score_q(
            ((liquidity_impact + grading_upside_score + sales_velocity_score) / Decimal("3"))
            - (duplication_risk * Decimal("0.25"))
        )
        portfolio_impact_score = _score_q(
            (diversification_impact * Decimal("0.28"))
            + (liquidity_impact * Decimal("0.22"))
            + (grading_upside_score * Decimal("0.18"))
            + (concentration_reduction_score * Decimal("0.20"))
            + (estimated_capital_efficiency * Decimal("0.12"))
            - (duplication_risk * Decimal("0.20"))
        )
        acquisition_category = _classify_category(
            issue=issue,
            diversification_impact=diversification_impact,
            liquidity_impact=liquidity_impact,
            grading_upside_score=grading_upside_score,
            concentration_reduction_score=concentration_reduction_score,
            sales_velocity_score=sales_velocity_score,
            duplication_risk=duplication_risk,
        )
        acquisition_priority = _classify_priority(portfolio_impact_score)
        recommendation_strength = _classify_strength(portfolio_impact_score)

        confidence_score = Decimal("25")
        warning_flags: list[str] = []
        if publisher_exp or title_exp or era_exp:
            confidence_score += Decimal("10")
        else:
            warning_flags.append("missing_exposure_support")
        if publisher_conc or title_conc or era_conc:
            confidence_score += Decimal("10")
        else:
            warning_flags.append("missing_concentration_support")
        if scope_liquidity is not None:
            confidence_score += Decimal("8")
        if issue.best_liquidity_status:
            confidence_score += Decimal("10")
        else:
            warning_flags.append("missing_liquidity_snapshot")
        if issue.realized_sales_total > ZERO:
            confidence_score += Decimal("8")
        else:
            warning_flags.append("no_realized_sales")
        if issue.active_listing_count > 0:
            confidence_score += Decimal("5")
        else:
            warning_flags.append("no_active_listing")
        if issue.best_grading_action:
            confidence_score += Decimal("8")
        if issue.recommendation_actions:
            confidence_score += Decimal("5")
        if issue.stale_listing_rate_avg >= Decimal("70"):
            confidence_score -= Decimal("8")
            warning_flags.append("listing_stale")
        confidence_level = _classify_confidence(_score_q(confidence_score))

        risk_points = 0
        if str(issue.best_liquidity_status or "").upper() in {"LOW", "ILLIQUID"}:
            risk_points += 2
            warning_flags.append("liquidity_weak")
        if issue.sell_through_rate_avg < Decimal("18"):
            risk_points += 1
            warning_flags.append("sell_through_weak")
        if issue.stale_listing_rate_avg >= Decimal("70"):
            risk_points += 1
        if duplication_risk >= Decimal("60"):
            risk_points += 2
            warning_flags.append("duplicate_overlap_high")
        if concentration_reduction_score < Decimal("30"):
            risk_points += 1
            warning_flags.append("concentration_reduction_limited")
        if issue.market_activity_count == 0:
            risk_points += 1
            warning_flags.append("market_activity_thin")
        risk_level = _classify_risk(risk_points)

        rationale_summary = (
            f"{acquisition_category.title().replace('_', ' ')} candidate for issue #{issue.canonical_comic_issue_id}: "
            f"diversification {diversification_impact}, liquidity {liquidity_impact}, "
            f"concentration reduction {concentration_reduction_score}, grading upside {grading_upside_score}."
        )[:600]

        checksum = _hash_payload(
            {
                "owner_user_id": owner_user_id,
                "canonical_comic_issue_id": issue.canonical_comic_issue_id,
                "acquisition_category": acquisition_category,
                "acquisition_priority": acquisition_priority,
                "portfolio_impact_score": portfolio_impact_score,
                "diversification_impact": diversification_impact,
                "liquidity_impact": liquidity_impact,
                "grading_upside_score": grading_upside_score,
                "duplication_risk": duplication_risk,
                "concentration_reduction_score": concentration_reduction_score,
                "estimated_capital_efficiency": estimated_capital_efficiency,
                "recommendation_strength": recommendation_strength,
                "confidence_level": confidence_level,
                "risk_level": risk_level,
                "warning_flags_json": warning_flags,
                "snapshot_date": snapshot_date_value,
                "replay_key": replay_key,
            }
        )

        evidence_rows = [
            (
                "PORTFOLIO_EXPOSURE",
                int(publisher_exp.id) if publisher_exp is not None else None,
                "portfolio_exposure_snapshot",
                {
                    "publisher_share_pct": _share_pct(publisher_exp),
                    "title_share_pct": _share_pct(title_exp),
                    "era_share_pct": _share_pct(era_exp),
                    "acquisition_source_share_pct": _share_pct(acq_exp),
                },
            ),
            (
                "CONCENTRATION_RISK",
                int(publisher_conc.id) if publisher_conc is not None else None,
                "concentration_risk_snapshot",
                {
                    "publisher_concentration_score": _concentration_score(publisher_conc),
                    "title_concentration_score": _concentration_score(title_conc),
                    "era_concentration_score": _concentration_score(era_conc),
                    "concentration_reduction_score": concentration_reduction_score,
                },
            ),
            (
                "DUPLICATE_INTELLIGENCE",
                None,
                "duplicate_consolidation",
                {
                    "inventory_item_ids": issue.inventory_item_ids,
                    "duplicate_overlap_count": issue.duplicate_overlap_count,
                    "duplication_risk": duplication_risk,
                },
            ),
            (
                "PORTFOLIO_LIQUIDITY",
                int(scope_liquidity.id) if scope_liquidity is not None else None,
                "portfolio_liquidity_snapshot",
                {
                    "scope_need_score": scope_need,
                    "liquidity_balance_status": scope_liquidity.liquidity_balance_status if scope_liquidity else None,
                    "liquidity_impact": liquidity_impact,
                },
            ),
            (
                "GRADING_RECOMMENDATION",
                None,
                "grading_recommendation",
                {
                    "grading_action": issue.best_grading_action,
                    "grading_strength": issue.best_grading_strength,
                    "grading_risk": issue.best_grading_risk,
                    "grading_upside_score": grading_upside_score,
                },
            ),
            (
                "SALES_LEDGER",
                None,
                "sale_record_line_item",
                {
                    "realized_sales_total": issue.realized_sales_total,
                    "sell_through_rate_avg": issue.sell_through_rate_avg,
                    "sales_velocity_score": sales_velocity_score,
                },
            ),
            (
                "LISTING_INTELLIGENCE",
                None,
                "listing_intelligence_snapshot",
                {
                    "active_listing_count": issue.active_listing_count,
                    "stale_listing_rate_avg": issue.stale_listing_rate_avg,
                    "estimated_capital_efficiency": estimated_capital_efficiency,
                },
            ),
        ]

        row_payloads.append(
            {
                "canonical_comic_issue_id": issue.canonical_comic_issue_id,
                "acquisition_category": acquisition_category,
                "acquisition_priority": acquisition_priority,
                "portfolio_impact_score": portfolio_impact_score,
                "diversification_impact": diversification_impact,
                "liquidity_impact": liquidity_impact,
                "grading_upside_score": grading_upside_score,
                "duplication_risk": duplication_risk,
                "concentration_reduction_score": concentration_reduction_score,
                "estimated_capital_efficiency": estimated_capital_efficiency,
                "recommendation_strength": recommendation_strength,
                "confidence_level": confidence_level,
                "risk_level": risk_level,
                "rationale_summary": rationale_summary,
                "warning_flags_json": warning_flags,
                "checksum": checksum,
                "evidence_rows": evidence_rows,
                "scenario_rows": {
                    "pessimistic": Decimal("0.85"),
                    "baseline": Decimal("1.00"),
                    "optimistic": Decimal("1.15"),
                },
            }
        )

    row_payloads.sort(
        key=lambda row: (
            CATEGORY_RANK.get(str(row["acquisition_category"]), 99),
            PRIORITY_RANK.get(str(row["acquisition_priority"]), 99),
            -(row["portfolio_impact_score"] or ZERO),
            int(row["canonical_comic_issue_id"] or 0),
        )
    )

    if existing:
        existing_by_key = {
            (row.canonical_comic_issue_id, row.acquisition_category): row
            for row in existing
        }
        payload_by_key = {
            (row["canonical_comic_issue_id"], row["acquisition_category"]): row
            for row in row_payloads
        }
        if set(existing_by_key) == set(payload_by_key) and all(
            str(existing_by_key[key].checksum) == str(payload_by_key[key]["checksum"]) for key in payload_by_key
        ):
            ordered = [existing_by_key[key] for key in sorted(existing_by_key, key=lambda item: (str(item[1]), int(item[0] or 0)))]
            return AcquisitionPriorityGenerateResponse(
                replayed=True,
                items=[_snapshot_read(row) for row in ordered],
                total=len(ordered),
                history_appended_count=0,
            )

    _delete_existing(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date_value, replay_key=replay_key)

    saved: list[AcquisitionPrioritySnapshot] = []
    history_appended_count = 0
    for payload_row in row_payloads:
        snapshot = AcquisitionPrioritySnapshot(
            owner_user_id=owner_user_id,
            canonical_comic_issue_id=payload_row["canonical_comic_issue_id"],
            acquisition_category=payload_row["acquisition_category"],
            acquisition_priority=payload_row["acquisition_priority"],
            replay_key=replay_key,
            portfolio_impact_score=payload_row["portfolio_impact_score"],
            diversification_impact=payload_row["diversification_impact"],
            liquidity_impact=payload_row["liquidity_impact"],
            grading_upside_score=payload_row["grading_upside_score"],
            duplication_risk=payload_row["duplication_risk"],
            concentration_reduction_score=payload_row["concentration_reduction_score"],
            estimated_capital_efficiency=payload_row["estimated_capital_efficiency"],
            recommendation_strength=payload_row["recommendation_strength"],
            confidence_level=payload_row["confidence_level"],
            risk_level=payload_row["risk_level"],
            rationale_summary=payload_row["rationale_summary"],
            warning_flags_json=_json_safe(payload_row["warning_flags_json"]),
            checksum=payload_row["checksum"],
            snapshot_date=snapshot_date_value,
            created_at=utc_now(),
        )
        session.add(snapshot)
        session.flush()
        sid = int(snapshot.id or 0)
        for evidence_type, source_id, source_table, evidence_value_json in payload_row["evidence_rows"]:
            session.add(
                AcquisitionPriorityEvidence(
                    acquisition_priority_snapshot_id=sid,
                    evidence_type=evidence_type,
                    source_id=source_id,
                    source_table=source_table,
                    evidence_value_json=_json_safe(evidence_value_json),
                    created_at=utc_now(),
                )
            )
        for scenario_name, factor in payload_row["scenario_rows"].items():
            session.add(
                AcquisitionPriorityScenario(
                    acquisition_priority_snapshot_id=sid,
                    scenario_name=scenario_name,
                    projected_liquidity_impact=_score_q(payload_row["liquidity_impact"] * factor),
                    projected_diversification_impact=_score_q(payload_row["diversification_impact"] * factor),
                    projected_portfolio_efficiency=_score_q(payload_row["estimated_capital_efficiency"] * factor),
                    created_at=utc_now(),
                )
            )
        history_appended_count += 1 if _append_history(session, snapshot) else 0
        saved.append(snapshot)
    session.commit()
    return AcquisitionPriorityGenerateResponse(
        replayed=False,
        items=[_snapshot_read(row) for row in saved],
        total=len(saved),
        history_appended_count=history_appended_count,
    )


def _query_snapshots(
    *,
    owner_user_id: int | None = None,
    acquisition_category: str | None = None,
    acquisition_priority: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(AcquisitionPrioritySnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.owner_user_id == owner_user_id)
    if acquisition_category is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.acquisition_category == acquisition_category)
    if acquisition_priority is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.acquisition_priority == acquisition_priority)
    if recommendation_strength is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.recommendation_strength == recommendation_strength)
    if confidence_level is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.risk_level == risk_level)
    if date_from is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.snapshot_date <= date_to)
    return stmt


def list_priorities_owner(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_category: str | None = None,
    acquisition_priority: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AcquisitionPriorityListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _query_snapshots(
        owner_user_id=owner_user_id,
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(AcquisitionPrioritySnapshot.snapshot_date).desc(),
            col(AcquisitionPrioritySnapshot.acquisition_category).asc(),
            col(AcquisitionPrioritySnapshot.acquisition_priority).asc(),
            col(AcquisitionPrioritySnapshot.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return AcquisitionPriorityListResponse(items=[_snapshot_read(row) for row in rows], total=total)


def list_priorities_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    acquisition_category: str | None = None,
    acquisition_priority: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AcquisitionPriorityListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _query_snapshots(
        owner_user_id=owner_user_id,
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(AcquisitionPrioritySnapshot.owner_user_id).asc(),
            col(AcquisitionPrioritySnapshot.snapshot_date).desc(),
            col(AcquisitionPrioritySnapshot.acquisition_category).asc(),
            col(AcquisitionPrioritySnapshot.acquisition_priority).asc(),
            col(AcquisitionPrioritySnapshot.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return AcquisitionPriorityListResponse(items=[_snapshot_read(row) for row in rows], total=total)


def _ensure_owner_snapshot(session: Session, *, owner_user_id: int, snapshot_id: int) -> AcquisitionPrioritySnapshot:
    row = session.get(AcquisitionPrioritySnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition priority snapshot not found")
    return row


def _ensure_ops_snapshot(session: Session, *, snapshot_id: int) -> AcquisitionPrioritySnapshot:
    row = session.get(AcquisitionPrioritySnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acquisition priority snapshot not found")
    return row


def get_priority_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> AcquisitionPrioritySnapshot:
    return _ensure_owner_snapshot(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)


def get_priority_ops(session: Session, *, snapshot_id: int) -> AcquisitionPrioritySnapshot:
    return _ensure_ops_snapshot(session, snapshot_id=snapshot_id)


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_priority_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AcquisitionPriorityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(AcquisitionPriorityEvidence).join(
        AcquisitionPrioritySnapshot,
        AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == AcquisitionPrioritySnapshot.id,
    ).where(AcquisitionPrioritySnapshot.owner_user_id == owner_user_id)
    if acquisition_priority_snapshot_id is not None:
        stmt = stmt.where(AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == acquisition_priority_snapshot_id)
    if evidence_type is not None:
        stmt = stmt.where(AcquisitionPriorityEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(stmt.order_by(col(AcquisitionPriorityEvidence.id).asc()).offset(offset).limit(limit)).all()
    return AcquisitionPriorityEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    acquisition_priority_snapshot_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AcquisitionPriorityEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(AcquisitionPriorityEvidence).join(
        AcquisitionPrioritySnapshot,
        AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == AcquisitionPrioritySnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(AcquisitionPrioritySnapshot.owner_user_id == owner_user_id)
    if acquisition_priority_snapshot_id is not None:
        stmt = stmt.where(AcquisitionPriorityEvidence.acquisition_priority_snapshot_id == acquisition_priority_snapshot_id)
    if evidence_type is not None:
        stmt = stmt.where(AcquisitionPriorityEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(AcquisitionPrioritySnapshot.owner_user_id).asc(), col(AcquisitionPriorityEvidence.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AcquisitionPriorityEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_category: str | None = None,
    acquisition_priority: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AcquisitionPriorityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(AcquisitionPriorityHistory).where(AcquisitionPriorityHistory.owner_user_id == owner_user_id)
    if acquisition_category is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.acquisition_category == acquisition_category)
    if acquisition_priority is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.acquisition_priority == acquisition_priority)
    if recommendation_strength is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.recommendation_strength == recommendation_strength)
    if confidence_level is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.risk_level == risk_level)
    if date_from is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.snapshot_date <= date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(AcquisitionPriorityHistory.snapshot_date).desc(),
            col(AcquisitionPriorityHistory.acquisition_category).asc(),
            col(AcquisitionPriorityHistory.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return AcquisitionPriorityHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    acquisition_category: str | None = None,
    acquisition_priority: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AcquisitionPriorityHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(AcquisitionPriorityHistory)
    if owner_user_id is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.owner_user_id == owner_user_id)
    if acquisition_category is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.acquisition_category == acquisition_category)
    if acquisition_priority is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.acquisition_priority == acquisition_priority)
    if recommendation_strength is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.recommendation_strength == recommendation_strength)
    if confidence_level is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.risk_level == risk_level)
    if date_from is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AcquisitionPriorityHistory.snapshot_date <= date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(AcquisitionPriorityHistory.owner_user_id).asc(),
            col(AcquisitionPriorityHistory.snapshot_date).desc(),
            col(AcquisitionPriorityHistory.acquisition_category).asc(),
            col(AcquisitionPriorityHistory.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return AcquisitionPriorityHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def inventory_acquisition_priority_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryAcquisitionPriorityTeaser | None:
    issue_id = session.exec(
        select(ComicIssue.id)
        .join(Variant, Variant.comic_issue_id == ComicIssue.id)
        .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
        .where(
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.id == inventory_item_id,
        )
    ).first()
    if issue_id is None:
        return None
    row = session.exec(
        select(AcquisitionPrioritySnapshot)
        .where(
            AcquisitionPrioritySnapshot.owner_user_id == owner_user_id,
            AcquisitionPrioritySnapshot.canonical_comic_issue_id == int(issue_id),
        )
        .order_by(col(AcquisitionPrioritySnapshot.snapshot_date).desc(), col(AcquisitionPrioritySnapshot.id).desc())
    ).first()
    if row is None:
        return None
    return InventoryAcquisitionPriorityTeaser(
        acquisition_category=str(row.acquisition_category),
        acquisition_priority=str(row.acquisition_priority),
        recommendation_strength=str(row.recommendation_strength),
        rationale_summary=str(row.rationale_summary),
        diversification_impact=str(row.diversification_impact) if row.diversification_impact is not None else None,
        liquidity_impact=str(row.liquidity_impact) if row.liquidity_impact is not None else None,
        duplication_risk=str(row.duplication_risk) if row.duplication_risk is not None else None,
    )
