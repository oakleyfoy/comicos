from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import AgentExecution, IntelligenceRecommendation, IntelligenceRecommendationReview
@dataclass(frozen=True)
class RecommendationOutcomeAggregate:
    recommendation_type: str
    recommendations_total: int
    reviewed_total: int
    accepted_total: int
    dismissed_total: int
    acceptance_rate: float
    dismissal_rate: float
    avg_confidence_score: float
    avg_opportunity_score: float
    avg_priority_score: float


def _round_rate(value: float) -> float:
    return round(float(value), 4)


def _latest_review_status_map(session: Session, *, recommendation_ids: list[int]) -> dict[int, str]:
    if not recommendation_ids:
        return {}
    rows = session.exec(
        select(IntelligenceRecommendationReview)
        .where(IntelligenceRecommendationReview.recommendation_id.in_(recommendation_ids))
        .order_by(IntelligenceRecommendationReview.reviewed_at.asc(), IntelligenceRecommendationReview.id.asc())
    ).all()
    latest: dict[int, str] = {}
    for row in rows:
        latest[row.recommendation_id] = row.review_status
    return latest


def calculate_review_rates(*, recommendations_total: int, reviewed_total: int) -> float:
    if recommendations_total <= 0:
        return 0.0
    return _round_rate(reviewed_total / recommendations_total)


def calculate_acceptance_rates(*, recommendations_total: int, accepted_total: int) -> float:
    if recommendations_total <= 0:
        return 0.0
    return _round_rate(accepted_total / recommendations_total)


def calculate_dismissal_rates(*, recommendations_total: int, dismissed_total: int) -> float:
    if recommendations_total <= 0:
        return 0.0
    return _round_rate(dismissed_total / recommendations_total)


def calculate_average_scores(rows: list[IntelligenceRecommendation]) -> dict[str, float]:
    if not rows:
        return {
            "avg_confidence_score": 0.0,
            "avg_opportunity_score": 0.0,
            "avg_priority_score": 0.0,
        }
    count = len(rows)
    return {
        "avg_confidence_score": _round_rate(sum(row.confidence_score for row in rows) / count),
        "avg_opportunity_score": _round_rate(sum(row.opportunity_score for row in rows) / count),
        "avg_priority_score": _round_rate(sum(row.priority_score for row in rows) / count),
    }


def calculate_outcomes_by_type(session: Session, *, owner_user_id: int) -> list[RecommendationOutcomeAggregate]:
    rows = session.exec(
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(IntelligenceRecommendation.recommendation_type.asc(), IntelligenceRecommendation.id.asc())
    ).all()
    latest_review_status = _latest_review_status_map(
        session,
        recommendation_ids=[int(row.id or 0) for row in rows],
    )
    grouped: dict[str, list[IntelligenceRecommendation]] = defaultdict(list)
    for row in rows:
        grouped[row.recommendation_type].append(row)

    aggregates: list[RecommendationOutcomeAggregate] = []
    for recommendation_type in sorted(grouped):
        grouped_rows = grouped[recommendation_type]
        reviewed_total = sum(1 for row in grouped_rows if int(row.id or 0) in latest_review_status)
        accepted_total = sum(1 for row in grouped_rows if latest_review_status.get(int(row.id or 0)) == "ACCEPTED")
        dismissed_total = sum(1 for row in grouped_rows if latest_review_status.get(int(row.id or 0)) == "DISMISSED")
        averages = calculate_average_scores(grouped_rows)
        aggregates.append(
            RecommendationOutcomeAggregate(
                recommendation_type=recommendation_type,
                recommendations_total=len(grouped_rows),
                reviewed_total=reviewed_total,
                accepted_total=accepted_total,
                dismissed_total=dismissed_total,
                acceptance_rate=calculate_acceptance_rates(
                    recommendations_total=len(grouped_rows),
                    accepted_total=accepted_total,
                ),
                dismissal_rate=calculate_dismissal_rates(
                    recommendations_total=len(grouped_rows),
                    dismissed_total=dismissed_total,
                ),
                avg_confidence_score=averages["avg_confidence_score"],
                avg_opportunity_score=averages["avg_opportunity_score"],
                avg_priority_score=averages["avg_priority_score"],
            )
        )
    return aggregates
