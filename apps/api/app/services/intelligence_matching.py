from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.character_intelligence import CharacterAlias, CharacterProfile
from app.models.creator_intelligence import CreatorAlias, CreatorProfile
from app.models.franchise_intelligence import FranchiseProfile
from app.models.intelligence_matching import ReleaseIntelligenceMatch
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.popularity_engine import (
    character_score,
    combined_popularity_score,
    creator_score,
    franchise_score,
)

ENTITY_CHARACTER = "CHARACTER"
ENTITY_FRANCHISE = "FRANCHISE"
ENTITY_CREATOR = "CREATOR"


@dataclass
class MatchedEntityRead:
    entity_type: str
    entity_id: int
    entity_name: str
    match_confidence: float


@dataclass
class ReleaseMatchResult:
    release_issue_id: int
    release_variant_id: int | None
    matched_entities: list[MatchedEntityRead] = field(default_factory=list)
    combined_popularity_score: float = 0.0


@dataclass(frozen=True)
class IntelligenceMatchCatalog:
    franchises: tuple[FranchiseProfile, ...]
    characters: tuple[tuple[CharacterProfile, tuple[str, ...]], ...]
    creators: tuple[tuple[CreatorProfile, tuple[str, ...]], ...]


def build_intelligence_match_catalog(session: Session) -> IntelligenceMatchCatalog:
    franchises = tuple(
        session.exec(select(FranchiseProfile).where(FranchiseProfile.status == "ACTIVE")).all()
    )
    characters = tuple(
        session.exec(select(CharacterProfile).where(CharacterProfile.status == "ACTIVE")).all()
    )
    char_ids = [int(c.id or 0) for c in characters if c.id is not None]
    char_alias_map: dict[int, list[str]] = {cid: [] for cid in char_ids}
    if char_ids:
        for alias in session.exec(
            select(CharacterAlias).where(CharacterAlias.character_id.in_(char_ids))
        ).all():
            char_alias_map.setdefault(int(alias.character_id), []).append(alias.alias_name)

    character_rows: list[tuple[CharacterProfile, tuple[str, ...]]] = []
    for character in characters:
        cid = int(character.id or 0)
        names = (character.character_name, *tuple(char_alias_map.get(cid, [])))
        character_rows.append((character, names))

    creators = tuple(
        session.exec(select(CreatorProfile).where(CreatorProfile.status == "ACTIVE")).all()
    )
    creator_ids = [int(c.id or 0) for c in creators if c.id is not None]
    creator_alias_map: dict[int, list[str]] = {cid: [] for cid in creator_ids}
    if creator_ids:
        for alias in session.exec(
            select(CreatorAlias).where(CreatorAlias.creator_id.in_(creator_ids))
        ).all():
            creator_alias_map.setdefault(int(alias.creator_id), []).append(alias.alias_name)

    creator_rows: list[tuple[CreatorProfile, tuple[str, ...]]] = []
    for creator in creators:
        cid = int(creator.id or 0)
        names = (creator.creator_name, *tuple(creator_alias_map.get(cid, [])))
        creator_rows.append((creator, names))

    return IntelligenceMatchCatalog(
        franchises=franchises,
        characters=tuple(character_rows),
        creators=tuple(creator_rows),
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains_token(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    normalized_needle = _normalize(needle)
    normalized_haystack = _normalize(haystack)
    if len(normalized_needle) < 3:
        return normalized_needle in normalized_haystack
    pattern = rf"\b{re.escape(normalized_needle)}\b"
    return re.search(pattern, normalized_haystack) is not None


def _match_franchises_from_catalog(
    catalog: IntelligenceMatchCatalog,
    *,
    series_name: str,
    title: str,
) -> list[MatchedEntityRead]:
    matches: list[MatchedEntityRead] = []
    for franchise in catalog.franchises:
        name = franchise.franchise_name
        confidence = 0.0
        if _normalize(series_name) == _normalize(name):
            confidence = 0.95
        elif _contains_token(series_name, name) or _contains_token(title, name):
            confidence = 0.82
        if confidence > 0:
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_FRANCHISE,
                    entity_id=int(franchise.id or 0),
                    entity_name=name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:3]


def _match_franchises(session: Session, *, series_name: str, title: str) -> list[MatchedEntityRead]:
    matches: list[MatchedEntityRead] = []
    for franchise in session.exec(select(FranchiseProfile).where(FranchiseProfile.status == "ACTIVE")).all():
        name = franchise.franchise_name
        confidence = 0.0
        if _normalize(series_name) == _normalize(name):
            confidence = 0.95
        elif _contains_token(series_name, name) or _contains_token(title, name):
            confidence = 0.82
        if confidence > 0:
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_FRANCHISE,
                    entity_id=int(franchise.id or 0),
                    entity_name=name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:3]


