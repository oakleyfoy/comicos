from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.intelligence_matching import match_release_issue
from app.services.popularity_engine import franchise_score


@dataclass(frozen=True)
class KeyIssueScoreBreakdown:
    release_issue_id: int
    importance_score: float
    collector_importance: float
    historical_importance: float
    franchise_importance: float
    overall_key_issue_score: float


def score_key_issue_profile(
    session: Session,
    *,
    profile: KeyIssueProfile,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> KeyIssueScoreBreakdown:
    base = float(profile.importance_score)
    confidence = float(profile.confidence_score)
    intelligence = match_release_issue(session, issue=issue, series=series)
    franchise_boost = 0.0
    for entity in intelligence.matched_entities:
        if entity.entity_type == "FRANCHISE":
            franchise_boost = max(franchise_boost, franchise_score(session, franchise_id=entity.entity_id))

    collector = round(min(100.0, base * 0.55 + franchise_boost * 0.45), 2)
    historical = round(min(100.0, base * confidence), 2)
    franchise_importance = round(franchise_boost, 2)
    overall = round(min(100.0, (collector * 0.35 + historical * 0.35 + franchise_importance * 0.2 + base * 0.1)), 2)
    return KeyIssueScoreBreakdown(
        release_issue_id=int(issue.id or 0),
        importance_score=base,
        collector_importance=collector,
        historical_importance=historical,
        franchise_importance=franchise_importance,
        overall_key_issue_score=overall,
    )


def apply_key_issue_scoring_for_owner(session: Session, *, owner_user_id: int) -> int:
    updated = 0
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    for profile, issue, series in rows:
        breakdown = score_key_issue_profile(session, profile=profile, issue=issue, series=series)
        profile.importance_score = breakdown.overall_key_issue_score
        session.add(profile)
        updated += 1
    session.commit()
    return updated
