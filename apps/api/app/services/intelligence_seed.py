from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.character_intelligence import CharacterAlias, CharacterPopularityScore, CharacterProfile
from app.models.creator_intelligence import CreatorAlias, CreatorPopularityScore, CreatorProfile
from app.models.franchise_intelligence import FranchisePopularityScore, FranchiseProfile
from app.services.intelligence_catalog_data import (
    CHARACTER_SEEDS,
    CONFIDENCE_BASE,
    CREATOR_SEEDS,
    FRANCHISE_SEEDS,
    SOURCE_VERSION,
    _EXTRA_CHARACTERS,
    _EXTRA_CREATORS,
    _EXTRA_FRANCHISES,
    CharacterSeedRow,
    CreatorSeedRow,
    FranchiseSeedRow,
)
from app.services.popularity_engine import refresh_popularity_scores


@dataclass(frozen=True)
class IntelligenceSeedSummary:
    franchise_count: int
    character_count: int
    creator_count: int
    scores_created: int


def _upsert_franchise(session: Session, row: FranchiseSeedRow) -> FranchiseProfile:
    existing = session.exec(select(FranchiseProfile).where(FranchiseProfile.franchise_name == row.name)).first()
    if existing:
        return existing
    profile = FranchiseProfile(franchise_name=row.name, primary_publisher=row.publisher, status="ACTIVE")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        FranchisePopularityScore(
            franchise_id=int(profile.id or 0),
            popularity_score=row.popularity,
            demand_score=row.demand,
            longevity_score=row.longevity,
            collector_strength_score=row.collector_strength,
            confidence_score=CONFIDENCE_BASE,
            source_version=SOURCE_VERSION,
        )
    )
    session.commit()
    return profile


def _upsert_character(session: Session, row: CharacterSeedRow, franchise_id: int | None) -> CharacterProfile:
    existing = session.exec(
        select(CharacterProfile)
        .where(CharacterProfile.character_name == row.name)
        .where(CharacterProfile.publisher == row.publisher)
    ).first()
    if existing:
        return existing
    profile = CharacterProfile(
        character_name=row.name,
        publisher=row.publisher,
        franchise_id=franchise_id,
        status="ACTIVE",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        CharacterPopularityScore(
            character_id=int(profile.id or 0),
            popularity_score=row.popularity,
            demand_score=row.demand,
            collector_score=row.collector,
            confidence_score=CONFIDENCE_BASE,
            source_version=SOURCE_VERSION,
        )
    )
    for alias in row.aliases:
        session.add(CharacterAlias(character_id=int(profile.id or 0), alias_name=alias))
    session.commit()
    return profile


def _upsert_creator(session: Session, row: CreatorSeedRow) -> CreatorProfile:
    existing = session.exec(
        select(CreatorProfile)
        .where(CreatorProfile.creator_name == row.name)
        .where(CreatorProfile.creator_role == row.role)
    ).first()
    if existing:
        return existing
    profile = CreatorProfile(creator_name=row.name, creator_role=row.role, status="ACTIVE")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    session.add(
        CreatorPopularityScore(
            creator_id=int(profile.id or 0),
            popularity_score=row.popularity,
            demand_score=row.demand,
            collector_score=row.collector,
            confidence_score=CONFIDENCE_BASE,
            source_version=SOURCE_VERSION,
        )
    )
    for alias in row.aliases:
        session.add(CreatorAlias(creator_id=int(profile.id or 0), alias_name=alias))
    session.commit()
    return profile


def seed_intelligence_catalog(session: Session) -> IntelligenceSeedSummary:
    franchise_by_name: dict[str, FranchiseProfile] = {}
    for row in FRANCHISE_SEEDS:
        franchise_by_name[row.name] = _upsert_franchise(session, row)
    for name, publisher, pop in _EXTRA_FRANCHISES:
        extra = FranchiseSeedRow(name, publisher, pop, pop - 2, pop - 4, pop - 1)
        franchise_by_name[name] = _upsert_franchise(session, extra)

    for row in CHARACTER_SEEDS:
        franchise_id = int(franchise_by_name[row.franchise].id or 0) if row.franchise in franchise_by_name else None
        _upsert_character(session, row, franchise_id)
    for name, publisher, franchise, pop in _EXTRA_CHARACTERS:
        franchise_id = int(franchise_by_name[franchise].id or 0) if franchise in franchise_by_name else None
        _upsert_character(
            session,
            CharacterSeedRow(name, publisher, franchise, pop, pop - 2, pop - 1),
            franchise_id,
        )

    for row in CREATOR_SEEDS:
        _upsert_creator(session, row)
    for name, role, pop in _EXTRA_CREATORS:
        _upsert_creator(session, CreatorSeedRow(name, role, pop, pop - 2, pop - 1))

    scores_created = refresh_popularity_scores(session, source_version=SOURCE_VERSION, confidence=CONFIDENCE_BASE)

    franchise_count = len(session.exec(select(FranchiseProfile)).all())
    character_count = len(session.exec(select(CharacterProfile)).all())
    creator_count = len(session.exec(select(CreatorProfile)).all())
    return IntelligenceSeedSummary(
        franchise_count=franchise_count,
        character_count=character_count,
        creator_count=creator_count,
        scores_created=scores_created,
    )


def catalog_is_seeded(session: Session) -> bool:
    return session.exec(select(FranchiseProfile).limit(1)).first() is not None
