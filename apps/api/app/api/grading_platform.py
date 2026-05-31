from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.grading_platform_health import get_grading_platform_health
from app.services.grading_platform_summary import get_grading_platform_certification, get_grading_platform_summary
from app.services.grading_platform_validation import validate_grading_platform

grading_platform_v1_router = APIRouter(prefix="/api/v1", tags=["Grading Platform API v1 (P49-04)"])


def attach_grading_platform_layer(app: FastAPI) -> None:
    app.include_router(grading_platform_v1_router)


@grading_platform_v1_router.get("/grading-platform/summary", response_model=ScanApiV1Envelope)
def v1_grading_platform_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_grading_platform_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_platform_v1_router.get("/grading-platform/health", response_model=ScanApiV1Envelope)
def v1_grading_platform_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_grading_platform_health(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_platform_v1_router.get("/grading-platform/validation", response_model=ScanApiV1Envelope)
def v1_grading_platform_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_grading_platform(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_platform_v1_router.get("/grading-platform/certification", response_model=ScanApiV1Envelope)
def v1_grading_platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_grading_platform_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
