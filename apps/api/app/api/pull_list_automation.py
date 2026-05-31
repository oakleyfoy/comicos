from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.models.pull_list import PullListAutomationRun
from app.schemas.pull_list_automation import (
    PullListAutomationRunListResponse,
    PullListAutomationRunRead,
    PullListAutomationRunTriggerResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.pull_list_automation import run_pull_list_refresh

logger = logging.getLogger(__name__)

pull_list_automation_v1_router = APIRouter(prefix="/api/v1", tags=["Pull List Automation API v1 (P52-04)"])


def attach_pull_list_automation_layer(app: FastAPI) -> None:
    app.include_router(pull_list_automation_v1_router)


def _to_read(row: PullListAutomationRun) -> PullListAutomationRunRead:
    return PullListAutomationRunRead(
        id=int(row.id or 0),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        owners_processed=int(row.owners_processed),
        releases_processed=int(row.releases_processed),
        decisions_created=int(row.decisions_created),
        actions_generated=int(row.actions_generated),
        runtime_ms=int(row.runtime_ms),
        error_message=row.error_message or "",
    )


@pull_list_automation_v1_router.get("/pull-list-automation/runs", response_model=ScanApiV1Envelope)
def v1_list_pull_list_automation_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    body = PullListAutomationRunListResponse(
        items=[_to_read(row) for row in page],
        total_items=total,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@pull_list_automation_v1_router.get("/pull-list-automation/latest", response_model=ScanApiV1Envelope)
def v1_latest_pull_list_automation_run(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No pull list automation runs recorded yet.")
    return wrap_object(_to_read(row), owner_user_id=int(current_user.id))


@pull_list_automation_v1_router.post("/pull-list-automation/run", response_model=ScanApiV1Envelope)
def v1_trigger_pull_list_automation_run(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    run = run_pull_list_refresh(session)
    body = PullListAutomationRunTriggerResponse(run=_to_read(run))
    return wrap_object(body, owner_user_id=int(current_user.id))
