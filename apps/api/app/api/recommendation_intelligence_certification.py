from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.recommendation_intelligence_certification import get_recommendation_intelligence_certification
from app.services.recommendation_intelligence_health import get_recommendation_intelligence_health
from app.services.recommendation_intelligence_summary import get_recommendation_intelligence_summary
from app.services.recommendation_intelligence_validation import validate_recommendation_intelligence
from app.services.recommendation_quality_calibration import calibrate_recommendation_quality

recommendation_intelligence_certification_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Recommendation Intelligence Certification API v1 (P51-05)"],
)


def attach_recommendation_intelligence_certification_layer(app: FastAPI) -> None:
    app.include_router(recommendation_intelligence_certification_v1_router)


@recommendation_intelligence_certification_v1_router.get(
    "/recommendation-intelligence/validation",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_intelligence_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_recommendation_intelligence(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_certification_v1_router.get(
    "/recommendation-intelligence/health",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_intelligence_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_intelligence_health(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_certification_v1_router.get(
    "/recommendation-intelligence/calibration",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_intelligence_calibration(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = calibrate_recommendation_quality(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_certification_v1_router.get(
    "/recommendation-intelligence/summary",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_intelligence_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_intelligence_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_intelligence_certification_v1_router.get(
    "/recommendation-intelligence/certification",
    response_model=ScanApiV1Envelope,
)
def v1_recommendation_intelligence_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_intelligence_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
