from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.release_platform_certification import get_release_platform_certification
from app.services.release_platform_health import get_release_platform_health
from app.services.release_platform_summary import get_release_platform_summary
from app.services.release_platform_validation import validate_release_platform

release_platform_certification_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Release Platform Certification API v1 (P50-05)"],
)


def attach_release_platform_certification_layer(app: FastAPI) -> None:
    app.include_router(release_platform_certification_v1_router)


@release_platform_certification_v1_router.get("/release-platform/validation", response_model=ScanApiV1Envelope)
def v1_release_platform_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_release_platform(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_certification_v1_router.get("/release-platform/health", response_model=ScanApiV1Envelope)
def v1_release_platform_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_release_platform_health(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_certification_v1_router.get("/release-platform/summary", response_model=ScanApiV1Envelope)
def v1_release_platform_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_release_platform_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_platform_certification_v1_router.get("/release-platform/certification", response_model=ScanApiV1Envelope)
def v1_release_platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_release_platform_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
