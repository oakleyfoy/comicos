from __future__ import annotations

from sqlmodel import Session, select

from app.models.key_issue_intelligence import KeyIssueClassification, KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.key_issue_intelligence import (
    KeyIssueDashboardRead,
    KeyIssueProfileRead,
    KeyIssueScoreBreakdownRead,
)
from app.services.key_issue_scoring import score_key_issue_profile


def _profile_read(
    session: Session,
    *,
    profile: KeyIssueProfile,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> KeyIssueProfileRead:
    breakdown = score_key_issue_profile(session, profile=profile, issue=issue, series=series)
    classification = session.exec(
        select(KeyIssueClassification).where(KeyIssueClassification.release_issue_id == issue.id)
    ).first()
    return KeyIssueProfileRead(
        id=int(profile.id or 0),
        release_issue_id=int(issue.id or 0),
        issue_number=issue.issue_number,
        title=issue.title,
        series_name=series.series_name,
        publisher=series.publisher,
        key_issue_type=profile.key_issue_type,
        importance_score=float(profile.importance_score),
        confidence_score=float(profile.confidence_score),
        classification=classification.classification if classification else profile.key_issue_type,
        scores=KeyIssueScoreBreakdownRead(
            importance_score=breakdown.importance_score,
            collector_importance=breakdown.collector_importance,
            historical_importance=breakdown.historical_importance,
            franchise_importance=breakdown.franchise_importance,
            overall_key_issue_score=breakdown.overall_key_issue_score,
        ),
    )


def _list_by_type(session: Session, *, owner_user_id: int, key_issue_type: str, limit: int) -> list[KeyIssueProfileRead]:
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(KeyIssueProfile.key_issue_type == key_issue_type)
        .order_by(KeyIssueProfile.importance_score.desc())
        .limit(limit)
    ).all()
    return [_profile_read(session, profile=profile, issue=issue, series=series) for profile, issue, series in rows]


def build_key_issue_dashboard(session: Session, *, owner_user_id: int, limit: int = 20) -> KeyIssueDashboardRead:
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(KeyIssueProfile.importance_score.desc())
        .limit(limit)
    ).all()
    reads = [_profile_read(session, profile=profile, issue=issue, series=series) for profile, issue, series in rows]
    return KeyIssueDashboardRead(
        top_key_issues=reads,
        first_appearances=_list_by_type(session, owner_user_id=owner_user_id, key_issue_type="FIRST_APPEARANCE", limit=limit),
        origins=_list_by_type(session, owner_user_id=owner_user_id, key_issue_type="ORIGIN", limit=limit),
        milestones=_list_by_type(session, owner_user_id=owner_user_id, key_issue_type="MILESTONE_NUMBERING", limit=limit),
        anniversaries=_list_by_type(session, owner_user_id=owner_user_id, key_issue_type="ANNIVERSARY", limit=limit),
        universe_launches=_list_by_type(session, owner_user_id=owner_user_id, key_issue_type="UNIVERSE_LAUNCH", limit=limit),
        highest_importance=reads[: min(10, len(reads))],
        total_profiles=len(
            session.exec(
                select(KeyIssueProfile)
                .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
                .where(ReleaseIssue.owner_user_id == owner_user_id)
            ).all()
        ),
    )


def list_key_issues_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[KeyIssueProfileRead], int]:
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(KeyIssueProfile.importance_score.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(
        session.exec(
            select(KeyIssueProfile)
            .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    )
    items = [_profile_read(session, profile=profile, issue=issue, series=series) for profile, issue, series in rows]
    return items, total
