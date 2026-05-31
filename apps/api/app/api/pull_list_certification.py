from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.pull_list_certification import (
    PullListCertificationRunListResponse,
    PullListCertificationRunTriggerResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.pull_list_certification import (
    get_latest_pull_list_certification,
    list_pull_list_certification_runs,
    run_pull_list_certification,
)

pull_list_certification_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Pull List Certification API v1 (P52-05)"],
)


def attach_pull_list_certification_layer(app: FastAPI) -> None:
    app.include_router(pull_list_certification_v1_router)


@pull_list_certification_v1_router.get("/pull-list-certification/runs", response_model=ScanApiV1Envelope)
def v1_list_pull_list_certification_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_pull_list_certification_runs(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = PullListCertificationRunListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@pull_list_certification_v1_router.get("/pull-list-certification/latest", response_model=ScanApiV1Envelope)
def v1_latest_pull_list_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_pull_list_certification(session, owner_user_id=int(current_user.id))
    if body is None:
        raise HTTPException(status_code=404, detail="No pull list certification runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@pull_list_certification_v1_router.post("/pull-list-certification/run", response_model=ScanApiV1Envelope)
def v1_run_pull_list_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body = run_pull_list_certification(session, owner_user_id=int(current_user.id))
    payload = PullListCertificationRunTriggerResponse(run=body)
    return wrap_object(payload, owner_user_id=int(current_user.id))
