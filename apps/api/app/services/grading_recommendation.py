"""P37-06 deterministic grading recommendation engine."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.models import (
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingRecommendation,
    GradingRecommendationEvidence,
    GradingRecommendationHistory,
    GradingRecommendationScenario,
    GradingReconciliationRecord,
    GradingRiskSnapshot,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    MarketSaleRecord,
    SaleRecord,
    Variant,
)
from app.services.catalog_unification_issue_id import (
    effective_catalog_issue_id,
    resolve_legacy_comic_issue_id,
)
from app.schemas.grading_recommendation import (
    GradingRecommendationDashboardSummary,
    GradingRecommendationDetailRead,
    GradingRecommendationEvidenceListResponse,
    GradingRecommendationEvidenceRead,
    GradingRecommendationGeneratePayload,
    GradingRecommendationHistoryListResponse,
    GradingRecommendationHistoryRead,
    GradingRecommendationListResponse,
    GradingRecommendationRead,
    GradingRecommendationScenarioRead,
    InventoryGradingRecommendationBadge,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
SCORE_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1.00")
LOW_LIQUIDITY = {"LOW", "ILLIQUID"}
BAD_LISTING_INTELLIGENCE = {"WEAK", "INCOMPLETE", "INSUFFICIENT_DATA"}
NEGATIVE_ACTIONS = {"HOLD_RAW", "NOT_RECOMMENDED"}
GRADE_STEP_INCREMENT = Decimal("0.2")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_recommendation_pagination(limit: int, offset: int) -> tuple[int, int]:
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
    return dec.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _grade_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _format_grade(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


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


def _record_read(row: GradingRecommendation) -> GradingRecommendationRead:
    return GradingRecommendationRead.model_validate(row, from_attributes=True)


def _record_with_risk_read(session: Session, row: GradingRecommendation) -> GradingRecommendationRead:
    payload = _record_read(row).model_dump()
    risk = session.exec(
        select(GradingRiskSnapshot)
        .where(GradingRiskSnapshot.owner_user_id == row.owner_user_id)
        .where(GradingRiskSnapshot.recommendation_id == row.id)
        .order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
    ).first()
    if risk is not None:
        payload["grading_risk_snapshot_id"] = int(risk.id or 0)
        payload["overall_risk_level"] = risk.overall_risk_level
        payload["overall_confidence_level"] = risk.overall_confidence_level
        payload["risk_adjusted_roi"] = risk.risk_adjusted_roi
        payload["confidence_weight"] = risk.confidence_weight
    return GradingRecommendationRead.model_validate(payload)


def _evidence_read(row: GradingRecommendationEvidence) -> GradingRecommendationEvidenceRead:
    return GradingRecommendationEvidenceRead.model_validate(row, from_attributes=True)


def _scenario_read(row: GradingRecommendationScenario) -> GradingRecommendationScenarioRead:
    return GradingRecommendationScenarioRead.model_validate(row, from_attributes=True)


def _history_read(row: GradingRecommendationHistory) -> GradingRecommendationHistoryRead:
    return GradingRecommendationHistoryRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, row: GradingRecommendation) -> GradingRecommendationDetailRead:
    rid = int(row.id or 0)
    evidence = session.exec(
        select(GradingRecommendationEvidence)
        .where(GradingRecommendationEvidence.grading_recommendation_id == rid)
        .order_by(col(GradingRecommendationEvidence.created_at).asc(), col(GradingRecommendationEvidence.id).asc())
    ).all()
    scenarios = session.exec(
        select(GradingRecommendationScenario)
        .where(GradingRecommendationScenario.grading_recommendation_id == rid)
        .order_by(col(GradingRecommendationScenario.id).asc())
    ).all()
    history = session.exec(
        select(GradingRecommendationHistory)
        .where(GradingRecommendationHistory.owner_user_id == row.owner_user_id)
        .where(
            (GradingRecommendationHistory.grading_candidate_id == row.grading_candidate_id)
            if row.grading_candidate_id is not None
            else col(GradingRecommendationHistory.inventory_item_id) == row.inventory_item_id
        )
        .order_by(col(GradingRecommendationHistory.snapshot_date).desc(), col(GradingRecommendationHistory.id).desc())
    ).all()
    return GradingRecommendationDetailRead(
        recommendation=_record_with_risk_read(session, row),
        evidence=[_evidence_read(item) for item in evidence],
        scenarios=[_scenario_read(item) for item in scenarios],
        history=[_history_read(item) for item in history],
    )


def _ensure_owner_recommendation(session: Session, *, owner_user_id: int, recommendation_id: int) -> GradingRecommendation:
    row = session.get(GradingRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading recommendation not found")
    return row


def _ensure_ops_recommendation(session: Session, *, recommendation_id: int) -> GradingRecommendation:
    row = session.get(GradingRecommendation, recommendation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grading recommendation not found")
    return row


def _inventory_context(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> tuple[InventoryCopy, int | None, int | None, GradingCandidate | None]:
    candidate: GradingCandidate | None = None
    if grading_candidate_id is not None:
        candidate = session.get(GradingCandidate, grading_candidate_id)
        if candidate is None or candidate.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="grading candidate not found")
        inventory_item_id = candidate.inventory_item_id
        if canonical_comic_issue_id is None:
            canonical_comic_issue_id = candidate.canonical_comic_issue_id
    if inventory_item_id is None:
        if canonical_comic_issue_id is not None:
            linked_catalog = effective_catalog_issue_id(
                session,
                catalog_issue_id=None,
                canonical_comic_issue_id=canonical_comic_issue_id,
                inventory_copy_id=None,
            )
            scope_filters = []
            if linked_catalog is not None:
                scope_filters.append(InventoryCopy.catalog_issue_id == linked_catalog)
            scope_filters.append(
                InventoryCopy.variant_id.in_(
                    select(Variant.id).where(Variant.comic_issue_id == canonical_comic_issue_id)
                )
            )
            inventory = session.exec(
                select(InventoryCopy)
                .where(InventoryCopy.user_id == owner_user_id)
                .where(or_(*scope_filters))
                .order_by(col(InventoryCopy.id).asc())
            ).first()
        else:
            raise HTTPException(status_code=400, detail="grading_candidate_id or inventory_item_id is required")
    else:
        inventory = session.get(InventoryCopy, inventory_item_id)
        if inventory is None or int(inventory.user_id or 0) != owner_user_id:
            raise HTTPException(status_code=404, detail="inventory item not found")
    if inventory is None:
        raise HTTPException(status_code=404, detail="inventory item not found")
    catalog_issue_id = effective_catalog_issue_id(
        session,
        catalog_issue_id=(candidate.catalog_issue_id if candidate else None) or inventory.catalog_issue_id,
        canonical_comic_issue_id=canonical_comic_issue_id
        or (candidate.canonical_comic_issue_id if candidate else None),
        inventory_copy_id=int(inventory.id or 0),
    )
    issue_id = resolve_legacy_comic_issue_id(
        session,
        inventory,
        fallback_canonical_comic_issue_id=canonical_comic_issue_id
        or (candidate.canonical_comic_issue_id if candidate else None),
    )
    if candidate is None:
        candidate = session.exec(
            select(GradingCandidate)
            .where(GradingCandidate.owner_user_id == owner_user_id)
            .where(GradingCandidate.inventory_item_id == int(inventory.id or 0))
            .order_by(col(GradingCandidate.created_at).desc(), col(GradingCandidate.id).desc())
        ).first()
    return inventory, issue_id, catalog_issue_id, candidate


def _latest_roi_candidates(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    grading_candidate_id: int | None,
) -> list[GradingRoiSnapshot]:
    stmt = select(GradingRoiSnapshot).where(GradingRoiSnapshot.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingRoiSnapshot.grading_candidate_id == grading_candidate_id)
    elif inventory_item_id is not None:
        stmt = stmt.where(GradingRoiSnapshot.inventory_item_id == inventory_item_id)
    elif canonical_comic_issue_id is not None:
        linked_catalog = effective_catalog_issue_id(
            session,
            catalog_issue_id=None,
            canonical_comic_issue_id=canonical_comic_issue_id,
            inventory_copy_id=None,
        )
        scope = [GradingRoiSnapshot.canonical_comic_issue_id == canonical_comic_issue_id]
        if linked_catalog is not None:
            scope.append(GradingRoiSnapshot.catalog_issue_id == linked_catalog)
        stmt = stmt.where(or_(*scope))
    rows = session.exec(
        stmt.order_by(col(GradingRoiSnapshot.snapshot_date).desc(), col(GradingRoiSnapshot.id).desc())
    ).all()
    latest_by_target: dict[tuple[str, str | None], GradingRoiSnapshot] = {}
    for row in rows:
        latest_by_target.setdefault((row.target_grader, row.target_grade), row)
    return list(latest_by_target.values())


def _best_roi_snapshot(rows: list[GradingRoiSnapshot]) -> GradingRoiSnapshot | None:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            row.liquidity_adjusted_roi or Decimal("-999"),
            row.estimated_roi_pct or Decimal("-999"),
            row.id or 0,
        ),
    )


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


def _latest_reconciliation_record(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int,
    target_grader: str | None,
) -> GradingReconciliationRecord | None:
    stmt = select(GradingReconciliationRecord).where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.grading_candidate_id == grading_candidate_id)
    else:
        stmt = stmt.where(GradingReconciliationRecord.inventory_item_id == inventory_item_id)
    if target_grader is not None:
        stmt = stmt.where(GradingReconciliationRecord.target_grader == target_grader)
    return session.exec(
        stmt.order_by(col(GradingReconciliationRecord.created_at).desc(), col(GradingReconciliationRecord.id).desc())
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


def _liquidity_bonus(liquidity: InventoryLiquiditySnapshot | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if liquidity is None:
        flags.append("missing_liquidity_snapshot")
        return Decimal("0.00"), 2, flags
    status = str(liquidity.liquidity_status).upper()
    if status == "HIGH":
        return Decimal("0.15"), 0, flags
    if status == "MODERATE":
        return Decimal("0.05"), 1, flags
    flags.append(f"liquidity_{status.lower()}")
    return Decimal("-0.20"), 2, flags


def _listing_modifier(listing_intel: ListingIntelligenceSnapshot | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if listing_intel is None:
        flags.append("missing_listing_intelligence")
        return ZERO, 1, flags
    status = str(listing_intel.intelligence_status).upper()
    modifier = ZERO
    risk = 0
    if status == "STRONG":
        modifier += Decimal("0.05")
    elif status == "ADEQUATE":
        modifier += Decimal("0.02")
    else:
        flags.append(f"listing_{status.lower()}")
        risk += 1
    if listing_intel.stale_risk_flag:
        flags.append("listing_stale_risk")
        modifier -= Decimal("0.05")
        risk += 1
    return modifier, risk, flags


def _reconciliation_modifier(reconciliation: GradingReconciliationRecord | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if reconciliation is None:
        return ZERO, 0, flags
    accuracy = str(reconciliation.grading_accuracy_status).upper()
    if accuracy == "ABOVE_EXPECTATION":
        return Decimal("0.08"), 0, flags
    if accuracy == "MET_EXPECTATION":
        return Decimal("0.03"), 0, flags
    if accuracy == "BELOW_EXPECTATION":
        flags.append("below_expectation_history")
        return Decimal("-0.10"), 1, flags
    flags.append("insufficient_reconciliation_history")
    return Decimal("-0.03"), 1, flags


def _grader_modifier(perf: GraderPerformanceSnapshot | None) -> tuple[Decimal, int, list[str]]:
    flags: list[str] = []
    if perf is None or perf.submission_count == 0:
        flags.append("missing_grader_performance")
        return ZERO, 1, flags
    above_ratio = Decimal(perf.above_expectation_count) / Decimal(max(1, perf.submission_count))
    below_ratio = Decimal(perf.below_expectation_count) / Decimal(max(1, perf.submission_count))
    if below_ratio >= Decimal("0.50"):
        flags.append("poor_grader_performance")
        return Decimal("-0.10"), 2, flags
    if above_ratio >= Decimal("0.30"):
        return Decimal("0.08"), 0, flags
    if below_ratio > above_ratio:
        flags.append("mixed_grader_performance")
        return Decimal("-0.04"), 1, flags
    return Decimal("0.03"), 0, flags


def _confidence_score(
    *,
    roi_snapshot: GradingRoiSnapshot | None,
    spread_snapshot: GradingSpreadSnapshot | None,
    liquidity: InventoryLiquiditySnapshot | None,
    reconciliation: GradingReconciliationRecord | None,
    grader_perf: GraderPerformanceSnapshot | None,
    listing_intel: ListingIntelligenceSnapshot | None,
    sale_record: SaleRecord | None,
    market_sale: MarketSaleRecord | None,
    risk_points: int,
) -> Decimal:
    score = Decimal("25.00")
    if roi_snapshot is not None:
        score += Decimal("20.00")
    if spread_snapshot is not None:
        score += Decimal("15.00")
    if liquidity is not None:
        score += Decimal("10.00")
        if str(liquidity.liquidity_confidence).upper() in {"HIGH", "MEDIUM"}:
            score += Decimal("5.00")
    if reconciliation is not None:
        score += Decimal("10.00")
    if grader_perf is not None and grader_perf.submission_count >= 3:
        score += Decimal("10.00")
    if listing_intel is not None:
        score += Decimal("5.00")
        if str(listing_intel.intelligence_status).upper() in {"STRONG", "ADEQUATE"}:
            score += Decimal("5.00")
    if sale_record is not None:
        score += Decimal("5.00")
    if market_sale is not None:
        score += Decimal("5.00")
    score -= Decimal(str(risk_points * 8))
    if score < ZERO:
        score = ZERO
    if score > Decimal("100.00"):
        score = Decimal("100.00")
    return _score(score)


def _risk_level(risk_points: int) -> str:
    if risk_points >= 4:
        return "HIGH"
    if risk_points >= 2:
        return "MEDIUM"
    return "LOW"


def _recommendation_action(
    *,
    expected_roi: Decimal | None,
    liquidity_adjusted_roi: Decimal | None,
    estimated_net_profit: Decimal | None,
    spread_status: str | None,
    confidence_score: Decimal,
    risk_level: str,
    warning_flags: list[str],
) -> str:
    if expected_roi is None or liquidity_adjusted_roi is None:
        return "REVIEW_MANUALLY"
    if estimated_net_profit is not None and estimated_net_profit < ZERO:
        return "NOT_RECOMMENDED"
    if expected_roi < Decimal("0.00") or liquidity_adjusted_roi < Decimal("0.00"):
        return "NOT_RECOMMENDED"
    if risk_level == "HIGH" and confidence_score < Decimal("70.00"):
        return "REVIEW_MANUALLY"
    if spread_status in {"NEGATIVE", "WEAK"} or liquidity_adjusted_roi < Decimal("0.25") or expected_roi < Decimal("0.25"):
        return "HOLD_RAW"
    if "conflicting_evidence" in warning_flags or confidence_score < Decimal("45.00"):
        return "REVIEW_MANUALLY"
    if expected_roi >= Decimal("0.75") and liquidity_adjusted_roi >= Decimal("0.55") and risk_level != "HIGH":
        return "GRADE"
    if expected_roi >= Decimal("0.35") and liquidity_adjusted_roi >= Decimal("0.35") and risk_level == "LOW":
        return "GRADE"
    return "REVIEW_MANUALLY"


def _recommendation_strength(
    *,
    action: str,
    expected_roi: Decimal | None,
    confidence_score: Decimal,
    risk_level: str,
) -> str:
    if action == "GRADE":
        if expected_roi is not None and expected_roi >= Decimal("1.50") and confidence_score >= Decimal("80.00") and risk_level == "LOW":
            return "ELITE"
        if expected_roi is not None and expected_roi >= Decimal("0.75") and confidence_score >= Decimal("65.00"):
            return "STRONG"
        if expected_roi is not None and expected_roi >= Decimal("0.35"):
            return "MODERATE"
        return "WEAK"
    if action == "NOT_RECOMMENDED":
        if confidence_score >= Decimal("75.00") and risk_level == "HIGH":
            return "STRONG"
        return "MODERATE"
    if action == "HOLD_RAW":
        return "MODERATE" if confidence_score >= Decimal("55.00") else "WEAK"
    return "WEAK" if confidence_score < Decimal("55.00") else "MODERATE"


def _scenario_rows(
    *,
    base_grade: str | None,
    estimated_value: Decimal | None,
    expected_roi: Decimal | None,
    action: str,
) -> list[dict[str, Any]]:
    if estimated_value is None and expected_roi is None:
        return []
    grade_value = _grade_decimal(base_grade)
    rows: list[dict[str, Any]] = []
    for scenario_name, multiplier, confidence_modifier, grade_step in (
        ("pessimistic", Decimal("0.90"), Decimal("-15.00"), Decimal("-0.2")),
        ("baseline", Decimal("1.00"), Decimal("0.00"), Decimal("0.0")),
        ("optimistic", Decimal("1.10"), Decimal("10.00"), Decimal("0.2")),
    ):
        scenario_grade = None
        if grade_value is not None:
            adjusted = grade_value + grade_step
            if adjusted < Decimal("0.5"):
                adjusted = Decimal("0.5")
            if adjusted > Decimal("10.0"):
                adjusted = Decimal("10.0")
            scenario_grade = _format_grade(adjusted)
        scenario_value = _money((estimated_value or ZERO) * multiplier) if estimated_value is not None else None
        scenario_roi = _pct((expected_roi or ZERO) * multiplier) if expected_roi is not None else None
        if action in NEGATIVE_ACTIONS and scenario_roi is not None:
            scenario_roi = _pct(scenario_roi)
        rows.append(
            {
                "scenario_name": scenario_name,
                "target_grade": scenario_grade,
                "estimated_value": scenario_value,
                "estimated_roi": scenario_roi,
                "confidence_modifier": confidence_modifier,
            }
        )
    return rows


def _append_history(session: Session, *, row: GradingRecommendation) -> None:
    checksum = deterministic_checksum(
        {
            "owner_user_id": row.owner_user_id,
            "grading_candidate_id": row.grading_candidate_id,
            "inventory_item_id": row.inventory_item_id,
            "recommended_action": row.recommended_action,
            "recommended_grader": row.recommended_grader,
            "recommendation_strength": row.recommendation_strength,
            "confidence_score": row.confidence_score,
            "snapshot_date": row.snapshot_date,
        }
    )
    existing = session.exec(
        select(GradingRecommendationHistory)
        .where(GradingRecommendationHistory.owner_user_id == row.owner_user_id)
        .where(GradingRecommendationHistory.grading_candidate_id == row.grading_candidate_id)
        .where(GradingRecommendationHistory.inventory_item_id == row.inventory_item_id)
        .where(GradingRecommendationHistory.recommended_action == row.recommended_action)
        .where(GradingRecommendationHistory.recommended_grader == row.recommended_grader)
        .where(GradingRecommendationHistory.snapshot_date == row.snapshot_date)
        .where(GradingRecommendationHistory.checksum == checksum)
    ).first()
    if existing is not None:
        return
    session.add(
        GradingRecommendationHistory(
            owner_user_id=row.owner_user_id,
            grading_candidate_id=row.grading_candidate_id,
            inventory_item_id=row.inventory_item_id,
            recommended_action=row.recommended_action,
            recommended_grader=row.recommended_grader,
            recommendation_strength=row.recommendation_strength,
            confidence_score=row.confidence_score,
            snapshot_date=row.snapshot_date,
            checksum=checksum,
            created_at=utc_now(),
        )
    )


def _supersede_previous_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
) -> None:
    stmt = select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id).where(
        GradingRecommendation.recommendation_status == "ACTIVE"
    )
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingRecommendation.grading_candidate_id == grading_candidate_id)
    elif inventory_item_id is not None:
        stmt = stmt.where(GradingRecommendation.inventory_item_id == inventory_item_id)
    elif canonical_comic_issue_id is not None:
        linked_catalog = effective_catalog_issue_id(
            session,
            catalog_issue_id=None,
            canonical_comic_issue_id=canonical_comic_issue_id,
            inventory_copy_id=None,
        )
        scope = [GradingRecommendation.canonical_comic_issue_id == canonical_comic_issue_id]
        if linked_catalog is not None:
            scope.append(GradingRecommendation.catalog_issue_id == linked_catalog)
        stmt = stmt.where(or_(*scope))
    rows = session.exec(stmt).all()
    for row in rows:
        row.recommendation_status = "SUPERSEDED"
        session.add(row)


def generate_grading_recommendation(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingRecommendationGeneratePayload,
) -> GradingRecommendationDetailRead:
    inventory, issue_id, catalog_issue_id, candidate = _inventory_context(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=payload.grading_candidate_id,
        inventory_item_id=payload.inventory_item_id,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
    )
    roi_rows = _latest_roi_candidates(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        canonical_comic_issue_id=issue_id,
        grading_candidate_id=int(candidate.id or 0) if candidate is not None else None,
    )
    best_roi = _best_roi_snapshot(roi_rows)
    selected_grader = best_roi.target_grader if best_roi is not None else (candidate.target_grader if candidate is not None else None)
    selected_grade = best_roi.target_grade if best_roi is not None else (candidate.target_grade if candidate is not None else None)
    spread = _latest_spread_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        target_grader=selected_grader,
        target_grade=selected_grade,
    )
    liquidity = _latest_liquidity_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        issue_id=issue_id,
    )
    reconciliation = _latest_reconciliation_record(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        target_grader=selected_grader,
    )
    grader_perf = _latest_grader_performance(session, owner_user_id=owner_user_id, grader=selected_grader)
    listing_intel = _latest_listing_intelligence(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        issue_id=issue_id,
    )
    sale_record = _latest_sale(session, int(inventory.id or 0))
    market_sale = _latest_market_sale(session, int(inventory.id or 0))

    base_expected_roi = (
        _pct(best_roi.estimated_roi_pct)
        if best_roi is not None and best_roi.estimated_roi_pct is not None
        else _pct(candidate.estimated_roi) if candidate is not None and candidate.estimated_roi is not None else None
    )
    liquidity_adjusted_roi = (
        _pct(best_roi.liquidity_adjusted_roi) if best_roi is not None and best_roi.liquidity_adjusted_roi is not None else base_expected_roi
    )
    estimated_net_profit = (
        _money(best_roi.estimated_net_profit) if best_roi is not None and best_roi.estimated_net_profit is not None else None
    )
    estimated_total_cost = (
        _money(best_roi.estimated_total_cost)
        if best_roi is not None and best_roi.estimated_total_cost is not None
        else _money(candidate.estimated_grading_cost) if candidate is not None and candidate.estimated_grading_cost is not None else None
    )

    warning_flags: list[str] = []
    risk_points = 0
    roi_modifier = ZERO
    if best_roi is None:
        warning_flags.append("missing_roi_snapshot")
        risk_points += 2
    else:
        if best_roi.roi_status in {"NEGATIVE", "WEAK"}:
            warning_flags.append(f"roi_{best_roi.roi_status.lower()}")
            risk_points += 2 if best_roi.roi_status == "NEGATIVE" else 1
        if best_roi.confidence_level == "LOW":
            warning_flags.append("low_roi_confidence")
            risk_points += 1

    if spread is None:
        warning_flags.append("missing_spread_snapshot")
        risk_points += 1
    elif spread.spread_status in {"NEGATIVE", "WEAK"}:
        warning_flags.append(f"spread_{spread.spread_status.lower()}")
        risk_points += 1

    liq_modifier, liq_risk, liq_flags = _liquidity_bonus(liquidity)
    warning_flags.extend(liq_flags)
    risk_points += liq_risk
    roi_modifier += liq_modifier

    listing_modifier, listing_risk, listing_flags = _listing_modifier(listing_intel)
    warning_flags.extend(listing_flags)
    risk_points += listing_risk
    roi_modifier += listing_modifier

    rec_modifier, rec_risk, rec_flags = _reconciliation_modifier(reconciliation)
    warning_flags.extend(rec_flags)
    risk_points += rec_risk
    roi_modifier += rec_modifier

    grader_modifier, grader_risk, grader_flags = _grader_modifier(grader_perf)
    warning_flags.extend(grader_flags)
    risk_points += grader_risk
    roi_modifier += grader_modifier

    if best_roi is not None and best_roi.estimated_roi_pct is not None:
        adjusted_expected_roi = _pct((best_roi.estimated_roi_pct or ZERO) + roi_modifier)
    else:
        adjusted_expected_roi = base_expected_roi
    if adjusted_expected_roi is not None:
        if liquidity_adjusted_roi is not None:
            liquidity_adjusted_roi = _pct(liquidity_adjusted_roi + (roi_modifier / Decimal("2")))
        else:
            liquidity_adjusted_roi = adjusted_expected_roi
    if candidate is None and best_roi is None:
        warning_flags.append("missing_candidate_context")
        risk_points += 2
    if reconciliation is not None and best_roi is not None:
        if best_roi.target_grade is not None and reconciliation.expected_grade is not None and best_roi.target_grade != reconciliation.expected_grade:
            warning_flags.append("conflicting_evidence")
            risk_points += 1

    confidence_score = _confidence_score(
        roi_snapshot=best_roi,
        spread_snapshot=spread,
        liquidity=liquidity,
        reconciliation=reconciliation,
        grader_perf=grader_perf,
        listing_intel=listing_intel,
        sale_record=sale_record,
        market_sale=market_sale,
        risk_points=risk_points,
    )
    risk_level = _risk_level(risk_points)
    action = _recommendation_action(
        expected_roi=adjusted_expected_roi,
        liquidity_adjusted_roi=liquidity_adjusted_roi,
        estimated_net_profit=estimated_net_profit,
        spread_status=spread.spread_status if spread is not None else None,
        confidence_score=confidence_score,
        risk_level=risk_level,
        warning_flags=warning_flags,
    )
    strength = _recommendation_strength(
        action=action,
        expected_roi=adjusted_expected_roi,
        confidence_score=confidence_score,
        risk_level=risk_level,
    )
    rationale_bits: list[str] = []
    if action == "GRADE":
        rationale_bits.append("grading economics are compelling")
    elif action == "HOLD_RAW":
        rationale_bits.append("raw hold is safer than grading")
    elif action == "NOT_RECOMMENDED":
        rationale_bits.append("grading is economically weak or negative")
    else:
        rationale_bits.append("evidence conflicts require manual review")
    if adjusted_expected_roi is not None:
        rationale_bits.append(f"expected ROI {adjusted_expected_roi}")
    if liquidity_adjusted_roi is not None:
        rationale_bits.append(f"liquidity-adjusted ROI {liquidity_adjusted_roi}")
    if risk_level == "HIGH":
        rationale_bits.append("risk remains high")
    elif risk_level == "LOW":
        rationale_bits.append("risk is manageable")
    rationale_summary = ". ".join(rationale_bits) + "."

    snapshot_date = payload.snapshot_date or date.today()
    checksum = deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "grading_candidate_id": int(candidate.id or 0) if candidate is not None else None,
            "inventory_item_id": int(inventory.id or 0),
            "canonical_comic_issue_id": issue_id,
            "recommended_action": action,
            "recommended_grader": selected_grader,
            "recommended_grade_target": selected_grade,
            "expected_roi": adjusted_expected_roi,
            "liquidity_adjusted_roi": liquidity_adjusted_roi,
            "estimated_net_profit": estimated_net_profit,
            "estimated_total_cost": estimated_total_cost,
            "confidence_score": confidence_score,
            "recommendation_strength": strength,
            "risk_level": risk_level,
            "warning_flags_json": warning_flags,
            "snapshot_date": snapshot_date,
        }
    )
    if payload.replay_key:
        existing_replay = session.exec(
            select(GradingRecommendation)
            .where(GradingRecommendation.owner_user_id == owner_user_id)
            .where(GradingRecommendation.replay_key == payload.replay_key)
        ).first()
        if existing_replay is not None:
            return _detail_read(session, existing_replay)
    existing = session.exec(
        select(GradingRecommendation)
        .where(GradingRecommendation.owner_user_id == owner_user_id)
        .where(GradingRecommendation.checksum == checksum)
    ).first()
    if existing is not None:
        return _detail_read(session, existing)

    _supersede_previous_recommendations(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        canonical_comic_issue_id=issue_id,
    )

    record = GradingRecommendation(
        owner_user_id=owner_user_id,
        grading_candidate_id=int(candidate.id or 0) if candidate is not None else None,
        inventory_item_id=int(inventory.id or 0),
        canonical_comic_issue_id=issue_id,
        catalog_issue_id=catalog_issue_id,
        recommended_action=action,
        recommended_grader=selected_grader,
        recommended_grade_target=selected_grade,
        expected_roi=adjusted_expected_roi,
        liquidity_adjusted_roi=liquidity_adjusted_roi,
        estimated_net_profit=estimated_net_profit,
        estimated_total_cost=estimated_total_cost,
        confidence_score=confidence_score,
        recommendation_strength=strength,
        risk_level=risk_level,
        recommendation_status="ACTIVE",
        rationale_summary=rationale_summary,
        warning_flags_json=warning_flags,
        evidence_count=0,
        checksum=checksum,
        replay_key=payload.replay_key,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(record)
    session.flush()

    evidence_rows: list[GradingRecommendationEvidence] = []
    if best_roi is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="ROI_ENGINE",
                source_id=int(best_roi.id or 0),
                source_table="grading_roi_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "target_grader": best_roi.target_grader,
                        "target_grade": best_roi.target_grade,
                        "roi_status": best_roi.roi_status,
                        "estimated_roi_pct": best_roi.estimated_roi_pct,
                        "liquidity_adjusted_roi": best_roi.liquidity_adjusted_roi,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if spread is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="SPREAD_ENGINE",
                source_id=int(spread.id or 0),
                source_table="grading_spread_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "spread_status": spread.spread_status,
                        "estimated_net_upside": spread.estimated_net_upside,
                        "liquidity_adjusted_upside": spread.liquidity_adjusted_upside,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if liquidity is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
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
    if reconciliation is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="RECONCILIATION",
                source_id=int(reconciliation.id or 0),
                source_table="grading_reconciliation_record",
                evidence_value_json=_json_safe(
                    {
                        "final_grade": reconciliation.final_grade,
                        "grading_accuracy_status": reconciliation.grading_accuracy_status,
                        "roi_delta": reconciliation.roi_delta,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if grader_perf is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="GRADER_PERFORMANCE",
                source_id=int(grader_perf.id or 0),
                source_table="grader_performance_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "grader": grader_perf.grader,
                        "submission_count": grader_perf.submission_count,
                        "above_expectation_count": grader_perf.above_expectation_count,
                        "below_expectation_count": grader_perf.below_expectation_count,
                        "average_roi_delta": grader_perf.average_roi_delta,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if listing_intel is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="LISTING_INTELLIGENCE",
                source_id=int(listing_intel.id or 0),
                source_table="listing_intelligence_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "intelligence_status": listing_intel.intelligence_status,
                        "completeness_score": listing_intel.completeness_score,
                        "export_readiness_score": listing_intel.export_readiness_score,
                        "stale_risk_flag": listing_intel.stale_risk_flag,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if sale_record is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="SALES_LEDGER",
                source_id=int(sale_record.id or 0),
                source_table="sale_record",
                evidence_value_json=_json_safe(
                    {
                        "sale_date": sale_record.sale_date,
                        "gross_sale_amount": sale_record.gross_sale_amount,
                        "net_proceeds_amount": sale_record.net_proceeds_amount,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if market_sale is not None:
        evidence_rows.append(
            GradingRecommendationEvidence(
                grading_recommendation_id=int(record.id or 0),
                evidence_type="MARKET_SALE",
                source_id=int(market_sale.id or 0),
                source_table="market_sale_record",
                evidence_value_json=_json_safe(
                    {
                        "sale_date": market_sale.sale_date,
                        "sale_price": market_sale.sale_price,
                        "normalized_grade": market_sale.normalized_grade,
                    }
                ),
                created_at=utc_now(),
            )
        )
    for evidence in evidence_rows:
        session.add(evidence)
    record.evidence_count = len(evidence_rows)
    session.add(record)

    for scenario in _scenario_rows(
        base_grade=selected_grade,
        estimated_value=best_roi.graded_fmv_amount if best_roi is not None else candidate.estimated_graded_value if candidate is not None else None,
        expected_roi=adjusted_expected_roi,
        action=action,
    ):
        session.add(
            GradingRecommendationScenario(
                grading_recommendation_id=int(record.id or 0),
                scenario_name=str(scenario["scenario_name"]),
                target_grade=scenario["target_grade"],
                estimated_value=scenario["estimated_value"],
                estimated_roi=scenario["estimated_roi"],
                confidence_modifier=scenario["confidence_modifier"],
                created_at=utc_now(),
            )
        )

    _append_history(session, row=record)
    session.commit()
    session.refresh(record)
    return _detail_read(session, record)


def _recommendation_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    recommended_action: str | None = None,
    recommendation_strength: str | None = None,
    confidence_score: Decimal | None = None,
    risk_level: str | None = None,
    recommended_grader: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GradingRecommendation)
    if owner_user_id is not None:
        stmt = stmt.where(GradingRecommendation.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingRecommendation.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingRecommendation.inventory_item_id == inventory_item_id)
    if recommended_action is not None:
        stmt = stmt.where(GradingRecommendation.recommended_action == recommended_action)
    if recommendation_strength is not None:
        stmt = stmt.where(GradingRecommendation.recommendation_strength == recommendation_strength)
    if confidence_score is not None:
        stmt = stmt.where(GradingRecommendation.confidence_score >= confidence_score)
    if risk_level is not None:
        stmt = stmt.where(GradingRecommendation.risk_level == risk_level)
    if recommended_grader is not None:
        stmt = stmt.where(GradingRecommendation.recommended_grader == recommended_grader)
    if date_from is not None:
        stmt = stmt.where(GradingRecommendation.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(GradingRecommendation.snapshot_date <= date_to)
    return stmt


def _evidence_query(*, owner_user_id: int | None = None, recommendation_id: int | None = None):
    stmt = select(GradingRecommendationEvidence).join(
        GradingRecommendation,
        GradingRecommendationEvidence.grading_recommendation_id == GradingRecommendation.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(GradingRecommendation.owner_user_id == owner_user_id)
    if recommendation_id is not None:
        stmt = stmt.where(GradingRecommendationEvidence.grading_recommendation_id == recommendation_id)
    return stmt


def _history_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    recommended_action: str | None = None,
    recommended_grader: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GradingRecommendationHistory)
    if owner_user_id is not None:
        stmt = stmt.where(GradingRecommendationHistory.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingRecommendationHistory.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingRecommendationHistory.inventory_item_id == inventory_item_id)
    if recommended_action is not None:
        stmt = stmt.where(GradingRecommendationHistory.recommended_action == recommended_action)
    if recommended_grader is not None:
        stmt = stmt.where(GradingRecommendationHistory.recommended_grader == recommended_grader)
    if date_from is not None:
        stmt = stmt.where(GradingRecommendationHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(GradingRecommendationHistory.snapshot_date <= date_to)
    return stmt


def list_recommendations_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    recommended_action: str | None,
    recommendation_strength: str | None,
    confidence_score: Decimal | None,
    risk_level: str | None,
    recommended_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendation], int]:
    stmt = _recommendation_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommendation_strength=recommendation_strength,
        confidence_score=confidence_score,
        risk_level=risk_level,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_recommendations_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    recommended_action: str | None,
    recommendation_strength: str | None,
    confidence_score: Decimal | None,
    risk_level: str | None,
    recommended_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendation], int]:
    stmt = _recommendation_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommendation_strength=recommendation_strength,
        confidence_score=confidence_score,
        risk_level=risk_level,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendationEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendationEvidence.created_at).desc(), col(GradingRecommendationEvidence.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    recommendation_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendationEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendationEvidence.created_at).desc(), col(GradingRecommendationEvidence.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    recommended_action: str | None,
    recommended_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendationHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendationHistory.snapshot_date).desc(), col(GradingRecommendationHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    recommended_action: str | None,
    recommended_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingRecommendationHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingRecommendationHistory.snapshot_date).desc(), col(GradingRecommendationHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def get_recommendation_owner(session: Session, *, owner_user_id: int, recommendation_id: int) -> GradingRecommendation:
    return _ensure_owner_recommendation(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)


def get_recommendation_ops(session: Session, *, recommendation_id: int) -> GradingRecommendation:
    return _ensure_ops_recommendation(session, recommendation_id=recommendation_id)


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingRecommendationDashboardSummary:
    rows = session.exec(select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)).all()
    active = [row for row in rows if row.recommendation_status == "ACTIVE"]
    expected = [row.expected_roi for row in active if row.expected_roi is not None]
    return GradingRecommendationDashboardSummary(
        grade_recommendation_count=sum(1 for row in active if row.recommended_action == "GRADE"),
        hold_raw_count=sum(1 for row in active if row.recommended_action == "HOLD_RAW"),
        elite_opportunity_count=sum(1 for row in active if row.recommendation_strength == "ELITE"),
        high_risk_count=sum(1 for row in active if row.risk_level == "HIGH"),
        average_expected_roi=_pct(sum(expected, Decimal("0")) / Decimal(len(expected))) if expected else None,
    )


def dashboard_summary_ops(session: Session, *, owner_user_id: int | None = None) -> GradingRecommendationDashboardSummary:
    stmt = select(GradingRecommendation)
    if owner_user_id is not None:
        stmt = stmt.where(GradingRecommendation.owner_user_id == owner_user_id)
    rows = session.exec(stmt).all()
    active = [row for row in rows if row.recommendation_status == "ACTIVE"]
    expected = [row.expected_roi for row in active if row.expected_roi is not None]
    return GradingRecommendationDashboardSummary(
        grade_recommendation_count=sum(1 for row in active if row.recommended_action == "GRADE"),
        hold_raw_count=sum(1 for row in active if row.recommended_action == "HOLD_RAW"),
        elite_opportunity_count=sum(1 for row in active if row.recommendation_strength == "ELITE"),
        high_risk_count=sum(1 for row in active if row.risk_level == "HIGH"),
        average_expected_roi=_pct(sum(expected, Decimal("0")) / Decimal(len(expected))) if expected else None,
    )


def recommendations_response_from_rows(
    *,
    rows: list[GradingRecommendation],
    total: int,
    limit: int,
    offset: int,
) -> GradingRecommendationListResponse:
    return GradingRecommendationListResponse(
        items=[_record_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def recommendations_response_from_rows_with_risk(
    session: Session,
    *,
    rows: list[GradingRecommendation],
    total: int,
    limit: int,
    offset: int,
) -> GradingRecommendationListResponse:
    return GradingRecommendationListResponse(
        items=[_record_with_risk_read(session, row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def evidence_response_from_rows(
    *,
    rows: list[GradingRecommendationEvidence],
    total: int,
    limit: int,
    offset: int,
) -> GradingRecommendationEvidenceListResponse:
    return GradingRecommendationEvidenceListResponse(
        items=[_evidence_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def history_response_from_rows(
    *,
    rows: list[GradingRecommendationHistory],
    total: int,
    limit: int,
    offset: int,
) -> GradingRecommendationHistoryListResponse:
    return GradingRecommendationHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def inventory_grading_recommendation_badge(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryGradingRecommendationBadge | None:
    row = session.exec(
        select(GradingRecommendation)
        .where(GradingRecommendation.owner_user_id == owner_user_id)
        .where(GradingRecommendation.inventory_item_id == inventory_item_id)
        .where(GradingRecommendation.recommendation_status == "ACTIVE")
        .order_by(col(GradingRecommendation.snapshot_date).desc(), col(GradingRecommendation.id).desc())
    ).first()
    if row is None:
        return None
    risk = session.exec(
        select(GradingRiskSnapshot)
        .where(GradingRiskSnapshot.owner_user_id == owner_user_id)
        .where(GradingRiskSnapshot.recommendation_id == row.id)
        .order_by(col(GradingRiskSnapshot.snapshot_date).desc(), col(GradingRiskSnapshot.id).desc())
    ).first()
    return InventoryGradingRecommendationBadge(
        grading_recommendation_id=int(row.id or 0),
        recommended_action=row.recommended_action,
        recommended_grader=row.recommended_grader,
        recommended_grade_target=row.recommended_grade_target,
        confidence_score=row.confidence_score,
        overall_confidence_level=risk.overall_confidence_level if risk is not None else None,
        risk_level=row.risk_level,
        grading_risk_snapshot_id=int(risk.id or 0) if risk is not None else None,
        overall_risk_level=risk.overall_risk_level if risk is not None else None,
        risk_adjusted_roi=risk.risk_adjusted_roi if risk is not None else None,
        recommendation_strength=row.recommendation_strength,
        rationale_summary=row.rationale_summary,
    )