def _match_characters_from_catalog(
    catalog: IntelligenceMatchCatalog,
    *,
    publisher: str,
    series_name: str,
    title: str,
) -> list[MatchedEntityRead]:
    haystack = f"{series_name} {title}"
    matches: list[MatchedEntityRead] = []
    for character, names in catalog.characters:
        confidence = 0.0
        for name in names:
            if _contains_token(haystack, name):
                confidence = max(confidence, 0.9 if _normalize(name) == _normalize(series_name) else 0.78)
        if confidence > 0:
            if publisher and character.publisher and _normalize(character.publisher) != _normalize(publisher):
                confidence = round(confidence * 0.92, 3)
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_CHARACTER,
                    entity_id=int(character.id or 0),
                    entity_name=character.character_name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:5]


def _match_characters(session: Session, *, publisher: str, series_name: str, title: str) -> list[MatchedEntityRead]:
    haystack = f"{series_name} {title}"
    matches: list[MatchedEntityRead] = []
    for character in session.exec(select(CharacterProfile).where(CharacterProfile.status == "ACTIVE")).all():
        names = [character.character_name]
        aliases = session.exec(select(CharacterAlias).where(CharacterAlias.character_id == character.id)).all()
        names.extend(alias.alias_name for alias in aliases)
        confidence = 0.0
        for name in names:
            if _contains_token(haystack, name):
                confidence = max(confidence, 0.9 if _normalize(name) == _normalize(series_name) else 0.78)
        if confidence > 0:
            if publisher and character.publisher and _normalize(character.publisher) != _normalize(publisher):
                confidence = round(confidence * 0.92, 3)
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_CHARACTER,
                    entity_id=int(character.id or 0),
                    entity_name=character.character_name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:5]


def _match_creators_from_catalog(
    catalog: IntelligenceMatchCatalog,
    *,
    title: str,
    variant: ReleaseVariant | None,
) -> list[MatchedEntityRead]:
    haystack = title
    if variant and variant.cover_artist:
        haystack = f"{haystack} {variant.cover_artist}"
    matches: list[MatchedEntityRead] = []
    for creator, names in catalog.creators:
        confidence = 0.0
        for name in names:
            if _contains_token(haystack, name):
                confidence = max(confidence, 0.88 if variant and variant.cover_artist else 0.72)
        if confidence > 0:
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_CREATOR,
                    entity_id=int(creator.id or 0),
                    entity_name=creator.creator_name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:3]


def _match_creators(session: Session, *, title: str, variant: ReleaseVariant | None) -> list[MatchedEntityRead]:
    haystack = title
    if variant and variant.cover_artist:
        haystack = f"{haystack} {variant.cover_artist}"
    matches: list[MatchedEntityRead] = []
    for creator in session.exec(select(CreatorProfile).where(CreatorProfile.status == "ACTIVE")).all():
        names = [creator.creator_name]
        aliases = session.exec(select(CreatorAlias).where(CreatorAlias.creator_id == creator.id)).all()
        names.extend(alias.alias_name for alias in aliases)
        confidence = 0.0
        for name in names:
            if _contains_token(haystack, name):
                confidence = max(confidence, 0.88 if variant and variant.cover_artist else 0.72)
        if confidence > 0:
            matches.append(
                MatchedEntityRead(
                    entity_type=ENTITY_CREATOR,
                    entity_id=int(creator.id or 0),
                    entity_name=creator.creator_name,
                    match_confidence=confidence,
                )
            )
    matches.sort(key=lambda row: row.match_confidence, reverse=True)
    return matches[:3]


