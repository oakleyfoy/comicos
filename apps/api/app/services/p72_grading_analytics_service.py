"""P72-03 grading intelligence analytics aggregation."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from statistics import median

from sqlmodel import Session, select

from app.models.p72_grading_analytics import P72GradingOutcome
from app.models.p72_grading_operations import P72GradingQueueEntry
from app.schemas.p72_grading_analytics import (
    P72GradingAnalyticsDashboardRead,
    P72GradingPerformanceRead,
    P72GradingPortfolioImpactRead,
    P72GradingPressingAnalyticsRead,
    P72GradingRecommendationAccuracyRead,
    P72GradingRoiAnalyticsRead,
    P72GradingOutcomeRead,
    P72GradingWinLossRead,
)
from app.services.grading_outcome_service import list_outcomes, sync_outcomes_from_queue
from app.services.grading_queue_service import (
    COMPLETED_STATUSES,
    IN_PROCESS_STATUSES,
    STATUS_AT_CGC,
    STATUS_RETURNED,
    STATUS_SOLD,
    STATUS_SUBMITTED,
    WAITING_STATUSES,
)


def _grade_numeric(grade: str) -> float | None:
    try:
        return float(grade.replace("_", ".").split()[0])
    except (ValueError, AttributeError):
        return None


def _distribution(grades: list[str]) -> dict[str, float]:
    buckets = {"9.8": 0, "9.6": 0, "9.4": 0, "9.2": 0, "other": 0}
    if not grades:
        return {k: 0.0 for k in buckets}
    for g in grades:
        num = _grade_numeric(g)
        if num is None:
            buckets["other"] += 1
        elif num >= 9.75:
            buckets["9.8"] += 1
        elif num >= 9.55:
            buckets["9.6"] += 1
        elif num >= 9.35:
            buckets["9.4"] += 1
        elif num >= 9.15:
            buckets["9.2"] += 1
        else:
            buckets["other"] += 1
    total = len(grades)
    return {k: round(v / total * 100, 1) for k, v in buckets.items()}


def build_performance_analytics(session: Session, *, owner_user_id: int) -> P72GradingPerformanceRead:
    sync_outcomes_from_queue(session, owner_user_id=owner_user_id)
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    queue = list(
        session.exec(
            select(P72GradingQueueEntry).where(P72GradingQueueEntry.owner_user_id == owner_user_id)
        ).all()
    )
    submitted = sum(1 for q in queue if q.status not in WAITING_STATUSES and q.status != "CANDIDATE")
    returned = sum(1 for q in queue if q.status in {STATUS_RETURNED, STATUS_SOLD} | COMPLETED_STATUSES)
    sold = sum(1 for q in queue if q.status == STATUS_SOLD)
    held = sum(1 for q in queue if q.status in {"LISTED", STATUS_RETURNED})
    grades = [o.actual_grade for o in outcomes if o.actual_grade]
    nums = [n for g in grades for n in [_grade_numeric(g)] if n is not None]
    avg_grade = round(sum(nums) / len(nums), 2) if nums else 0.0
    med_grade = round(median(nums), 2) if nums else 0.0
    hit_98 = round(sum(1 for n in nums if n >= 9.8) / len(nums) * 100, 1) if nums else 0.0
    hit_96_plus = round(sum(1 for n in nums if n >= 9.6) / len(nums) * 100, 1) if nums else 0.0
    return P72GradingPerformanceRead(
        books_submitted=submitted,
        books_returned=returned,
        books_sold=sold,
        books_held=held,
        average_grade=avg_grade,
        median_grade=med_grade,
        hit_rate_9_8_pct=hit_98,
        hit_rate_9_6_plus_pct=hit_96_plus,
        grade_distribution_pct=_distribution(grades),
    )


def build_roi_analytics(session: Session, *, owner_user_id: int) -> P72GradingRoiAnalyticsRead:
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    spend = sum(float(o.actual_grading_cost) for o in outcomes)
    profit = sum(float(o.actual_profit) for o in outcomes)
    net_roi = round((profit / spend * 100.0) if spend > 0 else 0.0, 2)

    def _rollup(key_fn):
        groups: dict[str, list[float]] = defaultdict(list)
        for o in outcomes:
            groups[key_fn(o)].append(float(o.actual_profit))
        return {k: round(sum(v), 2) for k, v in sorted(groups.items(), key=lambda x: -sum(x[1]))[:20]}

    return P72GradingRoiAnalyticsRead(
        total_grading_spend=round(spend, 2),
        total_profit=round(profit, 2),
        net_roi_pct=net_roi,
        profit_by_publisher=_rollup(lambda o: o.publisher or "unknown"),
        profit_by_series=_rollup(lambda o: o.series or o.title),
        profit_by_character=_rollup(lambda o: (o.metadata_json or {}).get("character") or "unknown"),
        profit_by_creator=_rollup(lambda o: (o.metadata_json or {}).get("creator") or "unknown"),
        profit_by_era=_rollup(lambda o: o.era or "unknown"),
    )


def build_pressing_analytics(session: Session, *, owner_user_id: int) -> P72GradingPressingAnalyticsRead:
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    pressed = [o for o in outcomes if o.was_pressed]
    not_pressed = [o for o in outcomes if not o.was_pressed]

    def _avg_roi(rows: list[P72GradingOutcome]) -> float:
        if not rows:
            return 0.0
        return round(sum(float(r.actual_roi_pct) for r in rows) / len(rows), 2)

    def _avg_grade(rows: list[P72GradingOutcome]) -> float:
        nums = [_grade_numeric(r.actual_grade) for r in rows]
        nums = [n for n in nums if n is not None]
        return round(sum(nums) / len(nums), 2) if nums else 0.0

    pressed_rec = [o for o in outcomes if o.pressing_recommended == "PRESS"]
    success = sum(1 for o in pressed_rec if float(o.actual_roi_pct) >= float(o.expected_roi_pct) * 0.85)
    rate = round(success / len(pressed_rec) * 100, 1) if pressed_rec else 0.0

    return P72GradingPressingAnalyticsRead(
        pressed_book_count=len(pressed),
        non_pressed_book_count=len(not_pressed),
        pressed_avg_roi_pct=_avg_roi(pressed),
        non_pressed_avg_roi_pct=_avg_roi(not_pressed),
        pressed_avg_grade=_avg_grade(pressed),
        non_pressed_avg_grade=_avg_grade(not_pressed),
        roi_difference_pct=round(_avg_roi(pressed) - _avg_roi(not_pressed), 2),
        grade_difference=round(_avg_grade(pressed) - _avg_grade(not_pressed), 2),
        pressing_success_rate_pct=rate,
        pressing_worth_it=rate >= 50 or (_avg_roi(pressed) > _avg_roi(not_pressed) + 5),
    )


def build_recommendation_accuracy(
    session: Session,
    *,
    owner_user_id: int,
) -> P72GradingRecommendationAccuracyRead:
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    rows = [
        {
            "recommendation": o.recommendation,
            "expected_roi_pct": float(o.expected_roi_pct),
            "actual_roi_pct": float(o.actual_roi_pct),
            "accuracy": o.recommendation_accuracy,
            "title": o.title,
        }
        for o in outcomes
        if o.recommendation_accuracy != "N/A"
    ]
    high = sum(1 for o in outcomes if o.recommendation_accuracy == "HIGH")
    scored = [o for o in outcomes if o.recommendation_accuracy in {"HIGH", "MEDIUM", "LOW"}]
    overall = round(high / len(scored) * 100, 1) if scored else 0.0
    return P72GradingRecommendationAccuracyRead(
        overall_accuracy_pct=overall,
        sample_count=len(scored),
        comparisons=rows[:50],
    )


def build_portfolio_impact(session: Session, *, owner_user_id: int) -> P72GradingPortfolioImpactRead:
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    raw_total = round(sum(float(o.raw_fmv) for o in outcomes), 2)
    graded_total = round(sum(float(o.graded_value_estimate) for o in outcomes), 2)
    return P72GradingPortfolioImpactRead(
        total_books_graded=len(outcomes),
        total_slab_value=graded_total,
        total_raw_value=raw_total,
        total_graded_value=graded_total,
        value_added_through_grading=round(graded_total - raw_total, 2),
    )


def _win_loss(outcomes: list[P72GradingOutcome]) -> tuple[list[P72GradingWinLossRead], list[P72GradingWinLossRead]]:
    ranked = sorted(outcomes, key=lambda o: float(o.actual_profit), reverse=True)
    wins = [
        P72GradingWinLossRead(
            title=o.title,
            actual_profit=float(o.actual_profit),
            actual_roi_pct=float(o.actual_roi_pct),
            actual_grade=o.actual_grade,
            recommendation=o.recommendation,
        )
        for o in ranked[:5]
        if float(o.actual_profit) > 0
    ]
    losses = [
        P72GradingWinLossRead(
            title=o.title,
            actual_profit=float(o.actual_profit),
            actual_roi_pct=float(o.actual_roi_pct),
            actual_grade=o.actual_grade,
            recommendation=o.recommendation,
        )
        for o in sorted(outcomes, key=lambda o: float(o.actual_profit))[:5]
        if float(o.actual_profit) < 0
    ]
    return wins, losses


def build_analytics_dashboard(session: Session, *, owner_user_id: int) -> P72GradingAnalyticsDashboardRead:
    sync_outcomes_from_queue(session, owner_user_id=owner_user_id)
    outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=500)
    perf = build_performance_analytics(session, owner_user_id=owner_user_id)
    roi = build_roi_analytics(session, owner_user_id=owner_user_id)
    pressing = build_pressing_analytics(session, owner_user_id=owner_user_id)
    accuracy = build_recommendation_accuracy(session, owner_user_id=owner_user_id)
    portfolio = build_portfolio_impact(session, owner_user_id=owner_user_id)
    wins, losses = _win_loss(outcomes)
    return P72GradingAnalyticsDashboardRead(
        performance=perf,
        roi=roi,
        recommendation_accuracy=accuracy,
        pressing=pressing,
        portfolio_impact=portfolio,
        top_grading_wins=wins,
        worst_grading_decisions=losses,
        outcome_count=len(outcomes),
    )


def list_outcome_reads(session: Session, *, owner_user_id: int, limit: int = 100) -> list[P72GradingOutcomeRead]:
    sync_outcomes_from_queue(session, owner_user_id=owner_user_id)
    return [P72GradingOutcomeRead.model_validate(o) for o in list_outcomes(session, owner_user_id=owner_user_id, limit=limit)]
