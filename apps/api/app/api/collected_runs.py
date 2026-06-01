from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.collected_run import CollectedRunListRead, CollectedRunSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.collected_runs import (
    build_collected_run_summary,
    list_collected_runs,
    refresh_and_list_latest_collected_runs,
)

collected_run_v1_router = APIRouter(prefix="/api/v1", tags=["Collected Runs API v1 (P58-01)"])


def attach_collected_run_layer(app: FastAPI) -> None:
    app.include_router(collected_run_v1_router)


@collected_run_v1_router.get("/collected-runs", response_model=ScanApiV1Envelope)
def v1_list_collected_runs(
    run_status: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collected_runs(
        session,
        owner_user_id=int(current_user.id),
        run_status=run_status,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectedRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collected_run_v1_router.get("/collected-runs/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_collected_runs(
    run_status: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_collected_runs(
        session,
        owner_user_id=int(current_user.id),
        run_status=run_status,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectedRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collected_run_v1_router.get("/collected-runs/summary", response_model=ScanApiV1Envelope)
def v1_collected_run_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_collected_run_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
