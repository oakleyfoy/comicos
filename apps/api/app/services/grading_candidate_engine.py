"""P72-01 grading decision candidate discovery (read-only; no inventory mutation)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import InventoryCopy
from app.services.authoritative_fmv_service import get_authoritative_fmv, latest_p68_snapshot_for_copy
from app.services.grade_probability_engine import estimate_grade_probabilities
from app.services.grading_cost_service import estimate_grading_costs
from app.services.grading_roi_service import calculate_grading_roi
from app.services.p71_sell_context import load_sell_intel_contexts
from app.services.pressing_intelligence_service import DO_NOT_PRESS, PRESS, recommend_pressing
from app.services.sell_candidate_engine import _split_identity_key

REC_GRADE = "GRADE"
REC_PRESS_AND_GRADE = "PRESS_AND_GRADE"
REC_WATCH = "WATCH"
REC_DO_NOT_GRADE = "DO_NOT_GRADE"


@dataclass(frozen=True)
class GradingDecisionCandidate:
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    raw_fmv: float
    blended_fmv: float
    liquidity_score: float
    market_confidence: float
    sales_velocity: float
    sell_intelligence_score: float
    recommendation: str
    pressing_recommendation: str
    expected_grade: str
    grade_probabilities: dict[str, float]
    expected_graded_fmv: float
    expected_total_cost: float
    expected_profit: float
    expected_roi_pct: float
    grading_score: float
    confidence: float
    primary_reason: str
    factors_json: dict


def _is_raw_copy(copy: InventoryCopy) -> bool:
    status = (copy.grade_status or "raw").strip().lower()
    return status in {"", "raw", "ungraded"}


def _sell_score_for_copy(ctx_by_id: dict, copy_id: int) -> float:
    ctx = ctx_by_id.get(copy_id)
    if ctx is None:
        return 0.0
    if ctx.market_timing_signal in {"SELL_NOW", "SELL_SOON"}:
        return max(0.0, 40.0 - ctx.unrealized_gain_pct * 0.05)
    return min(100.0, ctx.fmv_confidence * 30 + ctx.liquidity_score * 0.35)


def _recommendation_and_score(
    *,
    roi_pct: float,
    profit: float,
    raw_fmv: float,
    liquidity: float,
    confidence: float,
    press: str,
    sell_score: float,
) -> tuple[str, float, str]:
    score = 0.0
    if roi_pct >= 100:
        score += 40
    elif roi_pct >= 50:
        score += 28
    elif roi_pct >= 25:
        score += 18
    elif roi_pct > 0:
        score += 8
    else:
        score -= 15
    score += min(25, liquidity * 0.25)
    score += min(15, confidence * 15)
    score += min(10, sell_score * 0.1)
    if profit < 5:
        score -= 12
    if raw_fmv < 8:
        score -= 20
    score = round(max(0.0, min(100.0, score)), 1)

    if score >= 75 and roi_pct >= 50 and profit >= 15:
        rec = REC_PRESS_AND_GRADE if press == PRESS else REC_GRADE
        reason = "Strong grading ROI with adequate market depth."
    elif score >= 55 and roi_pct >= 25:
        rec = REC_PRESS_AND_GRADE if press == PRESS and roi_pct >= 40 else REC_GRADE
        reason = "Positive expected ROI supports grading."
    elif score >= 35:
        rec = REC_WATCH
        reason = "Marginal ROI; monitor market before submitting."
    else:
        rec = REC_DO_NOT_GRADE
        reason = "Insufficient ROI or market support for grading."
    return rec, score, reason


def build_grading_decision_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    ctx_by_id: dict | None = None,
) -> GradingDecisionCandidate | None:
    if not _is_raw_copy(copy):
        return None
    cid = int(copy.id or 0)
    auth = get_authoritative_fmv(session, owner_user_id=owner_user_id, inventory_copy_id=cid)
    snap = latest_p68_snapshot_for_copy(session, owner_user_id=owner_user_id, inventory_copy_id=cid)
    if auth and auth.raw_fmv is not None and auth.raw_fmv > 0:
        raw_fmv = float(auth.raw_fmv)
    elif auth:
        raw_fmv = float(auth.authoritative_fmv)
    else:
        raw_fmv = float(copy.current_fmv or 0)
    market_graded_fmv = float(snap.graded_fmv) if snap and snap.graded_fmv else None
    if raw_fmv <= 0:
        return None
    blended = float(auth.blended_fmv or raw_fmv) if auth else raw_fmv
    liquidity = float(auth.liquidity_score if auth else 0)
    confidence = float(auth.confidence if auth else 0.45)
    velocity = float((auth and auth.sales_count) or 0) / 3.0

    pub, series, issue, _ = _split_identity_key(copy.metadata_identity_key)
    title = series or (copy.metadata_identity_key or f"Copy {cid}")
    release_year = copy.release_year
    probs = estimate_grade_probabilities(
        publisher=pub,
        release_year=release_year,
        ownership_source=copy.order_status,
        condition_notes=copy.condition_notes,
    )
    press_pre = recommend_pressing(
        raw_fmv=raw_fmv,
        liquidity_score=liquidity,
        roi=calculate_grading_roi(
            raw_fmv=raw_fmv,
            blended_fmv=blended,
            graded_fmv=market_graded_fmv,
            probabilities=probs,
            costs=estimate_grading_costs(raw_fmv=raw_fmv, release_year=release_year, include_press=False),
        ),
        condition_notes=copy.condition_notes,
        expected_roi_pct=0,
    )
    costs = estimate_grading_costs(
        raw_fmv=raw_fmv,
        release_year=release_year,
        include_press=press_pre.recommendation == PRESS,
        include_cleaning=press_pre.recommendation == PRESS,
    )
    roi = calculate_grading_roi(
        raw_fmv=raw_fmv,
        blended_fmv=blended,
        graded_fmv=market_graded_fmv,
        probabilities=probs,
        costs=costs,
    )
    press = recommend_pressing(
        raw_fmv=raw_fmv,
        liquidity_score=liquidity,
        roi=roi,
        condition_notes=copy.condition_notes,
        expected_roi_pct=roi.expected_roi_pct,
        release_year=release_year,
    )
    if press.recommendation == PRESS and costs.pressing_fee == 0:
        costs = estimate_grading_costs(
            raw_fmv=raw_fmv,
            release_year=release_year,
            include_press=True,
            include_cleaning=True,
        )
        roi = calculate_grading_roi(
            raw_fmv=raw_fmv,
            blended_fmv=blended,
            graded_fmv=market_graded_fmv,
            probabilities=probs,
            costs=costs,
        )

    ctx_map = ctx_by_id or {c.copy_id: c for c in load_sell_intel_contexts(session, owner_user_id=owner_user_id)}
    sell_score = _sell_score_for_copy(ctx_map, cid)
    rec, grading_score, reason = _recommendation_and_score(
        roi_pct=roi.expected_roi_pct,
        profit=roi.expected_profit,
        raw_fmv=raw_fmv,
        liquidity=liquidity,
        confidence=confidence,
        press=press.recommendation,
        sell_score=sell_score,
    )

    return GradingDecisionCandidate(
        inventory_copy_id=cid,
        title=title,
        publisher=pub,
        issue_number=issue,
        raw_fmv=roi.raw_fmv,
        blended_fmv=round(blended, 2),
        liquidity_score=round(liquidity, 2),
        market_confidence=round(confidence, 3),
        sales_velocity=round(velocity, 3),
        sell_intelligence_score=round(sell_score, 2),
        recommendation=rec,
        pressing_recommendation=press.recommendation,
        expected_grade=probs.expected_grade_label,
        grade_probabilities=probs.as_dict(),
        expected_graded_fmv=roi.expected_graded_fmv,
        expected_total_cost=roi.total_cost,
        expected_profit=roi.expected_profit,
        expected_roi_pct=roi.expected_roi_pct,
        grading_score=grading_score,
        confidence=round(min(0.95, probs.confidence * 0.6 + confidence * 0.4), 3),
        primary_reason=reason,
        factors_json={
            "pressing_rationale": press.rationale,
            "roi_calculation": roi.calculation_json,
            "grade_probability_factors": probs.factors_json,
            "cost_tier": costs.grading_tier,
        },
    )


def discover_grading_candidates(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
) -> list[GradingDecisionCandidate]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    ctx_by_id = {c.copy_id: c for c in load_sell_intel_contexts(session, owner_user_id=owner_user_id)}
    candidates: list[GradingDecisionCandidate] = []
    for copy in copies:
        row = build_grading_decision_for_copy(session, owner_user_id=owner_user_id, copy=copy, ctx_by_id=ctx_by_id)
        if row is not None:
            candidates.append(row)
    candidates.sort(key=lambda c: (-c.grading_score, -c.expected_roi_pct, c.inventory_copy_id))
    return candidates[: min(max(limit, 1), 200)]
