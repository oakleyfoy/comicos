from __future__ import annotations

from sqlmodel import Session, select

from app.models.character_intelligence import CharacterPopularityScore, CharacterProfile
from app.models.creator_intelligence import CreatorPopularityScore, CreatorProfile
from app.models.franchise_intelligence import FranchisePopularityScore, FranchiseProfile
from app.services.intelligence_catalog_data import CONFIDENCE_BASE, SOURCE_VERSION


def _latest_character_score(session: Session, *, character_id: int) -> CharacterPopularityScore | None:
    return session.exec(
        select(CharacterPopularityScore)
        .where(CharacterPopularityScore.character_id == character_id)
        .order_by(CharacterPopularityScore.id.desc())
    ).first()


def _latest_franchise_score(session: Session, *, franchise_id: int) -> FranchisePopularityScore | None:
    return session.exec(
        select(FranchisePopularityScore)
        .where(FranchisePopularityScore.franchise_id == franchise_id)
        .order_by(FranchisePopularityScore.id.desc())
    ).first()


def _latest_creator_score(session: Session, *, creator_id: int) -> CreatorPopularityScore | None:
    return session.exec(
        select(CreatorPopularityScore)
        .where(CreatorPopularityScore.creator_id == creator_id)
        .order_by(CreatorPopularityScore.id.desc())
    ).first()


def refresh_popularity_scores(
    session: Session,
    *,
    source_version: str = SOURCE_VERSION,
    confidence: float = CONFIDENCE_BASE,
) -> int:
    created = 0
    for profile in session.exec(select(CharacterProfile)).all():
        latest = _latest_character_score(session, character_id=int(profile.id or 0))
        if latest and latest.source_version == source_version:
            continue
        base = latest.popularity_score if latest else 70.0
        session.add(
            CharacterPopularityScore(
                character_id=int(profile.id or 0),
                popularity_score=round(base, 2),
                demand_score=round(max(base - 2.0, 0.0), 2),
                collector_score=round(max(base - 1.0, 0.0), 2),
                confidence_score=round(confidence, 3),
                source_version=source_version,
            )
        )
        created += 1
    for profile in session.exec(select(FranchiseProfile)).all():
        latest = _latest_franchise_score(session, franchise_id=int(profile.id or 0))
        if latest and latest.source_version == source_version:
            continue
        base = latest.popularity_score if latest else 68.0
        session.add(
            FranchisePopularityScore(
                franchise_id=int(profile.id or 0),
                popularity_score=round(base, 2),
                demand_score=round(max(base - 2.0, 0.0), 2),
                longevity_score=round(max(base - 1.5, 0.0), 2),
                collector_strength_score=round(max(base - 1.0, 0.0), 2),
                confidence_score=round(confidence, 3),
                source_version=source_version,
            )
        )
        created += 1
    for profile in session.exec(select(CreatorProfile)).all():
        latest = _latest_creator_score(session, creator_id=int(profile.id or 0))
        if latest and latest.source_version == source_version:
            continue
        base = latest.popularity_score if latest else 65.0
        session.add(
            CreatorPopularityScore(
                creator_id=int(profile.id or 0),
                popularity_score=round(base, 2),
                demand_score=round(max(base - 2.0, 0.0), 2),
                collector_score=round(max(base - 1.0, 0.0), 2),
                confidence_score=round(confidence, 3),
                source_version=source_version,
            )
        )
        created += 1
    session.commit()
    return created


def character_score(session: Session, *, character_id: int) -> float:
    row = _latest_character_score(session, character_id=character_id)
    return float(row.popularity_score) if row else 0.0


def franchise_score(session: Session, *, franchise_id: int) -> float:
    row = _latest_franchise_score(session, franchise_id=franchise_id)
    return float(row.popularity_score) if row else 0.0


def creator_score(session: Session, *, creator_id: int) -> float:
    row = _latest_creator_score(session, creator_id=creator_id)
    return float(row.popularity_score) if row else 0.0


def combined_popularity_score(
    *,
    character: float,
    franchise: float,
    creator: float,
) -> float:
    weights = (0.45, 0.35, 0.20)
    values = (character, franchise, creator)
    active = [(weight, value) for weight, value in zip(weights, values, strict=True) if value > 0.0]
    if not active:
        return 0.0
    total_weight = sum(weight for weight, _ in active)
    score = sum(weight * value for weight, value in active) / total_weight
    return round(score, 2)
