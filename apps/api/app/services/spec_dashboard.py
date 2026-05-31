from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseKeySignal
from app.schemas.spec_intelligence import SpecDashboardRead, SpecRecommendationRead
from app.services.spec_intelligence import list_executions_for_owner
from app.services.spec_recommendation_agent import list_recommendations_for_owner
from app.services.spec_review import list_reviews_for_owner
from app.services.release_variant_metrics import (
    count_ratio_variants_for_owner,
    count_variants_for_owner,
    list_top_ratio_variants,
)
from app.services.weekly_buy_list_agent import list_weekly_buy_lists_for_owner


def _recommendations_by_signal(
    session: Session,
    *,
    recommendations: list[SpecRecommendationRead],
    signal_type: str,
) -> list[SpecRecommendationRead]:
    recommendation_ids = [row.release_issue_id for row in recommendations]
    if not recommendation_ids:
        return []
    matches = {
        row.issue_id
        for row in session.exec(
            select(ReleaseKeySignal)
            .where(ReleaseKeySignal.issue_id.in_(recommendation_ids))
            .where(ReleaseKeySignal.signal_type == signal_type)
        ).all()
    }
    return [row for row in recommendations if row.release_issue_id in matches]


def build_spec_dashboard(session: Session, *, owner_user_id: int) -> SpecDashboardRead:
    recommendations, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=100, offset=0)
    weekly_buy_lists, _ = list_weekly_buy_lists_for_owner(session, owner_user_id=owner_user_id, limit=4, offset=0)
    executions, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    reviews = list_reviews_for_owner(session, owner_user_id=owner_user_id, limit=20)
    top = sorted(recommendations, key=lambda row: row.recommendation_score, reverse=True)[:10]
    return SpecDashboardRead(
        top_spec_opportunities=top,
        weekly_buy_lists=weekly_buy_lists,
        new_number_one_opportunities=_recommendations_by_signal(
            session, recommendations=recommendations, signal_type="NEW_NUMBER_ONE"
        )[:10],
        variant_opportunities=_recommendations_by_signal(
            session, recommendations=recommendations, signal_type="HIGH_RATIO_VARIANT"
        )[:10]
        + _recommendations_by_signal(session, recommendations=recommendations, signal_type="VARIANT_RATIO")[:10],
        key_issue_opportunities=_recommendations_by_signal(
            session, recommendations=recommendations, signal_type="FIRST_APPEARANCE"
        )[:10]
        + _recommendations_by_signal(session, recommendations=recommendations, signal_type="MILESTONE_NUMBERING")[:10],
        watch_opportunities=[row for row in recommendations if row.recommendation_type == "WATCH"][:10],
        recommendation_reviews=reviews,
        agent_activity=executions,
        variant_count=count_variants_for_owner(session, owner_user_id=owner_user_id),
        ratio_variant_count=count_ratio_variants_for_owner(session, owner_user_id=owner_user_id),
        top_ratio_variants=list_top_ratio_variants(session, owner_user_id=owner_user_id, limit=10),
        upcoming_incentive_variants=list_top_ratio_variants(session, owner_user_id=owner_user_id, limit=10),
    )
