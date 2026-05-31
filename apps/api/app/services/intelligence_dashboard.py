from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.character_intelligence import CharacterPopularityScore, CharacterProfile
from app.models.creator_intelligence import CreatorPopularityScore, CreatorProfile
from app.models.franchise_intelligence import FranchisePopularityScore, FranchiseProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.intelligence import (
    IntelligenceDashboardRead,
    IntelligenceEntityRankRead,
    IntelligencePopularityBucketRead,
    IntelligenceUpcomingReleaseRead,
)
from app.services.intelligence_matching import match_release_issue


def _latest_character_scores(session: Session, *, limit: int) -> list[IntelligenceEntityRankRead]:
    rows = session.exec(select(CharacterProfile).where(CharacterProfile.status == "ACTIVE")).all()
    ranked: list[IntelligenceEntityRankRead] = []
    for profile in rows:
        score_row = session.exec(
            select(CharacterPopularityScore)
            .where(CharacterPopularityScore.character_id == profile.id)
            .order_by(CharacterPopularityScore.id.desc())
        ).first()
        if not score_row:
            continue
        ranked.append(
            IntelligenceEntityRankRead(
                entity_id=int(profile.id or 0),
                entity_name=profile.character_name,
                entity_type="CHARACTER",
                popularity_score=float(score_row.popularity_score),
                demand_score=float(score_row.demand_score),
                collector_score=float(score_row.collector_score),
            )
        )
    ranked.sort(key=lambda row: row.popularity_score, reverse=True)
    return ranked[:limit]


def _latest_franchise_scores(session: Session, *, limit: int) -> list[IntelligenceEntityRankRead]:
    rows = session.exec(select(FranchiseProfile).where(FranchiseProfile.status == "ACTIVE")).all()
    ranked: list[IntelligenceEntityRankRead] = []
    for profile in rows:
        score_row = session.exec(
            select(FranchisePopularityScore)
            .where(FranchisePopularityScore.franchise_id == profile.id)
            .order_by(FranchisePopularityScore.id.desc())
        ).first()
        if not score_row:
            continue
        ranked.append(
            IntelligenceEntityRankRead(
                entity_id=int(profile.id or 0),
                entity_name=profile.franchise_name,
                entity_type="FRANCHISE",
                popularity_score=float(score_row.popularity_score),
                demand_score=float(score_row.demand_score),
                collector_score=float(score_row.collector_strength_score),
            )
        )
    ranked.sort(key=lambda row: row.popularity_score, reverse=True)
    return ranked[:limit]


def _latest_creator_scores(session: Session, *, limit: int) -> list[IntelligenceEntityRankRead]:
    rows = session.exec(select(CreatorProfile).where(CreatorProfile.status == "ACTIVE")).all()
    ranked: list[IntelligenceEntityRankRead] = []
    for profile in rows:
        score_row = session.exec(
            select(CreatorPopularityScore)
            .where(CreatorPopularityScore.creator_id == profile.id)
            .order_by(CreatorPopularityScore.id.desc())
        ).first()
        if not score_row:
            continue
        ranked.append(
            IntelligenceEntityRankRead(
                entity_id=int(profile.id or 0),
                entity_name=profile.creator_name,
                entity_type="CREATOR",
                popularity_score=float(score_row.popularity_score),
                demand_score=float(score_row.demand_score),
                collector_score=float(score_row.collector_score),
            )
        )
    ranked.sort(key=lambda row: row.popularity_score, reverse=True)
    return ranked[:limit]


def _popularity_distribution(scores: list[float]) -> list[IntelligencePopularityBucketRead]:
    buckets = [
        ("90-100", 90.0, 100.0),
        ("75-89", 75.0, 89.99),
        ("60-74", 60.0, 74.99),
        ("0-59", 0.0, 59.99),
    ]
    result: list[IntelligencePopularityBucketRead] = []
    for label, low, high in buckets:
        count = sum(1 for score in scores if low <= score <= high)
        result.append(IntelligencePopularityBucketRead(bucket_label=label, entity_count=count))
    return result


def build_intelligence_dashboard(session: Session, *, owner_user_id: int, limit: int = 15) -> IntelligenceDashboardRead:
    today = date.today()
    horizon = today + timedelta(days=120)
    issue_rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_date != None)  # noqa: E711
        .where(ReleaseIssue.release_date >= today)
        .where(ReleaseIssue.release_date <= horizon)
    ).all()

    upcoming: list[IntelligenceUpcomingReleaseRead] = []
    for issue, series in issue_rows:
        match = match_release_issue(session, issue=issue, series=series)
        upcoming.append(
            IntelligenceUpcomingReleaseRead(
                release_issue_id=int(issue.id or 0),
                title=issue.title,
                series_name=series.series_name,
                publisher=series.publisher,
                release_date=issue.release_date,
                combined_popularity_score=match.combined_popularity_score,
                matched_entity_count=len(match.matched_entities),
            )
        )
    upcoming.sort(key=lambda row: row.combined_popularity_score, reverse=True)

    top_characters = _latest_character_scores(session, limit=limit)
    top_franchises = _latest_franchise_scores(session, limit=limit)
    top_creators = _latest_creator_scores(session, limit=limit)
    distribution_scores = [row.popularity_score for row in top_characters + top_franchises + top_creators]

    return IntelligenceDashboardRead(
        top_characters=top_characters,
        top_franchises=top_franchises,
        top_creators=top_creators,
        upcoming_releases_by_popularity=upcoming[:limit],
        popularity_distribution=_popularity_distribution(distribution_scores),
        character_count=len(session.exec(select(CharacterProfile)).all()),
        franchise_count=len(session.exec(select(FranchiseProfile)).all()),
        creator_count=len(session.exec(select(CreatorProfile)).all()),
    )
