"""P37-07 deterministic grading risk and confidence engine."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ConfidenceFactorSnapshot,
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingRecommendation,
    GradingReconciliationHistory,
    GradingRiskEvidence,
    GradingRiskSnapshot,
    GradingRoiHistory,
    GradingRoiSnapshot,
    GradingSpreadHistory,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    ListingIntelligenceSnapshot,
    MarketFmvSnapshot,
    MarketSaleRecord,
    MarketTrendSnapshot,
    RiskHistory,
    SaleRecord,
    Listing,
    Variant,
)
from app.schemas.grading_risk import (
    ConfidenceFactorSnapshotListResponse,
    ConfidenceFactorSnapshotRead,
    GradingRiskDashboardSummary,
    GradingRiskDetailRead,
    GradingRiskEvidenceListResponse,
    GradingRiskEvidenceRead,
    GradingRiskGeneratePayload,
    GradingRiskListResponse,
    GradingRiskSnapshotRead,
    InventoryGradingRiskBadge,
    RiskHistoryListResponse,
    RiskHistoryRead,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
SCORE_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1.00")
FACTOR_WEIGHTS: dict[str, Decimal] = {
    "liquidity_stability": Decimal("0.20"),
    "spread_stability": Decimal("0.15"),
    "roi_stability": Decimal("0.20"),
    "grader_consistency": Decimal("0.15"),
    "market_depth": Decimal("0.10"),
    "evidence_volume": Decimal("0.10"),
    "reconciliation_history": Decimal("0.10"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_risk_pagination(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _score(value: Any | None) -> Decimal:
    dec = _decimal(value) or ZERO
    if dec < ZERO:
        dec = ZERO
    if dec > Decimal("100.00"):
        dec = Decimal("100.00")
    return dec.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        quant = value.quantize(PCT_QUANT if value.copy_abs() < Decimal("1000") else MONEY_QUANT)
        return format(quant, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def deterministic_checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _range(values: list[Decimal]) -> Decimal:
    if not values:
        return ZERO
    return max(values) - min(values)


def _record_read(row: GradingRiskSnapshot) -> GradingRiskSnapshotRead:
    return GradingRiskSnapshotRead.model_validate(row, from_attributes=True)


def _evidence_read(row: GradingRiskEvidence) -> GradingRiskEvidenceRead:
    return GradingRiskEvidenceRead.model_validate(row, from_attributes=True)


def _factor_read(row: ConfidenceFactorSnapshot) -> ConfidenceFactorSnapshotRead:
    return ConfidenceFactorSnapshotRead.model_validate(row, from_attributes=True)


def _history_read(row: RiskHistory) -> RiskHistoryRead:
    return RiskHistoryRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, row: GradingRiskSnapshot) -> GradingRiskDetailRead:
    rid = int(row.id or 0)
    evidence = session.exec(
        select(GradingRiskEvidence)
        .where(GradingRiskEvidence.grading_risk_snapshot_id == rid)
        .order_by(col(GradingRiskEvidence.created_at).asc(), col(GradingRiskEvidence.id).asc())
    ).all()
    factors = session.exec(
        select(ConfidenceFactorSnapshot)
        .where(ConfidenceFactorSnapshot.grading_risk_snapshot_id == rid)
        .order_by(col(ConfidenceFactorSnapshot.id).asc())
    ).all()
    history = session.exec(
        select(RiskHistory)
        .where(RiskHistory.owner_user_id == row.owner_user_id)
        .where(
            (RiskHistory.grading_candidate_id == row.grading_candidate_id)
            if row.grading_candidate_id is not None
            else col(RiskHistory.inventory_item_id) == row.inventory_item_id
        )
        .order_by(col(RiskHistory.snapshot_date).desc(), col(RiskHistory.id).desc())
    ).all()
    return GradingRiskDetailRead(
        snapshot=_record_read(row),
        evidence=[_evidence_read(item) for item in evidence],
        confidence_factors=[_factor_read(item) for item in factors],
        history=[_history_read(item) for item in history],
    )


def _ensure_owner_snapshot(session: Session, *, owner_user_id: int, snapshot_id: int) -> GradingRiskSnapshot:
    row = session.get(GradingRiskSnapshot, snapshot_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading risk snapshot not found")
    return row


def _ensure_ops_snapshot(session: Session, *, snapshot_id: int) -> GradingRiskSnapshot:
    row = session.get(GradingRiskSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grading risk snapshot not found")
    return row


def _resolve_context(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> tuple[InventoryCopy, int, GradingCandidate | None, GradingRecommendation | None]:
    recommendation: GradingRecommendation | None = None
    candidate: GradingCandidate | None = None
    if recommendation_id is not None:
        recommendation = session.get(GradingRecommendation, recommendation_id)
        if recommendation is None or recommendation.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="grading recommendation not found")
        grading_candidate_id = recommendation.grading_candidate_id
        inventory_item_id = recommendation.inventory_item_id
        canonical_comic_issue_id = recommendation.canonical_comic_issue_id
    if grading_candidate_id is not None:
        candidate = session.get(GradingCandidate, grading_candidate_id)
        if candidate is None or candidate.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="grading candidate not found")
        inventory_item_id = candidate.inventory_item_id
        if canonical_comic_issue_id is None:
            canonical_comic_issue_id = candidate.canonical_comic_issue_id
    if inventory_item_id is None:
        if canonical_comic_issue_id is None:
            raise HTTPException(status_code=400, detail="recommendation_id, grading_candidate_id, or inventory_item_id is required")
        inventory = session.exec(
            select(InventoryCopy)
            .join(Variant, InventoryCopy.variant_id == Variant.id)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(Variant.comic_issue_id == canonical_comic_issue_id)
            .order_by(col(InventoryCopy.id).asc())
        ).first()
    else:
        inventory = session.get(InventoryCopy, inventory_item_id)
        if inventory is None or int(inventory.user_id or 0) != owner_user_id:
            raise HTTPException(status_code=404, detail="inventory item not found")
    if inventory is None:
        raise HTTPException(status_code=404, detail="inventory item not found")
    issue_id = int(session.exec(select(Variant.comic_issue_id).where(Variant.id == inventory.variant_id)).one())
    if candidate is None:
        candidate = session.exec(
            select(GradingCandidate)
            .where(GradingCandidate.owner_user_id == owner_user_id)
            .where(GradingCandidate.inventory_item_id == int(inventory.id or 0))
            .order_by(col(GradingCandidate.created_at).desc(), col(GradingCandidate.id).desc())
        ).first()
    if recommendation is None:
        recommendation = session.exec(
            select(GradingRecommendation)
            .where(GradingRecommendation.owner_user_id == owner_user_id)
            .where(GradingRecommendation.inventory_item_id == int(inventory.id or 0))
            .where(GradingRecommendation.recommendation_status == "ACTIVE")
            .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
        ).first()
    return inventory, issue_id, candidate, recommendation


def _latest_liquidity_snapshot(session: Session, *, owner_user_id: int, inventory_item_id: int, issue_id: int) -> InventoryLiquiditySnapshot | None:
    return session.exec(
        select(InventoryLiquiditySnapshot)
        .where(InventoryLiquiditySnapshot.owner_user_id == owner_user_id)
        .where(
            (InventoryLiquiditySnapshot.inventory_item_id == inventory_item_id)
            | (InventoryLiquiditySnapshot.canonical_comic_issue_id == issue_id)
        )
        .order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc(), col(InventoryLiquiditySnapshot.id).desc())
    ).first()


def _latest_spread_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    target_grader: str | None,
    target_grade: str | None,
) -> GradingSpreadSnapshot | None:
    stmt = (
        select(GradingSpreadSnapshot)
        .where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
        .where(GradingSpreadSnapshot.inventory_item_id == inventory_item_id)
    )
    if target_grader is not None:
        stmt = stmt.where(GradingSpreadSnapshot.target_grader == target_grader)
    if target_grade is not None:
        stmt = stmt.where(GradingSpreadSnapshot.target_grade == target_grade)
    return session.exec(
        stmt.order_by(col(GradingSpreadSnapshot.snapshot_date).desc(), col(GradingSpreadSnapshot.id).desc())
    ).first()


def _latest_roi_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int | None,
    inventory_item_id: int,
    target_grader: str | None,
    target_grade: str | None,
) -> GradingRoiSnapshot | None:
    stmt = select(GradingRoiSnapshot).where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    if candidate_id is not None:
        stmt = stmt.where(GradingRoiSnapshot.grading_candidate_id == candidate_id)
    else:
        stmt = stmt.where(GradingRoiSnapshot.inventory_item_id == inventory_item_id)
    if target_grader is not None:
        stmt = stmt.where(GradingRoiSnapshot.target_grader == target_grader)
    if target_grade is not None:
        stmt = stmt.where(GradingRoiSnapshot.target_grade == target_grade)
    return session.exec(
        stmt.order_by(col(GradingRoiSnapshot.snapshot_date).desc(), col(GradingRoiSnapshot.id).desc())
    ).first()


def _latest_grader_performance(session: Session, *, owner_user_id: int, grader: str | None) -> GraderPerformanceSnapshot | None:
    if grader is None:
        return None
    return session.exec(
        select(GraderPerformanceSnapshot)
        .where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
        .where(GraderPerformanceSnapshot.grader == grader)
        .order_by(col(GraderPerformanceSnapshot.snapshot_date).desc(), col(GraderPerformanceSnapshot.id).desc())
    ).first()


def _latest_listing_intelligence(session: Session, *, owner_user_id: int, inventory_item_id: int, issue_id: int) -> ListingIntelligenceSnapshot | None:
    return session.exec(
        select(ListingIntelligenceSnapshot)
        .where(ListingIntelligenceSnapshot.owner_user_id == owner_user_id)
        .where(
            (ListingIntelligenceSnapshot.inventory_item_id == inventory_item_id)
            | (ListingIntelligenceSnapshot.canonical_comic_issue_id == issue_id)
        )
        .order_by(col(ListingIntelligenceSnapshot.snapshot_date).desc(), col(ListingIntelligenceSnapshot.id).desc())
    ).first()


def _latest_market_fmv(session: Session, *, issue_id: int, grader: str | None, grade: str | None) -> MarketFmvSnapshot | None:
    stmt = select(MarketFmvSnapshot).where(MarketFmvSnapshot.canonical_issue_id == issue_id)
    if grader is not None:
        stmt = stmt.where(MarketFmvSnapshot.grading_company == grader)
    if grade is not None:
        stmt = stmt.where(MarketFmvSnapshot.normalized_grade == grade)
    return session.exec(
        stmt.order_by(col(MarketFmvSnapshot.snapshot_date).desc(), col(MarketFmvSnapshot.id).desc())
    ).first()


def _latest_market_trend(session: Session, *, issue_id: int, grader: str | None, grade: str | None) -> MarketTrendSnapshot | None:
    stmt = select(MarketTrendSnapshot).where(MarketTrendSnapshot.canonical_issue_id == issue_id)
    if grader is not None:
        stmt = stmt.where(MarketTrendSnapshot.grading_company == grader)
    if grade is not None:
        stmt = stmt.where(MarketTrendSnapshot.normalized_grade == grade)
    return session.exec(
        stmt.order_by(col(MarketTrendSnapshot.created_at).desc(), col(MarketTrendSnapshot.id).desc())
    ).first()


def _latest_sale(session: Session, inventory_item_id: int) -> SaleRecord | None:
    return session.exec(
        select(SaleRecord)
        .join(Listing, SaleRecord.listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(SaleRecord.sale_date).desc(), col(SaleRecord.id).desc())
    ).first()


def _latest_market_sale(session: Session, inventory_item_id: int) -> MarketSaleRecord | None:
    return session.exec(
        select(MarketSaleRecord)
        .join(Listing, MarketSaleRecord.source_listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(MarketSaleRecord.sale_date).desc().nullslast(), col(MarketSaleRecord.id).desc())
    ).first()


def _spread_history(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    issue_id: int,
    target_grader: str | None,
    target_grade: str | None,
) -> list[GradingSpreadHistory]:
    stmt = (
        select(GradingSpreadHistory)
        .where(GradingSpreadHistory.owner_user_id == owner_user_id)
        .where(
            (GradingSpreadHistory.inventory_item_id == inventory_item_id)
            | (GradingSpreadHistory.canonical_comic_issue_id == issue_id)
        )
    )
    if target_grader is not None:
        stmt = stmt.where(GradingSpreadHistory.target_grader == target_grader)
    if target_grade is not None:
        stmt = stmt.where(GradingSpreadHistory.target_grade == target_grade)
    return list(
        session.exec(
            stmt.order_by(col(GradingSpreadHistory.snapshot_date).desc(), col(GradingSpreadHistory.id).desc()).limit(5)
        ).all()
    )


def _roi_history(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int | None,
    inventory_item_id: int,
    issue_id: int,
    target_grader: str | None,
    target_grade: str | None,
) -> list[GradingRoiHistory]:
    stmt = select(GradingRoiHistory).where(GradingRoiHistory.owner_user_id == owner_user_id)
    if candidate_id is not None:
        stmt = stmt.where(GradingRoiHistory.grading_candidate_id == candidate_id)
    else:
        stmt = stmt.where(
            (GradingRoiHistory.inventory_item_id == inventory_item_id)
            | (GradingRoiHistory.canonical_comic_issue_id == issue_id)
        )
    if target_grader is not None:
        stmt = stmt.where(GradingRoiHistory.target_grader == target_grader)
    if target_grade is not None:
        stmt = stmt.where(GradingRoiHistory.target_grade == target_grade)
    return list(
        session.exec(
            stmt.order_by(col(GradingRoiHistory.snapshot_date).desc(), col(GradingRoiHistory.id).desc()).limit(5)
        ).all()
    )


def _reconciliation_history(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int | None,
    inventory_item_id: int,
    grader: str | None,
) -> list[GradingReconciliationHistory]:
    stmt = select(GradingReconciliationHistory).where(GradingReconciliationHistory.owner_user_id == owner_user_id)
    if candidate_id is not None:
        stmt = stmt.where(GradingReconciliationHistory.grading_candidate_id == candidate_id)
    else:
        stmt = stmt.where(GradingReconciliationHistory.inventory_item_id == inventory_item_id)
    if grader is not None:
        stmt = stmt.where(GradingReconciliationHistory.target_grader == grader)
    return list(
        session.exec(
            stmt.order_by(col(GradingReconciliationHistory.snapshot_date).desc(), col(GradingReconciliationHistory.id).desc()).limit(5)
        ).all()
    )


def _liquidity_stability(liquidity: InventoryLiquiditySnapshot | None) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if liquidity is None:
        flags.append("missing_liquidity_snapshot")
        return _score(25), flags
    status = str(liquidity.liquidity_status).upper()
    score = {"HIGH": Decimal("90"), "MODERATE": Decimal("70"), "LOW": Decimal("35"), "ILLIQUID": Decimal("15")}.get(
        status,
        Decimal("45"),
    )
    confidence = str(liquidity.liquidity_confidence).upper()
    if confidence == "LOW":
        score -= Decimal("15")
        flags.append("low_liquidity_confidence")
    elif confidence == "MEDIUM":
        score -= Decimal("5")
    stale_rate = _decimal(liquidity.stale_listing_rate_pct) or ZERO
    if stale_rate > Decimal("25"):
        score -= Decimal("15")
        flags.append("stale_liquidity_signal")
    elif stale_rate > Decimal("10"):
        score -= Decimal("5")
    sell_through = _decimal(liquidity.sell_through_rate_pct) or ZERO
    if sell_through < Decimal("20"):
        score -= Decimal("15")
    elif sell_through < Decimal("40"):
        score -= Decimal("5")
    return _score(score), flags


def _spread_stability(spread: GradingSpreadSnapshot | None, rows: list[GradingSpreadHistory]) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if not rows:
        flags.append("thin_spread_history")
        score = Decimal("30")
    else:
        values = [(_decimal(row.spread_pct) or ZERO) for row in rows if row.spread_pct is not None]
        band = _range(values)
        if band <= Decimal("0.25"):
            score = Decimal("90")
        elif band <= Decimal("0.50"):
            score = Decimal("70")
        elif band <= Decimal("1.00"):
            score = Decimal("45")
        else:
            score = Decimal("20")
        if len(values) < 3:
            score -= Decimal("10")
            flags.append("limited_spread_history")
    if spread is not None:
        if str(spread.confidence_level).upper() == "LOW":
            score -= Decimal("10")
        if str(spread.spread_status).upper() in {"NEGATIVE", "WEAK"}:
            score -= Decimal("10")
            flags.append("unstable_spread_economics")
    return _score(score), flags


def _roi_stability(roi: GradingRoiSnapshot | None, rows: list[GradingRoiHistory]) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if not rows:
        flags.append("thin_roi_history")
        score = Decimal("30")
    else:
        values = [
            (_decimal(row.liquidity_adjusted_roi) or _decimal(row.roi_pct) or ZERO)
            for row in rows
            if row.liquidity_adjusted_roi is not None or row.roi_pct is not None
        ]
        band = _range(values)
        if band <= Decimal("0.25"):
            score = Decimal("90")
        elif band <= Decimal("0.50"):
            score = Decimal("70")
        elif band <= Decimal("1.00"):
            score = Decimal("45")
        else:
            score = Decimal("20")
        if len(values) < 3:
            score -= Decimal("10")
            flags.append("limited_roi_history")
    if roi is not None:
        if str(roi.confidence_level).upper() == "LOW":
            score -= Decimal("10")
        if str(roi.roi_status).upper() in {"NEGATIVE", "WEAK"}:
            score -= Decimal("10")
            flags.append("volatile_roi_economics")
    return _score(score), flags


def _grader_consistency(perf: GraderPerformanceSnapshot | None) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if perf is None or perf.submission_count <= 0:
        flags.append("missing_grader_performance")
        return _score(30), flags
    total = Decimal(max(1, perf.submission_count))
    below_ratio = Decimal(perf.below_expectation_count) / total
    above_ratio = Decimal(perf.above_expectation_count) / total
    score = Decimal("85")
    if perf.submission_count < 3:
        score = Decimal("55")
        flags.append("thin_grader_history")
    score -= below_ratio * Decimal("60")
    score += above_ratio * Decimal("10")
    if below_ratio >= Decimal("0.50"):
        flags.append("poor_grader_consistency")
    return _score(score), flags


def _reconciliation_history_score(rows: list[GradingReconciliationHistory]) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if not rows:
        flags.append("missing_reconciliation_history")
        return _score(50), flags
    score = Decimal("75" if len(rows) >= 3 else "55")
    roi_deltas = [(_decimal(row.roi_delta) or ZERO) for row in rows if row.roi_delta is not None]
    variance = _range(roi_deltas)
    if variance > Decimal("0.75"):
        score -= Decimal("25")
        flags.append("reconciliation_roi_variance")
    elif variance > Decimal("0.40"):
        score -= Decimal("10")
    below_count = sum(1 for row in rows if str(row.actual_grade or "").strip() and str(row.expected_grade or "").strip() and (Decimal(str(row.actual_grade)) < Decimal(str(row.expected_grade))))
    if rows and Decimal(below_count) / Decimal(len(rows)) > Decimal("0.50"):
        score -= Decimal("15")
        flags.append("below_expectation_reconciliation_history")
    return _score(score), flags


def _market_depth(fmv: MarketFmvSnapshot | None, trend: MarketTrendSnapshot | None) -> tuple[Decimal, list[str]]:
    flags: list[str] = []
    if fmv is None and trend is None:
        flags.append("missing_market_stability")
        return _score(30), flags
    scores: list[Decimal] = []
    if fmv is not None:
        bucket = str(fmv.confidence_bucket).lower()
        score = {
            "high": Decimal("85"),
            "medium": Decimal("70"),
            "low": Decimal("45"),
            "very_low": Decimal("25"),
        }.get(bucket, Decimal("55"))
        volatility = str(fmv.volatility_bucket).lower()
        if volatility == "stable":
            score += Decimal("10")
        elif volatility == "volatile":
            score -= Decimal("15")
            flags.append("volatile_market_fmv")
        if fmv.stale_data:
            score -= Decimal("10")
            flags.append("stale_market_fmv")
        if fmv.comp_count >= 8:
            score += Decimal("10")
        elif fmv.comp_count >= 4:
            score += Decimal("5")
        else:
            score -= Decimal("5")
        scores.append(_score(score))
    if trend is not None:
        score = Decimal("75")
        if trend.volatility_score >= 60:
            score -= Decimal("25")
            flags.append("volatile_market_trend")
        elif trend.volatility_score >= 40:
            score -= Decimal("10")
        if trend.stale_data:
            score -= Decimal("10")
            flags.append("stale_market_trend")
        if trend.comp_count < 3:
            score -= Decimal("10")
        scores.append(_score(score))
    avg = sum(scores, Decimal("0")) / Decimal(len(scores))
    return _score(avg), flags


def _evidence_volume_score(
    *,
    recommendation: GradingRecommendation | None,
    roi: GradingRoiSnapshot | None,
    spread: GradingSpreadSnapshot | None,
    liquidity: InventoryLiquiditySnapshot | None,
    grader_perf: GraderPerformanceSnapshot | None,
    listing_intel: ListingIntelligenceSnapshot | None,
    fmv: MarketFmvSnapshot | None,
    trend: MarketTrendSnapshot | None,
    sale: SaleRecord | None,
    market_sale: MarketSaleRecord | None,
    spread_history_count: int,
    roi_history_count: int,
    reconciliation_history_count: int,
) -> Decimal:
    source_count = sum(
        1
        for item in (
            recommendation,
            roi,
            spread,
            liquidity,
            grader_perf,
            listing_intel,
            fmv,
            trend,
            sale,
            market_sale,
        )
        if item is not None
    )
    history_points = min(spread_history_count + roi_history_count + reconciliation_history_count, 10)
    score = Decimal("20") + (Decimal(source_count) * Decimal("6")) + (Decimal(history_points) * Decimal("4"))
    return _score(score)


def _overall_confidence_level(confidence_weight: Decimal | None) -> str:
    if confidence_weight is None:
        return "LOW"
    if confidence_weight >= Decimal("0.75"):
        return "HIGH"
    if confidence_weight >= Decimal("0.50"):
        return "MEDIUM"
    return "LOW"


def _overall_risk_level(risk_score: Decimal, evidence_strength_score: Decimal) -> str:
    if evidence_strength_score <= Decimal("30") and risk_score >= Decimal("60"):
        return "EXTREME"
    if risk_score >= Decimal("75"):
        return "EXTREME"
    if risk_score >= Decimal("50"):
        return "HIGH"
    if risk_score >= Decimal("25"):
        return "MEDIUM"
    return "LOW"


def _latest_risk_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int | None = None,
    inventory_item_id: int | None = None,
) -> GradingRiskSnapshot | None:
    stmt = select(GradingRiskSnapshot).where(GradingRiskSnapshot.owner_user_id == owner_user_id)
    if recommendation_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.recommendation_id == recommendation_id)
    elif inventory_item_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.inventory_item_id == inventory_item_id)
    else:
        return None
    return session.exec(
        stmt.order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
    ).first()


def recommendation_risk_attachment(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> dict[str, Any]:
    row = _latest_risk_snapshot(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    if row is None:
        return {
            "grading_risk_snapshot_id": None,
            "overall_risk_level": None,
            "overall_confidence_level": None,
            "risk_adjusted_roi": None,
            "confidence_weight": None,
        }
    return {
        "grading_risk_snapshot_id": int(row.id or 0),
        "overall_risk_level": row.overall_risk_level,
        "overall_confidence_level": row.overall_confidence_level,
        "risk_adjusted_roi": row.risk_adjusted_roi,
        "confidence_weight": row.confidence_weight,
    }


def _append_history(session: Session, *, row: GradingRiskSnapshot) -> None:
    checksum = deterministic_checksum(
        {
            "owner_user_id": row.owner_user_id,
            "grading_candidate_id": row.grading_candidate_id,
            "inventory_item_id": row.inventory_item_id,
            "overall_risk_level": row.overall_risk_level,
            "overall_confidence_level": row.overall_confidence_level,
            "risk_adjusted_roi": row.risk_adjusted_roi,
            "snapshot_date": row.snapshot_date,
        }
    )
    existing = session.exec(
        select(RiskHistory)
        .where(RiskHistory.owner_user_id == row.owner_user_id)
        .where(RiskHistory.grading_candidate_id == row.grading_candidate_id)
        .where(RiskHistory.inventory_item_id == row.inventory_item_id)
        .where(RiskHistory.overall_risk_level == row.overall_risk_level)
        .where(RiskHistory.overall_confidence_level == row.overall_confidence_level)
        .where(RiskHistory.snapshot_date == row.snapshot_date)
        .where(RiskHistory.checksum == checksum)
    ).first()
    if existing is not None:
        return
    session.add(
        RiskHistory(
            owner_user_id=row.owner_user_id,
            grading_candidate_id=row.grading_candidate_id,
            inventory_item_id=row.inventory_item_id,
            overall_risk_level=row.overall_risk_level,
            overall_confidence_level=row.overall_confidence_level,
            risk_adjusted_roi=row.risk_adjusted_roi,
            checksum=checksum,
            snapshot_date=row.snapshot_date,
            created_at=utc_now(),
        )
    )


def generate_grading_risk(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingRiskGeneratePayload,
) -> GradingRiskDetailRead:
    inventory, issue_id, candidate, recommendation = _resolve_context(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=payload.recommendation_id,
        grading_candidate_id=payload.grading_candidate_id,
        inventory_item_id=payload.inventory_item_id,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
    )
    target_grader = recommendation.recommended_grader if recommendation is not None else (candidate.target_grader if candidate is not None else None)
    target_grade = recommendation.recommended_grade_target if recommendation is not None else (candidate.target_grade if candidate is not None else None)
    liquidity = _latest_liquidity_snapshot(session, owner_user_id=owner_user_id, inventory_item_id=int(inventory.id or 0), issue_id=issue_id)
    spread = _latest_spread_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        target_grader=target_grader,
        target_grade=target_grade,
    )
    roi = _latest_roi_snapshot(
        session,
        owner_user_id=owner_user_id,
        candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        target_grader=target_grader,
        target_grade=target_grade,
    )
    grader_perf = _latest_grader_performance(session, owner_user_id=owner_user_id, grader=target_grader)
    listing_intel = _latest_listing_intelligence(session, owner_user_id=owner_user_id, inventory_item_id=int(inventory.id or 0), issue_id=issue_id)
    fmv = _latest_market_fmv(session, issue_id=issue_id, grader=target_grader, grade=target_grade)
    trend = _latest_market_trend(session, issue_id=issue_id, grader=target_grader, grade=target_grade)
    sale = _latest_sale(session, int(inventory.id or 0))
    market_sale = _latest_market_sale(session, int(inventory.id or 0))
    spread_history = _spread_history(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        issue_id=issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
    )
    roi_history = _roi_history(
        session,
        owner_user_id=owner_user_id,
        candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        issue_id=issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
    )
    reconciliation_history = _reconciliation_history(
        session,
        owner_user_id=owner_user_id,
        candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        grader=target_grader,
    )

    warning_flags: list[str] = []
    liquidity_stability, flags = _liquidity_stability(liquidity)
    warning_flags.extend(flags)
    spread_stability, flags = _spread_stability(spread, spread_history)
    warning_flags.extend(flags)
    roi_stability, flags = _roi_stability(roi, roi_history)
    warning_flags.extend(flags)
    grader_consistency, flags = _grader_consistency(grader_perf)
    warning_flags.extend(flags)
    reconciliation_history_score, flags = _reconciliation_history_score(reconciliation_history)
    warning_flags.extend(flags)
    market_depth, flags = _market_depth(fmv, trend)
    warning_flags.extend(flags)
    evidence_volume = _evidence_volume_score(
        recommendation=recommendation,
        roi=roi,
        spread=spread,
        liquidity=liquidity,
        grader_perf=grader_perf,
        listing_intel=listing_intel,
        fmv=fmv,
        trend=trend,
        sale=sale,
        market_sale=market_sale,
        spread_history_count=len(spread_history),
        roi_history_count=len(roi_history),
        reconciliation_history_count=len(reconciliation_history),
    )
    if recommendation is None:
        warning_flags.append("missing_recommendation_context")

    factor_scores = {
        "liquidity_stability": liquidity_stability,
        "spread_stability": spread_stability,
        "roi_stability": roi_stability,
        "grader_consistency": grader_consistency,
        "market_depth": market_depth,
        "evidence_volume": evidence_volume,
        "reconciliation_history": reconciliation_history_score,
    }
    confidence_weight_sum = sum(
        factor_scores[key] * weight for key, weight in FACTOR_WEIGHTS.items()
    )
    confidence_weight = _pct(confidence_weight_sum / Decimal("100"))
    overall_confidence_level = _overall_confidence_level(confidence_weight)

    liquidity_risk = _score(Decimal("100") - liquidity_stability)
    spread_volatility = _score(Decimal("100") - spread_stability)
    roi_volatility = _score(Decimal("100") - roi_stability)
    grader_variability = _score(Decimal("100") - grader_consistency)
    reconciliation_variance = _score(Decimal("100") - reconciliation_history_score)
    market_stability = _score(market_depth)
    evidence_strength = _score(evidence_volume)
    overall_risk_score = (
        liquidity_risk * Decimal("0.20")
        + spread_volatility * Decimal("0.15")
        + roi_volatility * Decimal("0.20")
        + grader_variability * Decimal("0.15")
        + reconciliation_variance * Decimal("0.10")
        + (Decimal("100") - market_stability) * Decimal("0.10")
        + (Decimal("100") - evidence_strength) * Decimal("0.10")
    )
    overall_risk_level = _overall_risk_level(_score(overall_risk_score), evidence_strength)

    base_roi = None
    if recommendation is not None and recommendation.expected_roi is not None:
        base_roi = _pct(recommendation.expected_roi)
    elif roi is not None and roi.estimated_roi_pct is not None:
        base_roi = _pct(roi.estimated_roi_pct)
    risk_adjusted_roi = _pct((base_roi or ZERO) * (confidence_weight or ZERO)) if base_roi is not None and confidence_weight is not None else None
    snapshot_date = payload.snapshot_date or date.today()

    checksum = deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "grading_candidate_id": int(candidate.id or 0) if candidate is not None else None,
            "inventory_item_id": int(inventory.id or 0),
            "canonical_comic_issue_id": issue_id,
            "recommendation_id": int(recommendation.id or 0) if recommendation is not None else None,
            "overall_risk_level": overall_risk_level,
            "overall_confidence_level": overall_confidence_level,
            "liquidity_risk_score": liquidity_risk,
            "spread_volatility_score": spread_volatility,
            "roi_volatility_score": roi_volatility,
            "grader_variability_score": grader_variability,
            "reconciliation_variance_score": reconciliation_variance,
            "market_stability_score": market_stability,
            "evidence_strength_score": evidence_strength,
            "risk_adjusted_roi": risk_adjusted_roi,
            "confidence_weight": confidence_weight,
            "warning_flags_json": warning_flags,
            "snapshot_date": snapshot_date,
        }
    )
    if payload.replay_key:
        existing_replay = session.exec(
            select(GradingRiskSnapshot)
            .where(GradingRiskSnapshot.owner_user_id == owner_user_id)
            .where(GradingRiskSnapshot.replay_key == payload.replay_key)
        ).first()
        if existing_replay is not None:
            return _detail_read(session, existing_replay)
    existing = session.exec(
        select(GradingRiskSnapshot)
        .where(GradingRiskSnapshot.owner_user_id == owner_user_id)
        .where(GradingRiskSnapshot.checksum == checksum)
    ).first()
    if existing is not None:
        return _detail_read(session, existing)

    row = GradingRiskSnapshot(
        owner_user_id=owner_user_id,
        grading_candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        canonical_comic_issue_id=issue_id,
        recommendation_id=int(recommendation.id or 0) if recommendation is not None else None,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        liquidity_risk_score=liquidity_risk,
        spread_volatility_score=spread_volatility,
        roi_volatility_score=roi_volatility,
        grader_variability_score=grader_variability,
        reconciliation_variance_score=reconciliation_variance,
        market_stability_score=market_stability,
        evidence_strength_score=evidence_strength,
        risk_adjusted_roi=risk_adjusted_roi,
        confidence_weight=confidence_weight,
        warning_flags_json=warning_flags,
        evidence_count=0,
        checksum=checksum,
        replay_key=payload.replay_key,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()

    evidence_rows: list[GradingRiskEvidence] = []
    if roi is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="ROI_ENGINE",
                source_id=int(roi.id or 0),
                source_table="grading_roi_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "estimated_roi_pct": roi.estimated_roi_pct,
                        "liquidity_adjusted_roi": roi.liquidity_adjusted_roi,
                        "roi_status": roi.roi_status,
                        "history_count": len(roi_history),
                    }
                ),
                created_at=utc_now(),
            )
        )
    if spread is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="SPREAD_ENGINE",
                source_id=int(spread.id or 0),
                source_table="grading_spread_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "spread_status": spread.spread_status,
                        "estimated_spread_pct": spread.estimated_spread_pct,
                        "history_count": len(spread_history),
                    }
                ),
                created_at=utc_now(),
            )
        )
    if liquidity is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="LIQUIDITY",
                source_id=int(liquidity.id or 0),
                source_table="inventory_liquidity_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "liquidity_status": liquidity.liquidity_status,
                        "liquidity_confidence": liquidity.liquidity_confidence,
                        "sell_through_rate_pct": liquidity.sell_through_rate_pct,
                        "stale_listing_rate_pct": liquidity.stale_listing_rate_pct,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if grader_perf is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="GRADER_PERFORMANCE",
                source_id=int(grader_perf.id or 0),
                source_table="grader_performance_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "submission_count": grader_perf.submission_count,
                        "above_expectation_count": grader_perf.above_expectation_count,
                        "below_expectation_count": grader_perf.below_expectation_count,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if reconciliation_history:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="RECONCILIATION",
                source_id=int(reconciliation_history[0].id or 0),
                source_table="grading_reconciliation_history",
                evidence_value_json=_json_safe(
                    {
                        "history_count": len(reconciliation_history),
                        "roi_delta_range": _range([_decimal(item.roi_delta) or ZERO for item in reconciliation_history if item.roi_delta is not None]),
                    }
                ),
                created_at=utc_now(),
            )
        )
    if market_sale is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="MARKET_SALE",
                source_id=int(market_sale.id or 0),
                source_table="market_sale_record",
                evidence_value_json=_json_safe(
                    {
                        "sale_date": market_sale.sale_date,
                        "sale_price": market_sale.sale_price,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if listing_intel is not None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="LISTING_INTELLIGENCE",
                source_id=int(listing_intel.id or 0),
                source_table="listing_intelligence_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "intelligence_status": listing_intel.intelligence_status,
                        "stale_risk_flag": listing_intel.stale_risk_flag,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if recommendation is None:
        evidence_rows.append(
            GradingRiskEvidence(
                grading_risk_snapshot_id=int(row.id or 0),
                evidence_type="MANUAL_REVIEW",
                source_id=None,
                source_table=None,
                evidence_value_json={"reason": "missing active recommendation context"},
                created_at=utc_now(),
            )
        )
    for evidence in evidence_rows:
        session.add(evidence)
    row.evidence_count = len(evidence_rows)
    session.add(row)

    for factor_key, factor_score in factor_scores.items():
        session.add(
            ConfidenceFactorSnapshot(
                grading_risk_snapshot_id=int(row.id or 0),
                factor_key=factor_key,
                factor_score=factor_score,
                weighting=FACTOR_WEIGHTS[factor_key],
                created_at=utc_now(),
            )
        )

    _append_history(session, row=row)
    session.commit()
    session.refresh(row)
    return _detail_read(session, row)


def _risk_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    overall_risk_level: str | None = None,
    overall_confidence_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GradingRiskSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.inventory_item_id == inventory_item_id)
    if overall_risk_level is not None:
        stmt = stmt.where(GradingRiskSnapshot.overall_risk_level == overall_risk_level)
    if overall_confidence_level is not None:
        stmt = stmt.where(GradingRiskSnapshot.overall_confidence_level == overall_confidence_level)
    if date_from is not None:
        stmt = stmt.where(GradingRiskSnapshot.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(GradingRiskSnapshot.snapshot_date <= date_to)
    return stmt


def _evidence_query(*, owner_user_id: int | None = None, snapshot_id: int | None = None):
    stmt = select(GradingRiskEvidence).join(
        GradingRiskSnapshot,
        GradingRiskEvidence.grading_risk_snapshot_id == GradingRiskSnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.owner_user_id == owner_user_id)
    if snapshot_id is not None:
        stmt = stmt.where(GradingRiskEvidence.grading_risk_snapshot_id == snapshot_id)
    return stmt


def _factor_query(*, owner_user_id: int | None = None, snapshot_id: int | None = None):
    stmt = select(ConfidenceFactorSnapshot).join(
        GradingRiskSnapshot,
        ConfidenceFactorSnapshot.grading_risk_snapshot_id == GradingRiskSnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.owner_user_id == owner_user_id)
    if snapshot_id is not None:
        stmt = stmt.where(ConfidenceFactorSnapshot.grading_risk_snapshot_id == snapshot_id)
    return stmt


def _history_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    overall_risk_level: str | None = None,
    overall_confidence_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(RiskHistory)
    if owner_user_id is not None:
        stmt = stmt.where(RiskHistory.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(RiskHistory.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(RiskHistory.inventory_item_id == inventory_item_id)
    if overall_risk_level is not None:
        stmt = stmt.where(RiskHistory.overall_risk_level == overall_risk_level)
    if overall_confidence_level is not None:
        stmt = stmt.where(RiskHistory.overall_confidence_level == overall_confidence_level)
    if date_from is not None:
        stmt = stmt.where(RiskHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(RiskHistory.snapshot_date <= date_to)
    return stmt


def list_risk_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    overall_risk_level: str | None,
    overall_confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRiskSnapshot], int]:
    stmt = _risk_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_risk_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    overall_risk_level: str | None,
    overall_confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRiskSnapshot], int]:
    stmt = _risk_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_evidence_owner(session: Session, *, owner_user_id: int, snapshot_id: int | None, limit: int, offset: int) -> tuple[list[GradingRiskEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRiskEvidence.created_at).desc(), col(GradingRiskEvidence.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_evidence_ops(session: Session, *, owner_user_id: int | None, snapshot_id: int | None, limit: int, offset: int) -> tuple[list[GradingRiskEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRiskEvidence.created_at).desc(), col(GradingRiskEvidence.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_factors_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[ConfidenceFactorSnapshot], int]:
    stmt = _factor_query(owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(ConfidenceFactorSnapshot.created_at).desc(), col(ConfidenceFactorSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_factors_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[ConfidenceFactorSnapshot], int]:
    stmt = _factor_query(owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(ConfidenceFactorSnapshot.created_at).desc(), col(ConfidenceFactorSnapshot.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    overall_risk_level: str | None,
    overall_confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[RiskHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(RiskHistory.snapshot_date).desc(), col(RiskHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    overall_risk_level: str | None,
    overall_confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[RiskHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(RiskHistory.snapshot_date).desc(), col(RiskHistory.id).desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def get_risk_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> GradingRiskSnapshot:
    return _ensure_owner_snapshot(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)


def get_risk_ops(session: Session, *, snapshot_id: int) -> GradingRiskSnapshot:
    return _ensure_ops_snapshot(session, snapshot_id=snapshot_id)


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingRiskDashboardSummary:
    rows = session.exec(select(GradingRiskSnapshot).where(GradingRiskSnapshot.owner_user_id == owner_user_id)).all()
    adjusted = [row.risk_adjusted_roi for row in rows if row.risk_adjusted_roi is not None]
    return GradingRiskDashboardSummary(
        low_risk_count=sum(1 for row in rows if row.overall_risk_level == "LOW"),
        high_risk_count=sum(1 for row in rows if row.overall_risk_level in {"HIGH", "EXTREME"}),
        high_confidence_count=sum(1 for row in rows if row.overall_confidence_level == "HIGH"),
        low_confidence_count=sum(1 for row in rows if row.overall_confidence_level == "LOW"),
        average_risk_adjusted_roi=_pct(sum(adjusted, Decimal("0")) / Decimal(len(adjusted))) if adjusted else None,
    )


def dashboard_summary_ops(session: Session, *, owner_user_id: int | None = None) -> GradingRiskDashboardSummary:
    stmt = select(GradingRiskSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(GradingRiskSnapshot.owner_user_id == owner_user_id)
    rows = session.exec(stmt).all()
    adjusted = [row.risk_adjusted_roi for row in rows if row.risk_adjusted_roi is not None]
    return GradingRiskDashboardSummary(
        low_risk_count=sum(1 for row in rows if row.overall_risk_level == "LOW"),
        high_risk_count=sum(1 for row in rows if row.overall_risk_level in {"HIGH", "EXTREME"}),
        high_confidence_count=sum(1 for row in rows if row.overall_confidence_level == "HIGH"),
        low_confidence_count=sum(1 for row in rows if row.overall_confidence_level == "LOW"),
        average_risk_adjusted_roi=_pct(sum(adjusted, Decimal("0")) / Decimal(len(adjusted))) if adjusted else None,
    )


def risk_response_from_rows(*, rows: list[GradingRiskSnapshot], total: int, limit: int, offset: int) -> GradingRiskListResponse:
    return GradingRiskListResponse(items=[_record_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def evidence_response_from_rows(*, rows: list[GradingRiskEvidence], total: int, limit: int, offset: int) -> GradingRiskEvidenceListResponse:
    return GradingRiskEvidenceListResponse(items=[_evidence_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def factor_response_from_rows(*, rows: list[ConfidenceFactorSnapshot], total: int, limit: int, offset: int) -> ConfidenceFactorSnapshotListResponse:
    return ConfidenceFactorSnapshotListResponse(items=[_factor_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def history_response_from_rows(*, rows: list[RiskHistory], total: int, limit: int, offset: int) -> RiskHistoryListResponse:
    return RiskHistoryListResponse(items=[_history_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def inventory_grading_risk_badge(session: Session, *, owner_user_id: int, inventory_item_id: int) -> InventoryGradingRiskBadge | None:
    row = _latest_risk_snapshot(session, owner_user_id=owner_user_id, inventory_item_id=inventory_item_id)
    if row is None:
        return None
    return InventoryGradingRiskBadge(
        grading_risk_snapshot_id=int(row.id or 0),
        overall_risk_level=row.overall_risk_level,
        overall_confidence_level=row.overall_confidence_level,
        risk_adjusted_roi=row.risk_adjusted_roi,
        confidence_weight=row.confidence_weight,
        warning_flags_json=row.warning_flags_json,
    )
