from __future__ import annotations

from sqlmodel import Session, col, func, select

from app.models.key_issue_intelligence import KeyIssueClassification, KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.key_issue_intelligence import (
    KeyIssueDashboardRead,
    KeyIssueProfileRead,
    KeyIssueScoreBreakdownRead,
)
from app.services.key_issue_scoring import score_key_issue_profile


def _scores_from_stored_profile(profile: KeyIssueProfile) -> KeyIssueScoreBreakdownRead:
    base = float(profile.importance_score)
    confidence = float(profile.confidence_score)
    return KeyIssueScoreBreakdownRead(
        importance_score=base,
        collector_importance=round(min(100.0, base * 0.9), 2),
        historical_importance=round(min(100.0, base * confidence), 2),
        franchise_importance=round(min(100.0, base * 0.5), 2),
        overall_key_issue_score=base,
    )


def _classification_map(session: Session, *, issue_ids: set[int]) -> dict[int, str]:
    if not issue_ids:
        return {}
    rows = session.exec(
        select(KeyIssueClassification).where(col(KeyIssueClassification.release_issue_id).in_(issue_ids)),
    ).all()
    return {int(row.release_issue_id): row.classification for row in rows if row.release_issue_id is not None}


def _profile_read_fast(
    *,
    profile: KeyIssueProfile,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    classifications: dict[int, str],
) -> KeyIssueProfileRead:
    issue_id = int(issue.id or 0)
    classification = classifications.get(issue_id) or profile.key_issue_type
    return KeyIssueProfileRead(
        id=int(profile.id or 0),
        release_issue_id=issue_id,
        issue_number=issue.issue_number,
        title=issue.title,
        series_name=series.series_name,
        publisher=series.publisher,
        key_issue_type=profile.key_issue_type,
        importance_score=float(profile.importance_score),
        confidence_score=float(profile.confidence_score),
        classification=classification,
        scores=_scores_from_stored_profile(profile),
    )


def _count_profiles_for_owner(session: Session, *, owner_user_id: int) -> int:
    value = session.exec(
        select(func.count())
        .select_from(KeyIssueProfile)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id),
    ).one()
    return int(value or 0)


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


def _list_by_type_fast(
    session: Session,
    *,
    owner_user_id: int,
    key_issue_type: str,
    limit: int,
    classifications: dict[int, str],
) -> list[KeyIssueProfileRead]:
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(KeyIssueProfile.key_issue_type == key_issue_type)
        .order_by(KeyIssueProfile.importance_score.desc())
        .limit(limit)
    ).all()
    missing_ids = {
        int(issue.id or 0)
        for _, issue, _ in rows
        if issue.id is not None and int(issue.id) not in classifications
    }
    if missing_ids:
        classifications.update(_classification_map(session, issue_ids=missing_ids))
    return [
        _profile_read_fast(profile=profile, issue=issue, series=series, classifications=classifications)
        for profile, issue, series in rows
    ]


def build_key_issue_dashboard_fast(session: Session, *, owner_user_id: int, limit: int = 12) -> KeyIssueDashboardRead:
    """Cached-style read for nav page load — no per-row intelligence rescoring."""
    lim = max(1, min(limit, 50))
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(KeyIssueProfile.importance_score.desc())
        .limit(lim)
    ).all()
    issue_ids = {int(issue.id or 0) for _, issue, _ in rows if issue.id is not None}
    classifications = _classification_map(session, issue_ids=issue_ids)
    reads = [
        _profile_read_fast(profile=profile, issue=issue, series=series, classifications=classifications)
        for profile, issue, series in rows
    ]
    total = _count_profiles_for_owner(session, owner_user_id=owner_user_id)
    return KeyIssueDashboardRead(
        top_key_issues=reads,
        first_appearances=_list_by_type_fast(
            session, owner_user_id=owner_user_id, key_issue_type="FIRST_APPEARANCE", limit=lim, classifications=classifications
        ),
        origins=_list_by_type_fast(
            session, owner_user_id=owner_user_id, key_issue_type="ORIGIN", limit=lim, classifications=classifications
        ),
        milestones=_list_by_type_fast(
            session,
            owner_user_id=owner_user_id,
            key_issue_type="MILESTONE_NUMBERING",
            limit=lim,
            classifications=classifications,
        ),
        anniversaries=_list_by_type_fast(
            session, owner_user_id=owner_user_id, key_issue_type="ANNIVERSARY", limit=lim, classifications=classifications
        ),
        universe_launches=_list_by_type_fast(
            session, owner_user_id=owner_user_id, key_issue_type="UNIVERSE_LAUNCH", limit=lim, classifications=classifications
        ),
        highest_importance=reads[: min(10, len(reads))],
        total_profiles=total,
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
        total_profiles=_count_profiles_for_owner(session, owner_user_id=owner_user_id),
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