def match_release_issue(
    session: Session,
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variant: ReleaseVariant | None = None,
    catalog: IntelligenceMatchCatalog | None = None,
    popularity_fn: Callable[[str, int], float] | None = None,
) -> ReleaseMatchResult:
    if catalog is None:
        franchises = _match_franchises(session, series_name=series.series_name, title=issue.title)
        characters = _match_characters(
            session,
            publisher=series.publisher,
            series_name=series.series_name,
            title=issue.title,
        )
        creators = _match_creators(session, title=issue.title, variant=variant)
    else:
        franchises = _match_franchises_from_catalog(
            catalog, series_name=series.series_name, title=issue.title
        )
        characters = _match_characters_from_catalog(
            catalog,
            publisher=series.publisher,
            series_name=series.series_name,
            title=issue.title,
        )
        creators = _match_creators_from_catalog(catalog, title=issue.title, variant=variant)
    matched = franchises + characters + creators

    def _pop(entity_type: str, entity_id: int) -> float:
        if popularity_fn is not None:
            return popularity_fn(entity_type, entity_id)
        if entity_type == ENTITY_CHARACTER:
            return character_score(session, character_id=entity_id)
        if entity_type == ENTITY_FRANCHISE:
            return franchise_score(session, franchise_id=entity_id)
        if entity_type == ENTITY_CREATOR:
            return creator_score(session, creator_id=entity_id)
        return 0.0

    top_character = next((row for row in matched if row.entity_type == ENTITY_CHARACTER), None)
    top_franchise = next((row for row in matched if row.entity_type == ENTITY_FRANCHISE), None)
    top_creator = next((row for row in matched if row.entity_type == ENTITY_CREATOR), None)
    combined = combined_popularity_score(
        character=_pop(ENTITY_CHARACTER, top_character.entity_id) if top_character else 0.0,
        franchise=_pop(ENTITY_FRANCHISE, top_franchise.entity_id) if top_franchise else 0.0,
        creator=_pop(ENTITY_CREATOR, top_creator.entity_id) if top_creator else 0.0,
    )
    return ReleaseMatchResult(
        release_issue_id=int(issue.id or 0),
        release_variant_id=int(variant.id) if variant and variant.id else None,
        matched_entities=matched,
        combined_popularity_score=combined,
    )


def sync_owner_release_matches(session: Session, *, owner_user_id: int) -> int:
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    upserted = 0
    for issue, series in rows:
        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue.id)).all()
        targets: list[tuple[ReleaseVariant | None, ReleaseMatchResult]] = [
            (None, match_release_issue(session, issue=issue, series=series))
        ]
        for variant in variants:
            targets.append((variant, match_release_issue(session, issue=issue, series=series, variant=variant)))
        for variant, result in targets:
            for entity in result.matched_entities:
                existing = session.exec(
                    select(ReleaseIntelligenceMatch)
                    .where(ReleaseIntelligenceMatch.owner_user_id == owner_user_id)
                    .where(ReleaseIntelligenceMatch.release_issue_id == issue.id)
                    .where(ReleaseIntelligenceMatch.release_variant_id == (variant.id if variant else None))
                    .where(ReleaseIntelligenceMatch.entity_type == entity.entity_type)
                    .where(ReleaseIntelligenceMatch.entity_id == entity.entity_id)
                ).first()
                payload = {"entity_name": entity.entity_name}
                if existing:
                    existing.match_confidence = entity.match_confidence
                    existing.match_payload_json = payload
                    session.add(existing)
                else:
                    session.add(
                        ReleaseIntelligenceMatch(
                            owner_user_id=owner_user_id,
                            release_issue_id=int(issue.id or 0),
                            release_variant_id=int(variant.id) if variant and variant.id else None,
                            entity_type=entity.entity_type,
                            entity_id=entity.entity_id,
                            match_confidence=entity.match_confidence,
                            match_payload_json=payload,
                        )
                    )
                upserted += 1
    session.commit()
    return upserted
