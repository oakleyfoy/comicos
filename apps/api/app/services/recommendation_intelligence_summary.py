from __future__ import annotations

from collections import Counter

from sqlmodel import Session, func, select

from app.models.recommendation_v2 import RecommendationDecisionV2, RecommendationRunV2, RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue
from app.models.spec_intelligence import SpecRecommendation
from app.schemas.recommendation_intelligence_certification import RecommendationIntelligenceSummaryRead
from app.services.recommendation_v2_comparison import compare_v1_v2_recommendations
from app.services.recommendation_v2_engine import _latest_scores_by_issue


def get_recommendation_intelligence_summary(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceSummaryRead:
    latest = list(_latest_scores_by_issue(session, owner_user_id=owner_user_id).values())
    tier = Counter(row.recommendation_tier for row in latest)
    types = Counter(row.recommendation_type for row in latest)
    scores = [float(r.total_score) for r in latest]
    average = round(sum(scores) / len(scores), 2) if scores else 0.0

    v1_count = (
        session.scalar(
            select(func.count())
            .select_from(SpecRecommendation)
            .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        )
        or 0
    )
    run_count = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationRunV2)
            .where(RecommendationRunV2.owner_user_id == owner_user_id)
        )
        or 0
    )
    explanation_count = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationDecisionV2)
            .join(
                RecommendationScoreV2,
                RecommendationDecisionV2.recommendation_score_id == RecommendationScoreV2.id,
            )
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )
    comparison = compare_v1_v2_recommendations(session, owner_user_id=owner_user_id, limit=100)

    readiness = 0.0
    if latest:
        readiness += 40.0
    if v1_count:
        readiness += 15.0
    if explanation_count >= len(latest) and latest:
        readiness += 20.0
    if len(tier) >= 3:
        readiness += 15.0
    if comparison.v2_sample_size:
        readiness += 10.0
    readiness = min(100.0, readiness)

    return RecommendationIntelligenceSummaryRead(
        total_recommendations_v2=len(latest),
        must_buy_count=int(tier.get("MUST_BUY", 0)),
        strong_buy_count=int(tier.get("STRONG_BUY", 0)),
        buy_count=int(tier.get("BUY", 0)),
        watch_count=int(tier.get("WATCH", 0)),
        pass_count=int(tier.get("PASS", 0)),
        investment_number_one_count=int(types.get("INVESTMENT_NUMBER_ONE", 0)),
        start_run_count=int(types.get("START_RUN", 0)),
        key_issue_count=int(types.get("KEY_ISSUE", 0)),
        ratio_variant_count=int(types.get("RATIO_VARIANT", 0)),
        user_preference_match_count=int(types.get("USER_PREFERENCE_MATCH", 0)),
        average_score=average,
        readiness_score=round(readiness, 1),
        v1_recommendation_count=int(v1_count),
        v2_run_count=int(run_count),
        explanation_count=int(explanation_count),
        v1_vs_v2_moved_up=comparison.books_moved_up,
        v1_vs_v2_moved_down=comparison.books_moved_down,
    )
