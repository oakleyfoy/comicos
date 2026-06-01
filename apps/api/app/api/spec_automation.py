from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.spec_automation import SpecAutomationRunListRead, SpecAutomationRunTriggerResponse
from app.services.spec_automation import (
    get_latest_spec_automation_run,
    list_spec_automation_runs,
    run_spec_refresh,
)

spec_automation_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Spec Automation API v1 (P60-06)"],
)


def attach_spec_automation_layer(app: FastAPI) -> None:
    app.include_router(spec_automation_v1_router)


@spec_automation_v1_router.get("/spec-automation/runs", response_model=ScanApiV1Envelope)
def v1_list_spec_automation_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_spec_automation_runs(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = SpecAutomationRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@spec_automation_v1_router.get("/spec-automation/latest", response_model=ScanApiV1Envelope)
def v1_latest_spec_automation_run(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_spec_automation_run(session, owner_user_id=int(current_user.id))
    if body is None:
        raise HTTPException(status_code=404, detail="No spec automation runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@spec_automation_v1_router.post("/spec-automation/run", response_model=ScanApiV1Envelope)
def v1_run_spec_automation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.spec_automation import _to_read

    run = run_spec_refresh(session, owner_user_id=int(current_user.id))
    body = SpecAutomationRunTriggerResponse(run=_to_read(run))
    return wrap_object(body, owner_user_id=int(current_user.id))
