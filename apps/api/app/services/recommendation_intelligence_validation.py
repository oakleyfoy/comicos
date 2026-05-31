from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.character_intelligence import CharacterProfile
from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.franchise_intelligence import FranchiseProfile
from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.recommendation_v2 import (
    RecommendationDecisionV2,
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
)
from app.models.release_intelligence import ReleaseIssue
from app.models.spec_intelligence import SpecRecommendation
from app.models.user_preference_intelligence import UserPreferenceProfile
from app.schemas.recommendation_intelligence_certification import (
    RecommendationIntelligenceValidationCheckRead,
    RecommendationIntelligenceValidationRead,
)
from app.services.recommendation_v2_comparison import compare_v1_v2_recommendations
from app.services.recommendation_v2_engine import _latest_scores_by_issue

STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"


def _aggregate(statuses: list[str]) -> str:
    if any(s == STATUS_FAIL for s in statuses):
        return STATUS_FAIL
    if any(s == STATUS_WARNING for s in statuses):
        return STATUS_WARNING
    return STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> RecommendationIntelligenceValidationCheckRead:
    return RecommendationIntelligenceValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_p51_01_inputs(session: Session) -> RecommendationIntelligenceValidationCheckRead:
    characters = session.scalar(select(func.count()).select_from(CharacterProfile)) or 0
    franchises = session.scalar(select(func.count()).select_from(FranchiseProfile)) or 0
    creators = session.scalar(select(func.count()).select_from(CreatorProfile)) or 0
    status = STATUS_PASS
    if characters < 50 or franchises < 20 or creators < 50:
        status = STATUS_WARNING
    if characters == 0 or franchises == 0:
        status = STATUS_FAIL
    return _check(
        check_code="p51_01_collector_intelligence",
        title="P51-01 Character / Franchise / Creator Intelligence",
        status=status,
        summary=f"{characters} characters, {franchises} franchises, {creators} creators in catalog.",
        details_json={"characters": int(characters), "franchises": int(franchises), "creators": int(creators)},
    )


def validate_p51_02_inputs(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    count = (
        session.scalar(
            select(func.count())
            .select_from(KeyIssueProfile)
            .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        )
        or 0
    )
    status = STATUS_PASS if count else STATUS_WARNING
    if count == 0:
        status = STATUS_WARNING
    return _check(
        check_code="p51_02_key_issue_intelligence",
        title="P51-02 Key Issue Intelligence",
        status=status,
        summary=f"{count} key issue profiles for owner catalog.",
        details_json={"key_issue_profile_count": int(count)},
    )


def validate_p51_03_inputs(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    market = session.scalar(select(func.count()).select_from(MarketDemandProfile)) or 0
    prefs = (
        session.scalar(
            select(func.count())
            .select_from(UserPreferenceProfile)
            .where(UserPreferenceProfile.owner_user_id == owner_user_id)
        )
        or 0
    )
    status = STATUS_PASS if market >= 10 else STATUS_WARNING
    if market == 0:
        status = STATUS_FAIL
    return _check(
        check_code="p51_03_market_user_intelligence",
        title="P51-03 Market & User Intelligence",
        status=status,
        summary=f"{market} market demand profiles; {prefs} user preference profiles for owner.",
        details_json={"market_demand_profiles": int(market), "user_preference_profiles": int(prefs)},
    )


def validate_p51_04_outputs(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    v2_count = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationScoreV2)
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )
    latest = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    component_rows = (
        session.scalar(
            select(func.count())
            .select_from(RecommendationScoreComponentV2)
            .join(
                RecommendationScoreV2,
                RecommendationScoreComponentV2.recommendation_score_id == RecommendationScoreV2.id,
            )
            .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        )
        or 0
    )
    status = STATUS_PASS if v2_count and latest else STATUS_FAIL
    if v2_count and not latest:
        status = STATUS_WARNING
    return _check(
        check_code="p51_04_recommendation_v2",
        title="P51-04 Recommendation Engine V2",
        status=status,
        summary=f"{v2_count} V2 scores stored; {len(latest)} latest issue-level recommendations; {component_rows} components.",
        details_json={
            "v2_score_rows": int(v2_count),
            "latest_issue_scores": len(latest),
            "component_rows": int(component_rows),
        },
    )


def validate_v1_preserved(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    v1_count = (
        session.scalar(
            select(func.count())
            .select_from(SpecRecommendation)
            .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        )
        or 0
    )
    status = STATUS_PASS if v1_count else STATUS_WARNING
    return _check(
        check_code="v1_spec_preserved",
        title="V1 Spec Recommendations Preserved",
        status=status,
        summary=f"{v1_count} V1 spec recommendations remain available (append-only V2).",
        details_json={"v1_recommendation_count": int(v1_count)},
    )


def validate_explanations(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    decisions = (
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
    latest = len(_latest_scores_by_issue(session, owner_user_id=owner_user_id))
    status = STATUS_PASS if decisions >= latest and latest else STATUS_WARNING
    if latest and decisions == 0:
        status = STATUS_FAIL
    return _check(
        check_code="v2_explanations",
        title="V2 Explanations & Decisions",
        status=status,
        summary=f"{decisions} decision records for owner V2 recommendations.",
        details_json={"decision_count": int(decisions), "latest_issue_scores": latest},
    )


def validate_v1_v2_comparison(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    comparison = compare_v1_v2_recommendations(session, owner_user_id=owner_user_id, limit=100)
    status = STATUS_PASS if comparison.v2_sample_size else STATUS_WARNING
    if comparison.v1_sample_size and comparison.v2_sample_size == 0:
        status = STATUS_FAIL
    return _check(
        check_code="v1_v2_comparison",
        title="V1 vs V2 Comparison",
        status=status,
        summary=(
            f"V1 sample {comparison.v1_sample_size}, V2 sample {comparison.v2_sample_size}; "
            f"moved up {comparison.books_moved_up}, down {comparison.books_moved_down}."
        ),
        details_json={
            "v1_sample_size": comparison.v1_sample_size,
            "v2_sample_size": comparison.v2_sample_size,
            "books_moved_up": comparison.books_moved_up,
            "books_moved_down": comparison.books_moved_down,
        },
    )


def validate_append_only(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationCheckRead:
    runs = (
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
    status = STATUS_PASS if runs >= 1 and v2_rows >= 1 else STATUS_WARNING
    if runs > 0 and v2_rows == 0:
        status = STATUS_FAIL
    return _check(
        check_code="append_only_v2",
        title="Append-Only V2 Behavior",
        status=status,
        summary=f"{runs} V2 runs; {v2_rows} total score rows (append-only, no V1 overwrite).",
        details_json={
            "run_count": int(runs),
            "v2_score_rows": int(v2_rows),
            "incomplete_run_detected": runs > 0 and v2_rows == 0,
        },
    )


def validate_recommendation_intelligence(session: Session, *, owner_user_id: int) -> RecommendationIntelligenceValidationRead:
    checks = [
        validate_p51_01_inputs(session),
        validate_p51_02_inputs(session, owner_user_id=owner_user_id),
        validate_p51_03_inputs(session, owner_user_id=owner_user_id),
        validate_p51_04_outputs(session, owner_user_id=owner_user_id),
        validate_v1_preserved(session, owner_user_id=owner_user_id),
        validate_explanations(session, owner_user_id=owner_user_id),
        validate_v1_v2_comparison(session, owner_user_id=owner_user_id),
        validate_append_only(session, owner_user_id=owner_user_id),
    ]
    return RecommendationIntelligenceValidationRead(
        overall_status=_aggregate([c.status for c in checks]),
        checks=checks,
    )
