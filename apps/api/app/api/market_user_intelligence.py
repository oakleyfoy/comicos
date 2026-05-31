from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.user_preference_intelligence import UserPreferenceProfile, UserPreferenceScore
from app.schemas.market_user_intelligence import (
    MarketDemandListResponse,
    MarketUserDashboardRead,
    MarketUserRefreshResponse,
    UserPreferenceCreateRequest,
    UserPreferenceCreateResponse,
    UserPreferenceDisableResponse,
    UserPreferenceListResponse,
    UserPreferenceRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.market_demand_engine import refresh_market_demand
from app.services.market_user_dashboard import build_market_user_dashboard, list_market_demand_entities
from app.services.user_preference_engine import (
    create_manual_preference,
    disable_manual_preference,
    refresh_user_preferences,
)

market_user_intelligence_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Market & User Intelligence API v1 (P51-03)"],
)


def attach_market_user_intelligence_layer(app: FastAPI) -> None:
    app.include_router(market_user_intelligence_v1_router)


def _preference_read(session: Session, profile: UserPreferenceProfile) -> UserPreferenceRead:
    score_row = session.exec(
        select(UserPreferenceScore)
        .where(UserPreferenceScore.preference_profile_id == profile.id)
        .order_by(UserPreferenceScore.id.desc())
    ).first()
    return UserPreferenceRead(
        id=int(profile.id or 0),
        preference_type=profile.preference_type,
        preference_key=profile.preference_key,
        preference_label=profile.preference_label,
        status=profile.status,
        preference_score=float(score_row.preference_score) if score_row else 50.0,
        confidence_score=float(score_row.confidence_score) if score_row else 0.25,
    )


@market_user_intelligence_v1_router.get("/market-user-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_market_user_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_market_user_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@market_user_intelligence_v1_router.get("/market-user-intelligence/market-demand", response_model=ScanApiV1Envelope)
def v1_market_demand(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    items, total = list_market_demand_entities(session, limit=lim, offset=off)
    body = MarketDemandListResponse(items=items, total_items=total, limit=lim, offset=off)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_user_intelligence_v1_router.get("/market-user-intelligence/user-preferences", response_model=ScanApiV1Envelope)
def v1_user_preferences(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    profiles = session.exec(
        select(UserPreferenceProfile)
        .where(UserPreferenceProfile.owner_user_id == int(current_user.id))
        .order_by(UserPreferenceProfile.id.desc())
    ).all()
    page = profiles[off : off + lim]
    items = [_preference_read(session, profile) for profile in page]
    body = UserPreferenceListResponse(items=items, total_items=len(profiles), limit=lim, offset=off)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_user_intelligence_v1_router.post("/market-user-intelligence/user-preferences", response_model=ScanApiV1Envelope)
def v1_create_user_preference(
    payload: UserPreferenceCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    profile = create_manual_preference(
        session,
        owner_user_id=int(current_user.id),
        preference_type=payload.preference_type.strip().upper(),
        preference_label=payload.preference_label.strip(),
        preference_score=payload.preference_score,
    )
    body = UserPreferenceCreateResponse(preference=_preference_read(session, profile))
    return wrap_object(body, owner_user_id=int(current_user.id))


@market_user_intelligence_v1_router.patch(
    "/market-user-intelligence/user-preferences/{profile_id}/disable",
    response_model=ScanApiV1Envelope,
)
def v1_disable_user_preference(
    profile_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    existing = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.id == profile_id,
            UserPreferenceProfile.owner_user_id == int(current_user.id),
        )
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Preference profile not found")
    profile = disable_manual_preference(session, owner_user_id=int(current_user.id), profile_id=profile_id)
    body = UserPreferenceDisableResponse(preference=_preference_read(session, profile))
    return wrap_object(body, owner_user_id=int(current_user.id))


@market_user_intelligence_v1_router.post("/market-user-intelligence/refresh", response_model=ScanApiV1Envelope)
def v1_market_user_refresh(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    market = refresh_market_demand(session)
    user = refresh_user_preferences(session, owner_user_id=int(current_user.id))
    body = MarketUserRefreshResponse(market=market, user_preferences=user)
    return wrap_object(body, owner_user_id=int(current_user.id))
