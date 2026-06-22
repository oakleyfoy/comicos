"""P38-04 deterministic portfolio hold / sell recommendation engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, literal
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    GradingRecommendation,
    GradingRiskSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    MarketSaleRecord,
    Portfolio,
    PortfolioAllocationSnapshot,
    PortfolioExposureSnapshot,
    PortfolioItem,
    PortfolioRecommendation,
    PortfolioRecommendationEvidence,
    PortfolioRecommendationHistory,
    PortfolioRecommendationScenario,
    PortfolioLiquiditySnapshot,
    SaleRecord,
    SaleRecordLineItem,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.portfolio_recommendation import (
    InventoryPortfolioRecommendationTeaser,
    PortfolioRecommendationDetailRead,
    PortfolioRecommendationEvidenceListResponse,
    PortfolioRecommendationEvidenceRead,
    PortfolioRecommendationGeneratePayload,
    PortfolioRecommendationGenerateResponse,
    PortfolioRecommendationHistoryListResponse,
    PortfolioRecommendationHistoryRead,
    PortfolioRecommendationListResponse,
    PortfolioRecommendationRead,
    PortfolioRecommendationScenarioRead,
)
from app.services.duplicate_consolidation import inventory_duplicate_teaser

SCOPE_ALL_INVENTORY = "ALL_INVENTORY"
MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
DEC_100 = Decimal("100")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def scope_key(portfolio_id: int | None) -> str:
    return SCOPE_ALL_INVENTORY if portfolio_id is None else f"PORTFOLIO_{int(portfolio_id)}"


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
    return "".join(out).strip("-")


def _score_q(value: Decimal) -> Decimal:
    return min(DEC_100, max(ZERO, value)).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class _ItemFact:
    inventory_item_id: int
    portfolio_id: int | None
    canonical_comic_issue_id: int
    current_fmv: Decimal | None
    acquisition_cost: Decimal
    publisher_key: str
    title_key: str
    engine_status: str | None
    sell_through_rate_pct: Decimal
    stale_listing_rate_pct: Decimal
    grading_action: str | None
    grading_strength: str | None
    grading_confidence: str | None
    grading_risk: str | None
    grading_expected_roi: Decimal | None
    grading_liquidity_adjusted_roi: Decimal | None
    grading_rationale: str | None
    listing_intelligence_status: str | None
    listing_stale_risk_flag: bool
    exposure_status: str | None
    exposure_pct_value: Decimal | None
    duplicate_status: str | None
    duplicate_action: str | None
    duplicate_teaser: str | None
    portfolio_liquidity_bucket: str
    portfolio_liquidity_snapshot_id: int | None


def _scope_inventory_rows(session: Session, *, owner_user_id: int, portfolio_id: int | None) -> list[_ItemFact]:
    stmt = apply_inventory_spine_joins(
        select(
            InventoryCopy,
            publisher_expr(),
            title_expr(),
            issue_number_expr(),
            func.coalesce(ComicIssue.id, InventoryCopy.catalog_issue_id),
        )
    ).where(InventoryCopy.user_id == owner_user_id)
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
    facts: list[_ItemFact] = []
    for inv, publisher_name, comic_title_name, issue_number, issue_id in session.exec(stmt).all():
        iid = int(inv.id or 0)
        if not iid:
            continue
        facts.append(
            _ItemFact(
                inventory_item_id=iid,
                portfolio_id=portfolio_id,
                canonical_comic_issue_id=int(issue_id or 0),
                current_fmv=_money(inv.current_fmv) if inv.current_fmv is not None else None,
                acquisition_cost=_money(inv.acquisition_cost),
                publisher_key=_slug(publisher_name),
                title_key=_slug(f"{comic_title_name}::{issue_number}"),
                engine_status=None,
                sell_through_rate_pct=ZERO,
                stale_listing_rate_pct=ZERO,
                grading_action=None,
                grading_strength=None,
                grading_confidence=None,
                grading_risk=None,
                grading_expected_roi=None,
                grading_liquidity_adjusted_roi=None,
                grading_rationale=None,
                listing_intelligence_status=None,
                listing_stale_risk_flag=False,
                exposure_status=None,
                exposure_pct_value=None,
                duplicate_status=None,
                duplicate_action=None,
                duplicate_teaser=None,
                portfolio_liquidity_bucket="MEDIUM",
                portfolio_liquidity_snapshot_id=None,
            )
        )
    return facts


def _latest_liquidity_engine_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, tuple[str | None, Decimal, Decimal, int | None]]:
    out: dict[int, tuple[str | None, Decimal, Decimal, int | None]] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(
            InventoryLiquiditySnapshot.id,
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
    for snap_id, iid, status_val, sell, stale in rows:
        inv_id = int(iid or 0)
        if inv_id and inv_id not in out:
            out[inv_id] = (
                str(status_val) if status_val is not None else None,
                _pct(sell),
                _pct(stale),
                int(snap_id) if snap_id is not None else None,
            )
    return out


def _latest_grading_map(
    session: Session, *, owner_user_id: int, inv_ids: list[int]
) -> dict[int, GradingRecommendation]:
    out: dict[int, GradingRecommendation] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(GradingRecommendation)
        .where(
            GradingRecommendation.owner_user_id == owner_user_id,
            col(GradingRecommendation.inventory_item_id).in_(inv_ids),
            col(GradingRecommendation.inventory_item_id).is_not(None),
        )
        .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_risk_map(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, GradingRiskSnapshot]:
    out: dict[int, GradingRiskSnapshot] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(GradingRiskSnapshot)
        .where(
            GradingRiskSnapshot.owner_user_id == owner_user_id,
            col(GradingRiskSnapshot.inventory_item_id).in_(inv_ids),
            col(GradingRiskSnapshot.inventory_item_id).is_not(None),
        )
        .order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
    ).all()
    for row in rows:
        iid = int(row.inventory_item_id or 0)
        if iid and iid not in out:
            out[iid] = row
    return out


def _latest_listing_intel_map(
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


def _latest_exposure_map(
    session: Session,
    *,
    owner_user_id: int,
    scope: str,
    keys: set[tuple[str, str]],
) -> dict[tuple[str, str], PortfolioExposureSnapshot]:
    out: dict[tuple[str, str], PortfolioExposureSnapshot] = {}
    if not keys:
        return out
    rows = session.exec(
        select(PortfolioExposureSnapshot)
        .where(
            PortfolioExposureSnapshot.owner_user_id == owner_user_id,
            PortfolioExposureSnapshot.generation_scope_key == scope,
            col(PortfolioExposureSnapshot.portfolio_id).is_(None) if scope == SCOPE_ALL_INVENTORY else literal(True),
        )
        .order_by(col(PortfolioExposureSnapshot.created_at).desc(), col(PortfolioExposureSnapshot.id).desc())
    ).all()
    for row in rows:
        key = (str(row.exposure_type), str(row.exposure_key))
        if key in keys and key not in out:
            out[key] = row
    return out


def _latest_portfolio_liquidity_snapshot(
    session: Session, *, owner_user_id: int, portfolio_id: int | None
) -> PortfolioLiquiditySnapshot | None:
    scope = scope_key(portfolio_id)
    return session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == scope,
        )
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    ).first()


def _latest_allocation_snapshot(
    session: Session, *, owner_user_id: int, portfolio_id: int | None
) -> PortfolioAllocationSnapshot | None:
    scope = scope_key(portfolio_id)
    return session.exec(
        select(PortfolioAllocationSnapshot)
        .where(
            PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
            PortfolioAllocationSnapshot.generation_scope_key == scope,
        )
        .order_by(col(PortfolioAllocationSnapshot.created_at).desc(), col(PortfolioAllocationSnapshot.id).desc())
    ).first()


def _latest_sale_record(session: Session, *, inventory_item_id: int) -> SaleRecord | None:
    return session.exec(
        select(SaleRecord)
        .join(Listing, SaleRecord.listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(SaleRecord.sale_date).desc().nullslast(), col(SaleRecord.id).desc())
    ).first()


def _latest_market_sale(session: Session, *, inventory_item_id: int) -> MarketSaleRecord | None:
    return session.exec(
        select(MarketSaleRecord)
        .join(Listing, MarketSaleRecord.source_listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(MarketSaleRecord.sale_date).desc().nullslast(), col(MarketSaleRecord.id).desc())
    ).first()


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
            col(SaleRecordLineItem.inventory_item_id).in_(inv_ids),
        )
    ).all()
    for iid, amt in rows:
        inv_id = int(iid or 0)
        if inv_id:
            out[inv_id] = out.get(inv_id, ZERO) + _money(amt)
    return out


def _latest_active_listing_count(session: Session, *, owner_user_id: int, inv_ids: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    if not inv_ids:
        return out
    rows = session.exec(
        select(Listing.id, Listing.inventory_copy_id, Listing.archived_at)
        .where(
            Listing.owner_user_id == owner_user_id,
            col(Listing.inventory_copy_id).in_(inv_ids),
            Listing.archived_at.is_(None),
        )
    ).all()
    for _lid, iid, _archived_at in rows:
        inv_id = int(iid or 0)
        if inv_id:
            out[inv_id] = out.get(inv_id, 0) + 1
    return out


def _classify_confidence(score: Decimal) -> str:
    if score >= Decimal("75"):
        return "HIGH"
    if score >= Decimal("50"):
        return "MEDIUM"
    return "LOW"


def _classify_risk(points: int) -> str:
    if points >= 6:
        return "HIGH"
    if points >= 3:
        return "MEDIUM"
    return "LOW"


def _classify_strength(score: Decimal) -> str:
    if score >= Decimal("78"):
        return "ELITE"
    if score >= Decimal("58"):
        return "STRONG"
    if score >= Decimal("35"):
        return "MODERATE"
    return "WEAK"


def _portfolio_bucket_bonus(bucket: str | None) -> tuple[Decimal, int, list[str]]:
    if bucket == "HIGH":
        return Decimal("0.18"), 0, []
    if bucket == "MEDIUM":
        return Decimal("0.06"), 1, []
    if bucket == "LOW":
        return Decimal("-0.14"), 2, ["liquidity_low"]
    if bucket == "ILLIQUID":
        return Decimal("-0.28"), 3, ["liquidity_illiquid"]
    return Decimal("-0.08"), 1, ["liquidity_missing"]


def _duplicate_bonus(status: str | None, action: str | None, strongest: bool) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    score = ZERO
    risk = 0
    if status == "HEALTHY":
        score += Decimal("0.08")
    elif status == "WATCH":
        score += Decimal("0.02")
    elif status == "REDUNDANT":
        score -= Decimal("0.10")
        risk += 1
        flags.append("duplicate_redundant")
    elif status == "OVEREXPOSED":
        score -= Decimal("0.22")
        risk += 2
        flags.append("duplicate_overexposed")
    else:
        score -= Decimal("0.05")
        risk += 1
        flags.append("duplicate_unknown")
    if action:
        act = action.upper()
        if act in {"SELL_DUPLICATES", "REDUCE_EXPOSURE"}:
            score -= Decimal("0.10")
            risk += 1
            flags.append(f"duplicate_action_{act.lower()}")
        elif act == "KEEP_BEST_COPY":
            score += Decimal("0.05")
    if not strongest:
        score -= Decimal("0.08")
        risk += 1
        flags.append("not_strongest_copy")
    return score, risk, flags


def _grading_bonus(gr: GradingRecommendation | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if gr is None:
        return Decimal("-0.04"), 1, ["missing_grading_recommendation"]
    action = str(gr.recommended_action or "").upper()
    strength = str(gr.recommendation_strength or "").upper()
    risk = str(gr.risk_level or "").upper()
    bonus = ZERO
    risk_points = 0
    if action == "GRADE":
        bonus += Decimal("0.22")
        flags.append("grade_recommendation_present")
    elif action in {"HOLD_RAW", "REVIEW_MANUALLY"}:
        bonus += Decimal("0.04")
    elif action == "NOT_RECOMMENDED":
        bonus -= Decimal("0.10")
        risk_points += 1
        flags.append("grading_not_recommended")
    if strength == "ELITE":
        bonus += Decimal("0.14")
    elif strength == "STRONG":
        bonus += Decimal("0.10")
    elif strength == "MODERATE":
        bonus += Decimal("0.05")
    else:
        bonus -= Decimal("0.04")
        risk_points += 1
    if risk == "HIGH":
        bonus -= Decimal("0.18")
        risk_points += 2
        flags.append("grading_risk_high")
    elif risk == "MEDIUM":
        bonus -= Decimal("0.06")
        risk_points += 1
    if gr.expected_roi is not None:
        if gr.expected_roi >= Decimal("0.75"):
            bonus += Decimal("0.10")
        elif gr.expected_roi >= Decimal("0.35"):
            bonus += Decimal("0.05")
        else:
            bonus -= Decimal("0.04")
    if gr.liquidity_adjusted_roi is not None:
        if gr.liquidity_adjusted_roi >= Decimal("0.75"):
            bonus += Decimal("0.08")
        elif gr.liquidity_adjusted_roi < Decimal("0.25"):
            bonus -= Decimal("0.05")
    return bonus, risk_points, flags


def _risk_penalty(risk: GradingRiskSnapshot | None) -> tuple[Decimal, int, list[str]]:
    if risk is None:
        return Decimal("-0.04"), 1, ["missing_risk_snapshot"]
    flags: list[str] = []
    level = str(risk.overall_risk_level or "").upper()
    confidence = str(risk.overall_confidence_level or "").upper()
    penalty = ZERO
    risk_points = 0
    if level == "HIGH":
        penalty -= Decimal("0.22")
        risk_points += 3
        flags.append("risk_high")
    elif level == "MEDIUM":
        penalty -= Decimal("0.10")
        risk_points += 1
    if confidence == "LOW":
        penalty -= Decimal("0.10")
        risk_points += 2
        flags.append("confidence_low")
    elif confidence == "MEDIUM":
        penalty -= Decimal("0.04")
        risk_points += 1
    if risk.evidence_strength_score < Decimal("35"):
        penalty -= Decimal("0.05")
        risk_points += 1
        flags.append("evidence_thin")
    if risk.liquidity_risk_score >= Decimal("70"):
        penalty -= Decimal("0.08")
        risk_points += 1
        flags.append("liquidity_risk_high")
    if risk.market_stability_score < Decimal("35"):
        penalty -= Decimal("0.05")
        risk_points += 1
        flags.append("market_stability_weak")
    return penalty, risk_points, flags


def _listing_bonus(listing: ListingIntelligenceSnapshot | None, listing_count: int) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if listing is None:
        return Decimal("-0.03"), 1, ["missing_listing_intelligence"]
    status = str(listing.intelligence_status or "").upper()
    bonus = ZERO
    risk = 0
    if status == "STRONG":
        bonus += Decimal("0.08")
    elif status == "ADEQUATE":
        bonus += Decimal("0.04")
    else:
        bonus -= Decimal("0.06")
        risk += 1
        flags.append(f"listing_{status.lower() or 'missing'}")
    if listing.stale_risk_flag:
        bonus -= Decimal("0.08")
        risk += 1
        flags.append("listing_stale")
    if listing_count > 0:
        bonus += Decimal("0.03")
    return bonus, risk, flags


def _exposure_bonus(exposure_status: str | None, pct_value: Decimal | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if exposure_status is None:
        return Decimal("-0.03"), 1, ["missing_exposure"]
    status = exposure_status.upper()
    bonus = ZERO
    risk = 0
    if status == "BALANCED":
        bonus += Decimal("0.10")
    elif status == "WATCH":
        bonus += Decimal("0.02")
        risk += 1
    elif status == "CONCENTRATED":
        bonus -= Decimal("0.10")
        risk += 2
        flags.append("exposure_concentrated")
    elif status == "OVEREXPOSED":
        bonus -= Decimal("0.22")
        risk += 3
        flags.append("exposure_overexposed")
    else:
        bonus -= Decimal("0.04")
        risk += 1
        flags.append("exposure_unknown")
    if pct_value is not None:
        if pct_value >= Decimal("40"):
            bonus -= Decimal("0.08")
            risk += 1
        elif pct_value <= Decimal("15"):
            bonus += Decimal("0.04")
    return bonus, risk, flags


def _sell_pressure(
    *,
    sale_total: Decimal,
    active_listing_count: int,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    pressure = ZERO
    if sale_total > ZERO:
        pressure += Decimal("0.10")
    else:
        pressure -= Decimal("0.10")
        flags.append("no_sale_history")
    if active_listing_count > 0:
        pressure += Decimal("0.04")
    else:
        pressure -= Decimal("0.04")
        flags.append("no_active_listing")
    if sell_through_rate_pct < Decimal("18"):
        pressure -= Decimal("0.06")
        flags.append("weak_sell_through")
    if stale_listing_rate_pct >= Decimal("70"):
        pressure -= Decimal("0.08")
        flags.append("stale_listing_pressure")
    return pressure, flags


def _select_action(
    *,
    fact: _ItemFact,
    liquidity_bucket: str,
    duplicate_status: str | None,
    duplicate_action: str | None,
    strongest_copy: bool,
    grading: GradingRecommendation | None,
    exposure_status: str | None,
    confidence_score: Decimal,
    risk_level: str,
    sell_pressure_score: Decimal,
) -> str:
    grade_action = (grading.recommended_action if grading is not None else None or "").upper()
    grade_roi = grading.expected_roi if grading is not None else None
    grade_liq_roi = grading.liquidity_adjusted_roi if grading is not None else None

    duplicate_bad = duplicate_status in {"REDUNDANT", "OVEREXPOSED"} or (
        duplicate_action is not None and duplicate_action.upper() in {"SELL_DUPLICATES", "REDUCE_EXPOSURE"}
    )
    exposure_bad = exposure_status in {"CONCENTRATED", "OVEREXPOSED"}
    liquidity_bad = liquidity_bucket in {"LOW", "ILLIQUID"}
    liquidity_high = liquidity_bucket in {"HIGH", "MEDIUM"}
    grade_good = (
        grade_action == "GRADE"
        or (grade_roi is not None and grade_roi >= Decimal("0.35"))
        or (grade_liq_roi is not None and grade_liq_roi >= Decimal("0.35"))
    )

    if duplicate_bad and not strongest_copy:
        return "SELL"
    if duplicate_bad and strongest_copy and exposure_bad:
        return "CONSOLIDATE"
    if grade_good and liquidity_high and risk_level != "HIGH" and confidence_score >= Decimal("50"):
        return "GRADE_THEN_SELL"
    if exposure_bad and duplicate_bad:
        return "REDUCE_EXPOSURE"
    if liquidity_bad and (sell_pressure_score < ZERO or risk_level == "HIGH"):
        return "SELL"
    if confidence_score < Decimal("40") or risk_level == "HIGH":
        return "WATCH"
    if liquidity_high and not exposure_bad and not duplicate_bad:
        return "HOLD"
    if exposure_bad:
        return "REDUCE_EXPOSURE"
    if duplicate_bad:
        return "CONSOLIDATE"
    if liquidity_bad:
        return "WATCH"
    return "HOLD"


def _replay_signature(
    *,
    owner_user_id: int,
    portfolio_id: int | None,
    inventory_item_id: int,
    canonical_comic_issue_id: int,
    recommendation_action: str,
    recommendation_strength: str,
    confidence_level: str,
    risk_level: str,
    estimated_liquidity_impact: Decimal | None,
    estimated_capital_release: Decimal | None,
    estimated_portfolio_efficiency_gain: Decimal | None,
    expected_roi_if_graded: Decimal | None,
    warning_flags_json: list[object],
    snapshot_date: date,
    replay_key: str,
) -> str:
    return _hash_payload(
        {
            "owner_user_id": owner_user_id,
            "portfolio_id": portfolio_id,
            "inventory_item_id": inventory_item_id,
            "canonical_comic_issue_id": canonical_comic_issue_id,
            "recommendation_action": recommendation_action,
            "recommendation_strength": recommendation_strength,
            "confidence_level": confidence_level,
            "risk_level": risk_level,
            "estimated_liquidity_impact": estimated_liquidity_impact,
            "estimated_capital_release": estimated_capital_release,
            "estimated_portfolio_efficiency_gain": estimated_portfolio_efficiency_gain,
            "expected_roi_if_graded": expected_roi_if_graded,
            "warning_flags_json": warning_flags_json,
            "snapshot_date": snapshot_date,
            "replay_key": replay_key,
        }
    )


def _append_history(session: Session, row: PortfolioRecommendation) -> bool:
    checksum = _replay_signature(
        owner_user_id=row.owner_user_id,
        portfolio_id=row.portfolio_id,
        inventory_item_id=int(row.inventory_item_id or 0),
        canonical_comic_issue_id=int(row.canonical_comic_issue_id or 0),
        recommendation_action=row.recommendation_action,
        recommendation_strength=row.recommendation_strength,
        confidence_level=row.confidence_level,
        risk_level=row.risk_level,
        estimated_liquidity_impact=row.estimated_liquidity_impact,
        estimated_capital_release=row.estimated_capital_release,
        estimated_portfolio_efficiency_gain=row.estimated_portfolio_efficiency_gain,
        expected_roi_if_graded=row.expected_roi_if_graded,
        warning_flags_json=list(row.warning_flags_json or []),
        snapshot_date=row.snapshot_date,
        replay_key=str(row.replay_key or ""),
    )
    existing = session.exec(
        select(PortfolioRecommendationHistory)
        .where(PortfolioRecommendationHistory.owner_user_id == row.owner_user_id)
        .where(PortfolioRecommendationHistory.portfolio_id == row.portfolio_id)
        .where(PortfolioRecommendationHistory.inventory_item_id == row.inventory_item_id)
        .where(PortfolioRecommendationHistory.recommendation_action == row.recommendation_action)
        .where(PortfolioRecommendationHistory.recommendation_strength == row.recommendation_strength)
        .where(PortfolioRecommendationHistory.confidence_level == row.confidence_level)
        .where(PortfolioRecommendationHistory.risk_level == row.risk_level)
        .where(PortfolioRecommendationHistory.snapshot_date == row.snapshot_date)
        .where(PortfolioRecommendationHistory.checksum == checksum)
    ).first()
    if existing is not None:
        return False
    session.add(
        PortfolioRecommendationHistory(
            owner_user_id=row.owner_user_id,
            inventory_item_id=row.inventory_item_id,
            portfolio_id=row.portfolio_id,
            recommendation_action=row.recommendation_action,
            recommendation_strength=row.recommendation_strength,
            confidence_level=row.confidence_level,
            risk_level=row.risk_level,
            checksum=checksum,
            snapshot_date=row.snapshot_date,
            created_at=utc_now(),
        )
    )
    return True


def _recommendation_read(row: PortfolioRecommendation) -> PortfolioRecommendationRead:
    return PortfolioRecommendationRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_item_id=row.inventory_item_id,
        portfolio_id=row.portfolio_id,
        canonical_comic_issue_id=row.canonical_comic_issue_id,
        recommendation_action=str(row.recommendation_action),
        recommendation_strength=str(row.recommendation_strength),
        confidence_level=str(row.confidence_level),
        risk_level=str(row.risk_level),
        estimated_liquidity_impact=row.estimated_liquidity_impact,
        estimated_capital_release=row.estimated_capital_release,
        estimated_portfolio_efficiency_gain=row.estimated_portfolio_efficiency_gain,
        expected_roi_if_graded=row.expected_roi_if_graded,
        rationale_summary=str(row.rationale_summary),
        warning_flags_json=list(row.warning_flags_json or []),
        recommendation_status=str(row.recommendation_status),
        checksum=str(row.checksum),
        replay_key=row.replay_key,
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _evidence_read(row: PortfolioRecommendationEvidence) -> PortfolioRecommendationEvidenceRead:
    return PortfolioRecommendationEvidenceRead(
        id=int(row.id or 0),
        portfolio_recommendation_id=int(row.portfolio_recommendation_id),
        evidence_type=str(row.evidence_type),
        source_id=row.source_id,
        source_table=row.source_table,
        evidence_value_json=dict(row.evidence_value_json or {}),
        created_at=row.created_at,
    )


def _scenario_read(row: PortfolioRecommendationScenario) -> PortfolioRecommendationScenarioRead:
    return PortfolioRecommendationScenarioRead(
        id=int(row.id or 0),
        portfolio_recommendation_id=int(row.portfolio_recommendation_id),
        scenario_name=str(row.scenario_name),
        projected_capital_release=row.projected_capital_release,
        projected_liquidity_gain=row.projected_liquidity_gain,
        projected_portfolio_impact=row.projected_portfolio_impact,
        created_at=row.created_at,
    )


def _history_read(row: PortfolioRecommendationHistory) -> PortfolioRecommendationHistoryRead:
    return PortfolioRecommendationHistoryRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_item_id=row.inventory_item_id,
        portfolio_id=row.portfolio_id,
        recommendation_action=str(row.recommendation_action),
        recommendation_strength=str(row.recommendation_strength),
        confidence_level=str(row.confidence_level),
        risk_level=str(row.risk_level),
        checksum=str(row.checksum),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _detail_read(session: Session, row: PortfolioRecommendation) -> PortfolioRecommendationDetailRead:
    rid = int(row.id or 0)
    evidence = session.exec(
        select(PortfolioRecommendationEvidence)
        .where(PortfolioRecommendationEvidence.portfolio_recommendation_id == rid)
        .order_by(col(PortfolioRecommendationEvidence.created_at).asc(), col(PortfolioRecommendationEvidence.id).asc())
    ).all()
    scenarios = session.exec(
        select(PortfolioRecommendationScenario)
        .where(PortfolioRecommendationScenario.portfolio_recommendation_id == rid)
        .order_by(col(PortfolioRecommendationScenario.id).asc())
    ).all()
    history = session.exec(
        select(PortfolioRecommendationHistory)
        .where(PortfolioRecommendationHistory.owner_user_id == row.owner_user_id)
        .where(
            PortfolioRecommendationHistory.inventory_item_id == row.inventory_item_id
            if row.inventory_item_id is not None
            else literal(True)
        )
        .order_by(col(PortfolioRecommendationHistory.snapshot_date).desc(), col(PortfolioRecommendationHistory.id).desc())
    ).all()
    return PortfolioRecommendationDetailRead(
        recommendation=_recommendation_read(row),
        evidence=[_evidence_read(item) for item in evidence],
        scenarios=[_scenario_read(item) for item in scenarios],
        history=[_history_read(item) for item in history],
    )


def _ensure_owner_recommendation(session: Session, *, owner_user_id: int, recommendation_id: int) -> PortfolioRecommendation:
    row = session.get(PortfolioRecommendation, recommendation_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio recommendation not found")
    return row


def _ensure_ops_recommendation(session: Session, *, recommendation_id: int) -> PortfolioRecommendation:
    row = session.get(PortfolioRecommendation, recommendation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio recommendation not found")
    return row


def _recommendation_query(
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(PortfolioRecommendation)
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioRecommendation.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(PortfolioRecommendation.portfolio_id == portfolio_id)
    if inventory_item_id is not None:
        stmt = stmt.where(PortfolioRecommendation.inventory_item_id == inventory_item_id)
    if recommendation_action is not None:
        stmt = stmt.where(PortfolioRecommendation.recommendation_action == recommendation_action)
    if recommendation_strength is not None:
        stmt = stmt.where(PortfolioRecommendation.recommendation_strength == recommendation_strength)
    if confidence_level is not None:
        stmt = stmt.where(PortfolioRecommendation.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(PortfolioRecommendation.risk_level == risk_level)
    if date_from is not None:
        stmt = stmt.where(PortfolioRecommendation.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(PortfolioRecommendation.snapshot_date <= date_to)
    return stmt


def _evidence_query(*, owner_user_id: int | None = None, recommendation_id: int | None = None):
    stmt = select(PortfolioRecommendationEvidence).join(
        PortfolioRecommendation,
        PortfolioRecommendationEvidence.portfolio_recommendation_id == PortfolioRecommendation.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioRecommendation.owner_user_id == owner_user_id)
    if recommendation_id is not None:
        stmt = stmt.where(PortfolioRecommendationEvidence.portfolio_recommendation_id == recommendation_id)
    return stmt


def _history_query(
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(PortfolioRecommendationHistory)
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.owner_user_id == owner_user_id)
    if portfolio_id is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.portfolio_id == portfolio_id)
    if inventory_item_id is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.inventory_item_id == inventory_item_id)
    if recommendation_action is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.recommendation_action == recommendation_action)
    if recommendation_strength is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.recommendation_strength == recommendation_strength)
    if confidence_level is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.risk_level == risk_level)
    if date_from is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(PortfolioRecommendationHistory.snapshot_date <= date_to)
    return stmt


def _evidence_payload_for_fact(
    *,
    sale_total: Decimal,
    active_listing_count: int,
    scope_liquidity: PortfolioLiquiditySnapshot | None,
    scope_allocation: PortfolioAllocationSnapshot | None,
    grading: GradingRecommendation | None,
    risk: GradingRiskSnapshot | None,
    listing: ListingIntelligenceSnapshot | None,
    sale_record: SaleRecord | None,
    market_sale: MarketSaleRecord | None,
    duplicate_teaser: Any,
    exposure_rows: list[PortfolioExposureSnapshot],
) -> list[tuple[str, int | None, str | None, dict[str, Any]]]:
    exposure_payloads = []
    for row in exposure_rows:
        exposure_payloads.append(
            {
                "exposure_type": row.exposure_type,
                "exposure_key": row.exposure_key,
                "exposure_status": row.exposure_status,
                "percentage_of_portfolio_value": row.percentage_of_portfolio_value,
                "percentage_of_portfolio_count": row.percentage_of_portfolio_count,
                "generation_batch_checksum": row.generation_batch_checksum,
            }
        )
    return [
        (
            "PORTFOLIO_LIQUIDITY",
            int(scope_liquidity.id) if scope_liquidity is not None else None,
            "portfolio_liquidity_snapshot",
            {
                "liquidity_balance_status": scope_liquidity.liquidity_balance_status if scope_liquidity is not None else None,
                "liquidity_efficiency_score": scope_liquidity.liquidity_efficiency_score if scope_liquidity is not None else None,
                "dead_capital_estimate": scope_liquidity.dead_capital_estimate if scope_liquidity is not None else None,
            },
        ),
        (
            "PORTFOLIO_EXPOSURE",
            int(scope_allocation.id) if scope_allocation is not None else None,
            "portfolio_exposure_snapshot",
            {
                "scope_generation_checksum": scope_allocation.checksum if scope_allocation is not None else None,
                "high_liquidity_count": scope_allocation.high_liquidity_count if scope_allocation is not None else None,
                "low_liquidity_count": scope_allocation.low_liquidity_count if scope_allocation is not None else None,
                "duplicate_count": scope_allocation.duplicate_count if scope_allocation is not None else None,
            },
        ),
        (
            "GRADING_RECOMMENDATION",
            int(grading.id) if grading is not None else None,
            "grading_recommendation",
            {
                "recommended_action": grading.recommended_action if grading is not None else None,
                "recommendation_strength": grading.recommendation_strength if grading is not None else None,
                "confidence_score": grading.confidence_score if grading is not None else None,
                "risk_level": grading.risk_level if grading is not None else None,
                "expected_roi": grading.expected_roi if grading is not None else None,
                "liquidity_adjusted_roi": grading.liquidity_adjusted_roi if grading is not None else None,
            },
        ),
        (
            "RISK_ENGINE",
            int(risk.id) if risk is not None else None,
            "grading_risk_snapshot",
            {
                "overall_risk_level": risk.overall_risk_level if risk is not None else None,
                "overall_confidence_level": risk.overall_confidence_level if risk is not None else None,
                "liquidity_risk_score": risk.liquidity_risk_score if risk is not None else None,
                "market_stability_score": risk.market_stability_score if risk is not None else None,
            },
        ),
        (
            "LISTING_INTELLIGENCE",
            int(listing.id) if listing is not None else None,
            "listing_intelligence_snapshot",
            {
                "intelligence_status": listing.intelligence_status if listing is not None else None,
                "stale_risk_flag": listing.stale_risk_flag if listing is not None else None,
                "listing_count": active_listing_count,
            },
        ),
        (
            "SALES_LEDGER",
            None,
            "sale_record_line_item",
            {
                "recorded_sales_total": sale_total,
                "latest_sale_record_id": int(sale_record.id) if sale_record is not None else None,
            },
        ),
        (
            "MARKET_SALE",
            int(market_sale.id) if market_sale is not None else None,
            "market_sale_record",
            {
                "latest_market_sale_record_id": int(market_sale.id) if market_sale is not None else None,
            },
        ),
        (
            "DUPLICATE_INTELLIGENCE",
            None,
            "duplicate_consolidation",
            {
                "generation_batch_checksum": getattr(duplicate_teaser, "generation_batch_checksum", None),
                "cluster_types_present": getattr(duplicate_teaser, "cluster_types_present", []),
                "worst_duplication_status": getattr(duplicate_teaser, "worst_duplication_status", None),
            },
        ),
        *[
            (
                "PORTFOLIO_EXPOSURE",
                row.id,
                "portfolio_exposure_snapshot",
                payload,
            )
            for row, payload in zip(exposure_rows, exposure_payloads)
        ],
    ]


def generate_portfolio_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioRecommendationGeneratePayload,
) -> PortfolioRecommendationGenerateResponse:
    snap_date = payload.snapshot_date or date.today()
    rk = _norm_rk(payload.replay_key)
    portfolio_id = payload.portfolio_id
    if portfolio_id is not None:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None or int(portfolio.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found for owner")

    facts = _scope_inventory_rows(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    if not facts:
        return PortfolioRecommendationGenerateResponse(replayed=False, items=[], total=0, history_appended_count=0)

    inv_ids = [fact.inventory_item_id for fact in facts]
    liquidity_map = _latest_liquidity_engine_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    grading_map = _latest_grading_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    risk_map = _latest_risk_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_map = _latest_listing_intel_map(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    sale_map = _latest_sale_lines(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    listing_count_map = _latest_active_listing_count(session, owner_user_id=owner_user_id, inv_ids=inv_ids)
    scope_liquidity = _latest_portfolio_liquidity_snapshot(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    scope_allocation = _latest_allocation_snapshot(session, owner_user_id=owner_user_id, portfolio_id=portfolio_id)
    sale_record_map = {fact.inventory_item_id: _latest_sale_record(session, inventory_item_id=fact.inventory_item_id) for fact in facts}
    market_sale_map = {fact.inventory_item_id: _latest_market_sale(session, inventory_item_id=fact.inventory_item_id) for fact in facts}

    exposure_keys = {(kind, slug) for fact in facts for kind, slug in (("publisher", fact.publisher_key), ("title", fact.title_key))}
    exposure_map = _latest_exposure_map(
        session,
        owner_user_id=owner_user_id,
        scope=scope_key(portfolio_id),
        keys=exposure_keys,
    )

    duplicate_teasers = {fact.inventory_item_id: inventory_duplicate_teaser(session, owner_user_id=owner_user_id, inventory_item_id=fact.inventory_item_id) for fact in facts}

    total_scope_fmv = sum((_money(f.current_fmv) if f.current_fmv is not None else ZERO) for f in facts)
    item_rows: list[PortfolioRecommendation] = []
    history_appended_count = 0
    replayed_all = True

    for fact in facts:
        liq_status, sell_through, stale_rate, liq_snap_id = liquidity_map.get(
            fact.inventory_item_id, (None, ZERO, ZERO, None)
        )
        grading = grading_map.get(fact.inventory_item_id)
        risk = risk_map.get(fact.inventory_item_id)
        listing = listing_map.get(fact.inventory_item_id)
        sale_total = sale_map.get(fact.inventory_item_id, ZERO)
        active_listing_count = listing_count_map.get(fact.inventory_item_id, 0)
        dup = duplicate_teasers.get(fact.inventory_item_id)
        duplicate_status = getattr(dup, "worst_duplication_status", None)
        duplicate_action = getattr(dup, "primary_consolidation_action", None)
        strongest_copy = bool(getattr(dup, "is_strongest_copy_in_clusters", True))

        publisher_row = exposure_map.get(("publisher", fact.publisher_key))
        title_row = exposure_map.get(("title", fact.title_key))
        exposure_rows = [row for row in (publisher_row, title_row) if row is not None]
        exposure_status = None
        exposure_pct_value = None
        if exposure_rows:
            ordered = sorted(
                exposure_rows,
                key=lambda row: (
                    0
                    if row.exposure_status == "OVEREXPOSED"
                    else 1 if row.exposure_status == "CONCENTRATED" else 2,
                    row.id or 0,
                ),
            )
            chosen = ordered[0]
            exposure_status = str(chosen.exposure_status)
            exposure_pct_value = chosen.percentage_of_portfolio_value or chosen.percentage_of_portfolio_count

        liq_bucket = "MEDIUM"
        liq_bonus, liq_risk, liq_flags = _portfolio_bucket_bonus(liq_status)
        if liq_status == "HIGH":
            liq_bucket = "HIGH"
        elif liq_status == "MODERATE":
            liq_bucket = "MEDIUM"
        elif liq_status == "LOW":
            liq_bucket = "LOW"
        elif liq_status == "ILLIQUID":
            liq_bucket = "ILLIQUID"

        dup_bonus, dup_risk, dup_flags = _duplicate_bonus(duplicate_status, duplicate_action, strongest_copy)
        grade_bonus, grade_risk, grade_flags = _grading_bonus(grading)
        risk_penalty, risk_points, risk_flags = _risk_penalty(risk)
        listing_bonus, listing_risk, listing_flags = _listing_bonus(listing, active_listing_count)
        exposure_bonus, exposure_risk, exposure_flags = _exposure_bonus(exposure_status, exposure_pct_value)
        sell_pressure_score, sell_flags = _sell_pressure(
            sale_total=sale_total,
            active_listing_count=active_listing_count,
            sell_through_rate_pct=sell_through,
            stale_listing_rate_pct=stale_rate,
        )

        strength_score = _score_q(
            Decimal("45")
            + (liq_bonus * Decimal("100"))
            + (dup_bonus * Decimal("100"))
            + (grade_bonus * Decimal("100"))
            + (listing_bonus * Decimal("100"))
            + (exposure_bonus * Decimal("100"))
            + (risk_penalty * Decimal("100"))
        )
        confidence_score = _score_q(
            Decimal("28")
            + (Decimal("8") if scope_liquidity is not None else Decimal("0"))
            + (Decimal("8") if grading is not None else Decimal("0"))
            + (Decimal("8") if risk is not None else Decimal("0"))
            + (Decimal("6") if dup is not None else Decimal("0"))
            + (Decimal("6") if listing is not None else Decimal("0"))
            + (Decimal("6") if sale_total > ZERO else Decimal("0"))
            + (Decimal("6") if exposure_rows else Decimal("0"))
            + (Decimal("4") if scope_allocation is not None else Decimal("0"))
            - (Decimal(str((liq_risk + dup_risk + grade_risk + risk_points + listing_risk + exposure_risk) * 4)))
        )
        confidence_level = _classify_confidence(confidence_score)
        risk_level = _classify_risk(liq_risk + dup_risk + grade_risk + risk_points + listing_risk + exposure_risk)
        recommendation_action = _select_action(
            fact=fact,
            liquidity_bucket=liq_bucket,
            duplicate_status=duplicate_status,
            duplicate_action=duplicate_action,
            strongest_copy=strongest_copy,
            grading=grading,
            exposure_status=exposure_status,
            confidence_score=confidence_score,
            risk_level=risk_level,
            sell_pressure_score=sell_pressure_score,
        )
        recommendation_strength = _classify_strength(strength_score)

        base_fmv = fact.current_fmv if fact.current_fmv is not None else fact.acquisition_cost
        if recommendation_action == "SELL":
            capital_release = base_fmv
            liquidity_impact = capital_release
        elif recommendation_action == "REDUCE_EXPOSURE":
            capital_release = _money(base_fmv * Decimal("0.50"))
            liquidity_impact = _money(base_fmv * Decimal("0.40"))
        elif recommendation_action == "GRADE_THEN_SELL":
            capital_release = _money(base_fmv * Decimal("0.80"))
            liquidity_impact = _money(base_fmv * Decimal("0.60"))
        elif recommendation_action == "CONSOLIDATE":
            capital_release = _money(base_fmv * Decimal("0.65"))
            liquidity_impact = _money(base_fmv * Decimal("0.55"))
        else:
            capital_release = None
            liquidity_impact = None
        expected_roi_if_graded = None
        if grading is not None and grading.expected_roi is not None:
            expected_roi_if_graded = _pct(grading.expected_roi)
        if recommendation_action == "GRADE_THEN_SELL" and expected_roi_if_graded is None:
            expected_roi_if_graded = Decimal("0.35")

        efficiency_gain = None
        if capital_release is not None and total_scope_fmv > ZERO:
            efficiency_gain = _score_q((capital_release / total_scope_fmv) * DEC_100)

        warning_flags = sorted(
            {
                *liq_flags,
                *dup_flags,
                *grade_flags,
                *risk_flags,
                *listing_flags,
                *exposure_flags,
                *sell_flags,
                "portfolio_scope" if portfolio_id is not None else "all_inventory_scope",
            }
        )
        if recommendation_action in {"WATCH", "HOLD"} and confidence_level == "LOW":
            warning_flags.append("uncertain_economics")

        rationale_bits = [
            {
                "HOLD": "liquidity and exposure remain healthy",
                "SELL": "capital is tied in weak liquidity and strategic value is low",
                "REDUCE_EXPOSURE": "portfolio concentration is unhealthy",
                "GRADE_THEN_SELL": "grading upside and liquidity support a higher-value exit",
                "CONSOLIDATE": "duplicate posture suggests redundant capital",
                "WATCH": "signals are mixed or evidence is thin",
            }[recommendation_action]
        ]
        if liq_status:
            rationale_bits.append(f"liquidity {liq_status.lower()}")
        if duplicate_status:
            rationale_bits.append(f"duplicates {duplicate_status.lower()}")
        if exposure_status:
            rationale_bits.append(f"exposure {exposure_status.lower()}")
        if grading is not None and grading.recommended_action:
            rationale_bits.append(f"grading {grading.recommended_action.lower()}")
        rationale_summary = ". ".join(rationale_bits) + "."

        checksum = _hash_payload(
            {
                "owner_user_id": owner_user_id,
                "portfolio_id": portfolio_id,
                "inventory_item_id": fact.inventory_item_id,
                "canonical_comic_issue_id": fact.canonical_comic_issue_id,
                "recommendation_action": recommendation_action,
                "recommendation_strength": recommendation_strength,
                "confidence_level": confidence_level,
                "risk_level": risk_level,
                "estimated_liquidity_impact": liquidity_impact,
                "estimated_capital_release": capital_release,
                "estimated_portfolio_efficiency_gain": efficiency_gain,
                "expected_roi_if_graded": expected_roi_if_graded,
                "warning_flags_json": warning_flags,
                "snapshot_date": snap_date,
                "scope_key": scope_key(portfolio_id),
                "replay_key": rk,
                "ordered_exposure_keys": sorted([f"{k}:{v}" for k, v in exposure_keys]),
            }
        )

        existing = session.exec(
            select(PortfolioRecommendation)
            .where(PortfolioRecommendation.owner_user_id == owner_user_id)
            .where(PortfolioRecommendation.portfolio_id == portfolio_id)
            .where(PortfolioRecommendation.inventory_item_id == fact.inventory_item_id)
            .where(PortfolioRecommendation.snapshot_date == snap_date)
            .where(PortfolioRecommendation.replay_key == rk)
        ).first()
        if existing is not None and str(existing.checksum) == checksum:
            item_rows.append(existing)
            continue
        if existing is not None:
            existing.recommendation_status = "SUPERSEDED"
            session.add(existing)
        replayed_all = False

        row = PortfolioRecommendation(
            owner_user_id=owner_user_id,
            inventory_item_id=fact.inventory_item_id,
            portfolio_id=portfolio_id,
            canonical_comic_issue_id=fact.canonical_comic_issue_id,
            recommendation_action=recommendation_action,
            recommendation_strength=recommendation_strength,
            confidence_level=confidence_level,
            risk_level=risk_level,
            estimated_liquidity_impact=liquidity_impact,
            estimated_capital_release=capital_release,
            estimated_portfolio_efficiency_gain=efficiency_gain,
            expected_roi_if_graded=expected_roi_if_graded,
            rationale_summary=rationale_summary,
            warning_flags_json=warning_flags,
            recommendation_status="ACTIVE",
            checksum=checksum,
            replay_key=rk,
            snapshot_date=snap_date,
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()

        scope_liq_info = scope_liquidity
        scope_alloc_info = scope_allocation
        exposure_rows_for_item = [r for r in (publisher_row, title_row) if r is not None]
        evidence_rows = _evidence_payload_for_fact(
            sale_total=sale_total,
            active_listing_count=active_listing_count,
            scope_liquidity=scope_liq_info,
            scope_allocation=scope_alloc_info,
            grading=grading,
            risk=risk,
            listing=listing,
            sale_record=sale_record_map.get(fact.inventory_item_id),
            market_sale=market_sale_map.get(fact.inventory_item_id),
            duplicate_teaser=dup,
            exposure_rows=exposure_rows_for_item,
        )
        for evidence_type, source_id, source_table, payload_json in evidence_rows:
            session.add(
                PortfolioRecommendationEvidence(
                    portfolio_recommendation_id=int(row.id or 0),
                    evidence_type=str(evidence_type),
                    source_id=source_id,
                    source_table=source_table,
                    evidence_value_json=_json_safe(payload_json),
                    created_at=utc_now(),
                )
            )

        scenario_rows = []
        for scenario_name, multiplier in (
            ("pessimistic", Decimal("0.85")),
            ("baseline", Decimal("1.00")),
            ("optimistic", Decimal("1.15")),
        ):
            scenario_rows.append(
                PortfolioRecommendationScenario(
                    portfolio_recommendation_id=int(row.id or 0),
                    scenario_name=scenario_name,
                    projected_capital_release=_money(capital_release * multiplier) if capital_release is not None else None,
                    projected_liquidity_gain=_money(liquidity_impact * multiplier) if liquidity_impact is not None else None,
                    projected_portfolio_impact=_pct(efficiency_gain * multiplier) if efficiency_gain is not None else None,
                    created_at=utc_now(),
                )
            )
        for scenario in scenario_rows:
            session.add(scenario)

        history_written = _append_history(session, row=row)
        history_appended_count += 1 if history_written else 0
        item_rows.append(row)

    session.commit()
    return PortfolioRecommendationGenerateResponse(
        replayed=replayed_all,
        items=[_recommendation_read(row) for row in item_rows],
        total=len(item_rows),
        history_appended_count=history_appended_count,
    )


def list_recommendations_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PortfolioRecommendationListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _recommendation_query(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(PortfolioRecommendation.snapshot_date).desc(), col(PortfolioRecommendation.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationListResponse(items=[_recommendation_read(row) for row in rows], total=total)


def list_recommendations_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PortfolioRecommendationListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _recommendation_query(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioRecommendation.owner_user_id).asc(),
            col(PortfolioRecommendation.snapshot_date).desc(),
            col(PortfolioRecommendation.id).desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationListResponse(items=[_recommendation_read(row) for row in rows], total=total)


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioRecommendationEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _evidence_query(owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    if evidence_type is not None:
        stmt = stmt.where(PortfolioRecommendationEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioRecommendationEvidence.created_at).asc(),
            col(PortfolioRecommendationEvidence.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    recommendation_id: int | None = None,
    evidence_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioRecommendationEvidenceListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _evidence_query(owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    if evidence_type is not None:
        stmt = stmt.where(PortfolioRecommendationEvidence.evidence_type == evidence_type)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioRecommendationEvidence.created_at).asc(),
            col(PortfolioRecommendationEvidence.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationEvidenceListResponse(items=[_evidence_read(row) for row in rows], total=total)


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioRecommendationHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _history_query(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioRecommendationHistory.snapshot_date).desc(),
            col(PortfolioRecommendationHistory.id).desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    portfolio_id: int | None = None,
    inventory_item_id: int | None = None,
    recommendation_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioRecommendationHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = _history_query(
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioRecommendationHistory.owner_user_id).asc(),
            col(PortfolioRecommendationHistory.snapshot_date).desc(),
            col(PortfolioRecommendationHistory.id).desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioRecommendationHistoryListResponse(items=[_history_read(row) for row in rows], total=total)


def get_recommendation_owner(session: Session, *, owner_user_id: int, recommendation_id: int) -> PortfolioRecommendation:
    return _ensure_owner_recommendation(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)


def get_recommendation_ops(session: Session, *, recommendation_id: int) -> PortfolioRecommendation:
    return _ensure_ops_recommendation(session, recommendation_id=recommendation_id)


def inventory_portfolio_recommendation_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryPortfolioRecommendationTeaser | None:
    row = session.exec(
        select(PortfolioRecommendation)
        .where(
            PortfolioRecommendation.owner_user_id == owner_user_id,
            PortfolioRecommendation.inventory_item_id == inventory_item_id,
            PortfolioRecommendation.recommendation_status == "ACTIVE",
        )
        .order_by(col(PortfolioRecommendation.snapshot_date).desc(), col(PortfolioRecommendation.id).desc())
    ).first()
    if row is None:
        return None
    return InventoryPortfolioRecommendationTeaser(
        recommendation_action=str(row.recommendation_action),
        recommendation_strength=str(row.recommendation_strength),
        confidence_level=str(row.confidence_level),
        risk_level=str(row.risk_level),
        rationale_summary=str(row.rationale_summary),
        estimated_capital_release=str(row.estimated_capital_release) if row.estimated_capital_release is not None else None,
        estimated_liquidity_impact=str(row.estimated_liquidity_impact) if row.estimated_liquidity_impact is not None else None,
        estimated_portfolio_efficiency_gain=str(row.estimated_portfolio_efficiency_gain)
        if row.estimated_portfolio_efficiency_gain is not None
        else None,
        recommendation_status=str(row.recommendation_status),
        recommendation_checksum=str(row.checksum),
    )
