from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.models.lunar_scheduler import LunarScheduledRunError
from app.schemas.lunar_scheduler import (
    LunarSchedulerHistoryRead,
    LunarSchedulerRunNowRead,
    LunarSchedulerSetTimeRequest,
    LunarSchedulerStatusRead,
    LunarScheduledRunRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.lunar_credentials import get_credential_status
from app.services.lunar_scheduler import (
    disable_schedule,
    enable_schedule,
    get_or_create_schedule_config,
    list_scheduled_runs_for_owner,
    run_scheduled_lunar_import,
    set_schedule_time,
)
from app.services.ops_admin import ensure_ops_admin_access

lunar_scheduler_v1_router = APIRouter(prefix="/api/v1", tags=["Lunar Scheduler API v1 (P50-04B)"])


def attach_lunar_scheduler_layer(app: FastAPI) -> None:
    app.include_router(lunar_scheduler_v1_router)


def _require_lunar_admin(current_user: User) -> None:
    ensure_ops_admin_access(current_user, get_settings())


@lunar_scheduler_v1_router.get("/lunar-scheduler/status", response_model=ScanApiV1Envelope)
def v1_lunar_scheduler_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    config = get_or_create_schedule_config(session, owner_user_id=int(current_user.id))
    body = LunarSchedulerStatusRead.from_config(config, credential_available=get_credential_status().credential_available)
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_scheduler_v1_router.get("/lunar-scheduler/history", response_model=ScanApiV1Envelope)
def v1_lunar_scheduler_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    runs, total = list_scheduled_runs_for_owner(session, owner_user_id=int(current_user.id))
    body = LunarSchedulerHistoryRead(
        runs=[LunarScheduledRunRead.model_validate(row) for row in runs],
        total_runs=total,
        no_change_runs=sum(1 for row in runs if row.status == "NO_CHANGE"),
        import_runs=sum(1 for row in runs if row.status == "COMPLETED"),
        failed_runs=sum(1 for row in runs if row.status == "FAILED"),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_scheduler_v1_router.post("/lunar-scheduler/run-now", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_lunar_scheduler_run_now(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    try:
        run = run_scheduled_lunar_import(session, owner_user_id=int(current_user.id), trigger_type="MANUAL")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body = LunarSchedulerRunNowRead.from_run(run)
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_scheduler_v1_router.post("/lunar-scheduler/enable", response_model=ScanApiV1Envelope)
def v1_lunar_scheduler_enable(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    config = enable_schedule(session, owner_user_id=int(current_user.id))
    body = LunarSchedulerStatusRead.from_config(config, credential_available=get_credential_status().credential_available)
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_scheduler_v1_router.post("/lunar-scheduler/disable", response_model=ScanApiV1Envelope)
def v1_lunar_scheduler_disable(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    config = disable_schedule(session, owner_user_id=int(current_user.id))
    body = LunarSchedulerStatusRead.from_config(config, credential_available=get_credential_status().credential_available)
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_scheduler_v1_router.post("/lunar-scheduler/set-time", response_model=ScanApiV1Envelope)
def v1_lunar_scheduler_set_time(
    payload: LunarSchedulerSetTimeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    config = set_schedule_time(
        session,
        owner_user_id=int(current_user.id),
        schedule_time=payload.schedule_time,
        timezone_name=payload.timezone,
    )
    body = LunarSchedulerStatusRead.from_config(config, credential_available=get_credential_status().credential_available)
    return wrap_object(body, owner_user_id=int(current_user.id))
