from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.ai_spec_certification import (
    AISpecCertificationRunListRead,
    AISpecCertificationRunTriggerResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ai_spec_certification import (
    get_latest_ai_spec_certification,
    list_ai_spec_certification_runs,
    run_ai_spec_certification,
)
from app.services.ops_admin import ensure_ops_admin_access

ai_spec_certification_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["AI Spec Certification API v1 (P60-07)"],
)


def attach_ai_spec_certification_layer(app: FastAPI) -> None:
    app.include_router(ai_spec_certification_v1_router)


@ai_spec_certification_v1_router.get("/ai-spec-certification/runs", response_model=ScanApiV1Envelope)
def v1_list_ai_spec_certification_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_ai_spec_certification_runs(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = AISpecCertificationRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@ai_spec_certification_v1_router.get("/ai-spec-certification/latest", response_model=ScanApiV1Envelope)
def v1_latest_ai_spec_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_ai_spec_certification(session, owner_user_id=int(current_user.id))
    if body is None:
        raise HTTPException(status_code=404, detail="No AI spec certification runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@ai_spec_certification_v1_router.post("/ai-spec-certification/run", response_model=ScanApiV1Envelope)
def v1_run_ai_spec_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body = run_ai_spec_certification(session, owner_user_id=int(current_user.id))
    payload = AISpecCertificationRunTriggerResponse(run=body)
    return wrap_object(payload, owner_user_id=int(current_user.id))
