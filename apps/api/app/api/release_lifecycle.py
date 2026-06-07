from __future__ import annotations

import os

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.release_lifecycle import (
    P86ReleaseLifecycleDashboardRead,
    P86ReleaseLifecycleLatestReportRead,
    P86ReleaseLifecyclePlanRead,
    P86ReleaseLifecycleRunListRead,
    P86ReleaseLifecycleWeeklyRunResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_report_service import finalize_weekly_lifecycle_report, get_latest_lifecycle_report
from app.services.release_lifecycle_scheduler import (
    ReleaseLifecycleStopError,
    retry_lifecycle_run,
    run_weekly_lifecycle_batch,
)
from app.services.release_lifecycle_service import (
    build_lifecycle_dashboard,
    build_lifecycle_plan_read,
    list_lifecycle_runs,
)

release_lifecycle_v1_router = APIRouter(
    prefix="/api/v1/release-lifecycle",
    tags=["Release Lifecycle API v1 (P86)"],
)


def attach_release_lifecycle_layer(app: FastAPI) -> None:
    app.include_router(release_lifecycle_v1_router)


@release_lifecycle_v1_router.get("/plan", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_plan(
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P86ReleaseLifecyclePlanRead = build_lifecycle_plan_read()
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_lifecycle_v1_router.post("/run-weekly", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_run_weekly(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    database_url = os.environ.get("DATABASE_URL", "").strip() or settings.database_url
    if not database_url.strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured for lifecycle capture.")
    try:
        plan = build_weekly_lifecycle_plan()
        runs = run_weekly_lifecycle_batch(session, database_url=database_url, plan=plan)
    except ReleaseLifecycleStopError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from app.services.release_lifecycle_service import _to_read

    report_id: int | None = None
    if runs:
        report = finalize_weekly_lifecycle_report(
            session,
            owner_id=int(current_user.id),
            plan=plan,
            runs=runs,
        )
        if report is not None:
            report_id = int(report.id or 0)

    body = P86ReleaseLifecycleWeeklyRunResponse(
        runs=[_to_read(r) for r in runs],
        skipped=len(runs) == 0,
        message="Weekly batch skipped (duplicate active job) or completed with no new runs." if not runs else "",
        report_id=report_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_lifecycle_v1_router.get("/latest-report", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_latest_report(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P86ReleaseLifecycleLatestReportRead = get_latest_lifecycle_report(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_lifecycle_v1_router.get("/runs", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P86ReleaseLifecycleRunListRead = list_lifecycle_runs(
        session,
        owner_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_lifecycle_v1_router.get("/dashboard", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P86ReleaseLifecycleDashboardRead = build_lifecycle_dashboard(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_lifecycle_v1_router.post("/runs/{run_id}/retry", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_retry_run(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    database_url = os.environ.get("DATABASE_URL", "").strip() or settings.database_url
    if not database_url.strip():
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured for lifecycle capture.")
    try:
        row = retry_lifecycle_run(
            session,
            run_id=run_id,
            owner_id=int(current_user.id),
            database_url=database_url,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReleaseLifecycleStopError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from app.services.release_lifecycle_service import _to_read

    return wrap_object(_to_read(row), owner_user_id=int(current_user.id))
