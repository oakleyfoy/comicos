from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.character_intelligence import CharacterProfile
from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.franchise_intelligence import FranchiseProfile
from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue
from app.models.user_preference_intelligence import UserPreferenceProfile
from app.schemas.recommendation_intelligence_certification import (
    RecommendationIntelligenceHealthComponentRead,
    RecommendationIntelligenceHealthRead,
)
from app.services.recommendation_v2_engine import _latest_scores_by_issue

HEALTH_HEALTHY = "HEALTHY"
HEALTH_WARNING = "WARNING"
HEALTH_FAILED = "FAILED"
HEALTH_DISABLED = "DISABLED"


def _aggregate(statuses: list[str]) -> str:
    if any(s == HEALTH_FAILED for s in statuses):
        return HEALTH_FAILED
    if any(s == HEALTH_WARNING for s in statuses):
        return HEALTH_WARNING
    return HEALTH_HEALTHY


def _component(
    *,
    component_code: str,
    title: str,
    health_status: str,
    summary: str,
    details_json: dict[str, object],
) -> RecommendationIntelligenceHealthComponentRead:
    return RecommendationIntelligenceHealthComponentRead(
        component_code=component_code,
        title=title,
        health_status=health_status,
        summary=summary,
        details_json=details_json,
    )


def get_recommendation_intelligence_health(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceHealthRead:
    char_count = session.scalar(select(func.count()).select_from(CharacterProfile)) or 0
    franchise_count = session.scalar(select(func.count()).select_from(FranchiseProfile)) or 0
    creator_count = session.scalar(select(func.count()).select_from(CreatorProfile)) or 0
    key_count = (
        session.scalar(
            select(func.count())
            .select_from(KeyIssueProfile)
            .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        )
        or 0
    )
    market_count = session.scalar(select(func.count()).select_from(MarketDemandProfile)) or 0
    pref_count = (
        session.scalar(
            select(func.count())
            .select_from(UserPreferenceProfile)
            .where(UserPreferenceProfile.owner_user_id == owner_user_id)
        )
        or 0
    )
    v2_latest = len(_latest_scores_by_issue(session, owner_user_id=owner_user_id))
    v2_runs = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationRunV2)
            .where(RecommendationRunV2.owner_user_id == owner_user_id)
        )
        or 0
    )
    v2_rows = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationScoreV2)
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )

    components = [
        _component(
            component_code="character_intelligence",
            title="Character Intelligence",
            health_status=HEALTH_HEALTHY if char_count >= 50 else HEALTH_WARNING if char_count else HEALTH_FAILED,
            summary=f"{char_count} character profiles.",
            details_json={"count": int(char_count)},
        ),
        _component(
            component_code="franchise_intelligence",
            title="Franchise Intelligence",
            health_status=HEALTH_HEALTHY if franchise_count >= 20 else HEALTH_WARNING if franchise_count else HEALTH_FAILED,
            summary=f"{franchise_count} franchise profiles.",
            details_json={"count": int(franchise_count)},
        ),
        _component(
            component_code="creator_intelligence",
            title="Creator Intelligence",
            health_status=HEALTH_HEALTHY if creator_count >= 50 else HEALTH_WARNING if creator_count else HEALTH_FAILED,
            summary=f"{creator_count} creator profiles.",
            details_json={"count": int(creator_count)},
        ),
        _component(
            component_code="key_issue_intelligence",
            title="Key Issue Intelligence",
            health_status=HEALTH_HEALTHY if key_count else HEALTH_WARNING,
            summary=f"{key_count} key issue profiles for owner.",
            details_json={"count": int(key_count)},
        ),
        _component(
            component_code="market_demand_intelligence",
            title="Market Demand Intelligence",
            health_status=HEALTH_HEALTHY if market_count >= 10 else HEALTH_WARNING if market_count else HEALTH_FAILED,
            summary=f"{market_count} market demand baselines.",
            details_json={"count": int(market_count)},
        ),
        _component(
            component_code="user_preference_intelligence",
            title="User Preference Intelligence",
            health_status=HEALTH_HEALTHY if pref_count else HEALTH_WARNING,
            summary=f"{pref_count} user preference profiles (manual or inferred).",
            details_json={"count": int(pref_count)},
        ),
        _component(
            component_code="recommendation_v2_engine",
            title="Recommendation V2 Engine",
            health_status=HEALTH_HEALTHY if v2_latest else HEALTH_FAILED if v2_rows == 0 else HEALTH_WARNING,
            summary=f"{v2_runs} runs; {v2_latest} latest issue recommendations.",
            details_json={"runs": int(v2_runs), "latest_issue_scores": v2_latest, "total_rows": int(v2_rows)},
        ),
        _component(
            component_code="recommendation_v2_api",
            title="Recommendation V2 API",
            health_status=HEALTH_HEALTHY if v2_latest else HEALTH_WARNING,
            summary="V2 list/top/dashboard routes depend on scored catalog.",
            details_json={"latest_issue_scores": v2_latest},
        ),
        _component(
            component_code="recommendation_v2_dashboard",
            title="Recommendation V2 Dashboard",
            health_status=HEALTH_HEALTHY if v2_latest else HEALTH_WARNING,
            summary="Web dashboard reads V2 tier buckets.",
            details_json={"latest_issue_scores": v2_latest},
        ),
    ]
    return RecommendationIntelligenceHealthRead(
        overall_status=_aggregate([c.health_status for c in components]),
        components=components,
    )
