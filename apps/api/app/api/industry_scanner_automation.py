from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.industry_scanner_automation import (
    IndustryScannerAutomationRunListRead,
    IndustryScannerAutomationRunTriggerResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.industry_scanner_automation import (
    get_latest_industry_scanner_automation_run,
    list_industry_scanner_automation_runs,
    run_industry_scanner_refresh,
)
from app.services.ops_admin import ensure_ops_admin_access

industry_scanner_automation_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Scanner Automation API v1 (P59-06)"],
)


def attach_industry_scanner_automation_layer(app: FastAPI) -> None:
    app.include_router(industry_scanner_automation_v1_router)


@industry_scanner_automation_v1_router.get("/industry-scanner/runs", response_model=ScanApiV1Envelope)
def v1_list_industry_scanner_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_industry_scanner_automation_runs(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = IndustryScannerAutomationRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@industry_scanner_automation_v1_router.get("/industry-scanner/latest", response_model=ScanApiV1Envelope)
def v1_latest_industry_scanner_run(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_industry_scanner_automation_run(session, owner_user_id=int(current_user.id))
    if body is None:
        raise HTTPException(status_code=404, detail="No industry scanner automation runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_scanner_automation_v1_router.post("/industry-scanner/run", response_model=ScanApiV1Envelope)
def v1_run_industry_scanner_automation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    run = run_industry_scanner_refresh(session, owner_user_id=int(current_user.id), trigger_type="MANUAL")
    from app.services.industry_scanner_automation import _to_read

    body = IndustryScannerAutomationRunTriggerResponse(run=_to_read(run))
    return wrap_object(body, owner_user_id=int(current_user.id))
