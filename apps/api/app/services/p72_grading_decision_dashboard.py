"""P72-01 grading decision dashboard and API mapping."""

from __future__ import annotations

from sqlmodel import Session

from app.models import InventoryCopy
from app.schemas.grading_intelligence import (
    P72GradingDecisionCandidateRead,
    P72GradingDecisionDashboardRead,
)
from app.services.grading_candidate_engine import (
    REC_DO_NOT_GRADE,
    REC_GRADE,
    REC_PRESS_AND_GRADE,
    REC_WATCH,
    GradingDecisionCandidate,
    build_grading_decision_for_copy,
    discover_grading_candidates,
)


def _to_read(row: GradingDecisionCandidate) -> P72GradingDecisionCandidateRead:
    return P72GradingDecisionCandidateRead(
        inventory_copy_id=row.inventory_copy_id,
        title=row.title,
        publisher=row.publisher,
        issue_number=row.issue_number,
        raw_fmv=row.raw_fmv,
        blended_fmv=row.blended_fmv,
        liquidity_score=row.liquidity_score,
        market_confidence=row.market_confidence,
        sales_velocity=row.sales_velocity,
        sell_intelligence_score=row.sell_intelligence_score,
        recommendation=row.recommendation,
        pressing_recommendation=row.pressing_recommendation,
        expected_grade=row.expected_grade,
        grade_probabilities=row.grade_probabilities,
        expected_graded_fmv=row.expected_graded_fmv,
        expected_total_cost=row.expected_total_cost,
        expected_profit=row.expected_profit,
        expected_roi_pct=row.expected_roi_pct,
        grading_score=row.grading_score,
        confidence=row.confidence,
        primary_reason=row.primary_reason,
        factors_json=row.factors_json,
    )


def build_p72_decision_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    top_limit: int = 15,
) -> P72GradingDecisionDashboardRead:
    candidates = discover_grading_candidates(session, owner_user_id=owner_user_id, limit=200)
    top = [_to_read(c) for c in candidates[: min(max(top_limit, 1), 50)]]
    if not candidates:
        return P72GradingDecisionDashboardRead(
            candidate_count=0,
            average_grading_score=0.0,
            average_expected_roi_pct=0.0,
            press_and_grade_count=0,
            grade_count=0,
            watch_count=0,
            do_not_grade_count=0,
            top_grade_candidates=[],
        )
    return P72GradingDecisionDashboardRead(
        candidate_count=len(candidates),
        average_grading_score=round(sum(c.grading_score for c in candidates) / len(candidates), 2),
        average_expected_roi_pct=round(sum(c.expected_roi_pct for c in candidates) / len(candidates), 2),
        press_and_grade_count=sum(1 for c in candidates if c.recommendation == REC_PRESS_AND_GRADE),
        grade_count=sum(1 for c in candidates if c.recommendation == REC_GRADE),
        watch_count=sum(1 for c in candidates if c.recommendation == REC_WATCH),
        do_not_grade_count=sum(1 for c in candidates if c.recommendation == REC_DO_NOT_GRADE),
        top_grade_candidates=top,
    )


def list_p72_decision_candidates(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
) -> tuple[list[P72GradingDecisionCandidateRead], int]:
    rows = discover_grading_candidates(session, owner_user_id=owner_user_id, limit=limit)
    return [_to_read(r) for r in rows], len(rows)


def get_p72_decision_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> P72GradingDecisionCandidateRead | None:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        return None
    row = build_grading_decision_for_copy(session, owner_user_id=owner_user_id, copy=copy)
    return _to_read(row) if row else None
