from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.recommendation_v2 import RecommendationScoreComponentV2, RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue
from app.models.user_preference_intelligence import UserPreferenceProfile
from app.schemas.recommendation_intelligence_certification import RecommendationQualityCalibrationRead
from app.services.recommendation_v2_engine import _latest_scores_by_issue

CALIBRATION_PASS = "PASS"
CALIBRATION_WARNING = "WARNING"
CALIBRATION_FAIL = "FAIL"

_DIVERSITY_TYPES = {
    "KEY_ISSUE",
    "MILESTONE",
    "USER_PREFERENCE_MATCH",
    "MARKET_DEMAND_PLAY",
    "FRANCHISE_OPPORTUNITY",
    "START_RUN",
    "RATIO_VARIANT",
}


def _is_number_one(issue: ReleaseIssue | None) -> bool:
    if not issue:
        return False
    return issue.issue_number.strip().lstrip("#") in {"1", "001"}


def _owner_preference_profile_count(session: Session, *, owner_user_id: int) -> int:
    rows = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.status == "ACTIVE",
        )
    ).all()
    return len(rows)


def _user_preference_component_active(session: Session, *, score_ids: list[int]) -> bool:
    if not score_ids:
        return False
    rows = session.exec(
        select(RecommendationScoreComponentV2)
        .where(RecommendationScoreComponentV2.recommendation_score_id.in_(score_ids))
        .where(RecommendationScoreComponentV2.component_name == "USER_PREFERENCE_SCORE")
    ).all()
    scores = [float(r.component_score) for r in rows]
    if not scores:
        return False
    return max(scores) > 52.0 and (max(scores) - min(scores)) >= 4.0


def calibrate_recommendation_quality(session: Session, *, owner_user_id: int) -> RecommendationQualityCalibrationRead:
    latest = list(_latest_scores_by_issue(session, owner_user_id=owner_user_id).values())
    total = len(latest)
    findings: list[str] = []

    tier_dist = Counter(row.recommendation_tier for row in latest)
    type_dist = Counter(row.recommendation_type for row in latest)

    number_ones = 0
    one_scores: list[float] = []
    for score in latest:
        issue = session.get(ReleaseIssue, score.release_issue_id)
        if _is_number_one(issue):
            number_ones += 1
            one_scores.append(float(score.total_score))

    top20 = sorted(latest, key=lambda r: r.total_score, reverse=True)[:20]
    top20_number_ones = sum(
        1 for score in top20 if _is_number_one(session.get(ReleaseIssue, score.release_issue_id))
    )

    key_in_top = sum(1 for score in top20 if score.recommendation_type == "KEY_ISSUE")
    user_pref_in_top = sum(1 for score in top20 if score.recommendation_type == "USER_PREFERENCE_MATCH")
    diversity_in_top = sum(1 for score in top20 if score.recommendation_type in _DIVERSITY_TYPES)

    scores = [float(s.total_score) for s in latest]
    score_variance = 0.0
    if len(scores) >= 2:
        mean = sum(scores) / len(scores)
        score_variance = sum((s - mean) ** 2 for s in scores) / len(scores)

    top20_ids = [int(s.id or 0) for s in top20]
    user_pref_active = _user_preference_component_active(session, score_ids=top20_ids)
    pref_profiles = _owner_preference_profile_count(session, owner_user_id=owner_user_id)

    status = CALIBRATION_PASS
    if total == 0:
        status = CALIBRATION_FAIL
        findings.append("No V2 recommendations to calibrate.")
    else:
        must_pct = tier_dist.get("MUST_BUY", 0) / total
        if must_pct >= 0.9:
            status = CALIBRATION_FAIL
            findings.append("Over 90% of recommendations are MUST_BUY.")
        if number_ones == 0:
            status = CALIBRATION_WARNING if status == CALIBRATION_PASS else status
            findings.append("No #1 issues in latest V2 issue-level set.")
        elif one_scores and max(one_scores) < 35.0:
            status = CALIBRATION_FAIL
            findings.append("#1 issues lack meaningful score credit.")
        if top20 and top20_number_ones >= 18:
            status = CALIBRATION_FAIL
            findings.append("Random #1s dominate top 20 (possible #1-only bias).")
        if top20 and top20_number_ones == len(top20) and total >= 15:
            status = CALIBRATION_FAIL
            findings.append("Top 20 are exclusively #1 issues — diversify scoring signals.")
        if total >= 25 and diversity_in_top < 3:
            status = CALIBRATION_FAIL
            findings.append(
                "Top 20 lacks franchise/key/market/user-preference driven diversity (need >= 3 non-investment types)."
            )
        if key_in_top == 0 and total >= 25:
            status = CALIBRATION_FAIL
            findings.append("No key issue types in top 20 results.")
        elif key_in_top == 0 and total >= 10:
            findings.append("No key issue types in top 20 results.")
            if status == CALIBRATION_PASS:
                status = CALIBRATION_WARNING
        if pref_profiles >= 3 and not user_pref_active:
            status = CALIBRATION_FAIL
            findings.append("User preference profiles exist but USER_PREFERENCE_SCORE did not differentiate top ranks.")
        elif not user_pref_active and total >= 5 and pref_profiles == 0:
            findings.append("User preference component did not differentiate scores.")
            if status == CALIBRATION_PASS:
                status = CALIBRATION_WARNING
        if score_variance < 1.0 and total >= 5:
            status = CALIBRATION_FAIL
            findings.append("All recommendations share nearly identical scores.")

    return RecommendationQualityCalibrationRead(
        overall_status=status,
        total_recommendations=total,
        tier_distribution=dict(tier_dist),
        type_distribution=dict(type_dist),
        number_one_count=number_ones,
        key_issue_in_top_count=key_in_top,
        user_preference_component_active=user_pref_active,
        score_variance=round(score_variance, 3),
        findings=findings,
        details_json={
            "top20_number_one_count": top20_number_ones,
            "user_preference_matches_in_top20": user_pref_in_top,
            "top20_diversity_type_count": diversity_in_top,
            "active_preference_profiles": pref_profiles,
        },
    )
