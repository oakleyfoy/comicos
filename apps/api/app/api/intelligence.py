from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.character_intelligence import CharacterPopularityScore, CharacterProfile
from app.models.creator_intelligence import CreatorPopularityScore, CreatorProfile
from app.models.franchise_intelligence import FranchisePopularityScore, FranchiseProfile
from app.schemas.intelligence import (
    CharacterIntelligenceRead,
    CharacterPopularityScoreRead,
    CharacterProfileRead,
    CreatorIntelligenceRead,
    CreatorPopularityScoreRead,
    CreatorProfileRead,
    FranchiseIntelligenceRead,
    FranchisePopularityScoreRead,
    FranchiseProfileRead,
    IntelligenceCharacterListResponse,
    IntelligenceCreatorListResponse,
    IntelligenceFranchiseListResponse,
    IntelligenceSeedResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.intelligence_dashboard import build_intelligence_dashboard
from app.services.intelligence_matching import sync_owner_release_matches
from app.services.intelligence_seed import catalog_is_seeded, seed_intelligence_catalog

intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Collector Intelligence API v1 (P51-01)"])


def attach_intelligence_layer(app: FastAPI) -> None:
    app.include_router(intelligence_v1_router)


def _character_read(session: Session, profile: CharacterProfile) -> CharacterIntelligenceRead:
    score_row = session.exec(
        select(CharacterPopularityScore)
        .where(CharacterPopularityScore.character_id == profile.id)
        .order_by(CharacterPopularityScore.id.desc())
    ).first()
    latest = CharacterPopularityScoreRead.model_validate(score_row) if score_row else None
    return CharacterIntelligenceRead(profile=CharacterProfileRead.model_validate(profile), latest_score=latest)


def _franchise_read(session: Session, profile: FranchiseProfile) -> FranchiseIntelligenceRead:
    score_row = session.exec(
        select(FranchisePopularityScore)
        .where(FranchisePopularityScore.franchise_id == profile.id)
        .order_by(FranchisePopularityScore.id.desc())
    ).first()
    latest = FranchisePopularityScoreRead.model_validate(score_row) if score_row else None
    return FranchiseIntelligenceRead(profile=FranchiseProfileRead.model_validate(profile), latest_score=latest)


def _creator_read(session: Session, profile: CreatorProfile) -> CreatorIntelligenceRead:
    score_row = session.exec(
        select(CreatorPopularityScore)
        .where(CreatorPopularityScore.creator_id == profile.id)
        .order_by(CreatorPopularityScore.id.desc())
    ).first()
    latest = CreatorPopularityScoreRead.model_validate(score_row) if score_row else None
    return CreatorIntelligenceRead(profile=CreatorProfileRead.model_validate(profile), latest_score=latest)


@intelligence_v1_router.get("/intelligence/characters", response_model=ScanApiV1Envelope)
def v1_intelligence_characters(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    rows = session.exec(select(CharacterProfile).order_by(CharacterProfile.character_name).offset(off).limit(lim)).all()
    total = len(session.exec(select(CharacterProfile)).all())
    body = IntelligenceCharacterListResponse(
        items=[_character_read(session, row) for row in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.get("/intelligence/franchises", response_model=ScanApiV1Envelope)
def v1_intelligence_franchises(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    rows = session.exec(select(FranchiseProfile).order_by(FranchiseProfile.franchise_name).offset(off).limit(lim)).all()
    total = len(session.exec(select(FranchiseProfile)).all())
    body = IntelligenceFranchiseListResponse(
        items=[_franchise_read(session, row) for row in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.get("/intelligence/creators", response_model=ScanApiV1Envelope)
def v1_intelligence_creators(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    rows = session.exec(select(CreatorProfile).order_by(CreatorProfile.creator_name).offset(off).limit(lim)).all()
    total = len(session.exec(select(CreatorProfile)).all())
    body = IntelligenceCreatorListResponse(
        items=[_creator_read(session, row) for row in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.get("/intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_intelligence_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if not catalog_is_seeded(session):
        seed_intelligence_catalog(session)
    sync_owner_release_matches(session, owner_user_id=int(current_user.id))
    body = build_intelligence_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.post("/intelligence/seed", response_model=ScanApiV1Envelope)
def v1_intelligence_seed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    summary = seed_intelligence_catalog(session)
    body = IntelligenceSeedResponse(
        franchise_count=summary.franchise_count,
        character_count=summary.character_count,
        creator_count=summary.creator_count,
        scores_created=summary.scores_created,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
