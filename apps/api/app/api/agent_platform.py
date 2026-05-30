from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.agent_platform_validation import validate_platform, validate_platform_summary
from app.services.agent_readiness_report import generate_agent_platform_readiness_report

agent_platform_v1_router = APIRouter(prefix="/api/v1", tags=["Agent Platform API v1 (P45-08)"])


def attach_agent_platform_layer(app: FastAPI) -> None:
    app.include_router(agent_platform_v1_router)


@agent_platform_v1_router.get("/agent-platform/readiness", response_model=ScanApiV1Envelope)
def v1_get_agent_platform_readiness(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_agent_platform_readiness_report(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@agent_platform_v1_router.get("/agent-platform/validation", response_model=ScanApiV1Envelope)
def v1_get_agent_platform_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_platform(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@agent_platform_v1_router.get("/agent-platform/summary", response_model=ScanApiV1Envelope)
def v1_get_agent_platform_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_platform_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
