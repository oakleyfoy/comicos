from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.future_release_certification import FutureReleaseCertificationRunTriggerResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.future_release_certification import (
    get_latest_future_release_certification,
    run_future_release_certification,
)
from app.services.ops_admin import ensure_ops_admin_access

future_release_certification_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Future Release Certification API v1 (P58-06)"],
)


def attach_future_release_certification_layer(app: FastAPI) -> None:
    app.include_router(future_release_certification_v1_router)


@future_release_certification_v1_router.get("/future-release-certification/latest", response_model=ScanApiV1Envelope)
def v1_latest_future_release_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_future_release_certification(session, owner_user_id=int(current_user.id))
    if body is None:
        raise HTTPException(status_code=404, detail="No future release certification runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@future_release_certification_v1_router.post("/future-release-certification/run", response_model=ScanApiV1Envelope)
def v1_run_future_release_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body = run_future_release_certification(session, owner_user_id=int(current_user.id))
    payload = FutureReleaseCertificationRunTriggerResponse(run=body)
    return wrap_object(payload, owner_user_id=int(current_user.id))
