from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.daily_action_engine import DailyActionListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.daily_action_engine import (
    generate_daily_actions,
    get_daily_action_summary,
    list_latest_daily_actions,
    refresh_and_list_latest_daily_actions,
)

daily_action_v1_router = APIRouter(prefix="/api/v1", tags=["Daily Action Engine API v1 (P57-02)"])


def attach_daily_action_engine_layer(app: FastAPI) -> None:
    app.include_router(daily_action_v1_router)


@daily_action_v1_router.get("/daily-actions", response_model=ScanApiV1Envelope)
def v1_daily_actions(
    action_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    due_before: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_daily_actions(
        session,
        owner_user_id=int(current_user.id),
        action_type=action_type,
        priority_min=priority_min,
        due_before=due_before,
        limit=limit,
        offset=offset,
    )
    body = DailyActionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@daily_action_v1_router.get("/daily-actions/latest", response_model=ScanApiV1Envelope)
def v1_daily_actions_latest(
    action_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    due_before: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_daily_actions(
        session,
        owner_user_id=int(current_user.id),
        action_type=action_type,
        priority_min=priority_min,
        due_before=due_before,
        limit=limit,
        offset=offset,
    )
    body = DailyActionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@daily_action_v1_router.get("/daily-actions/summary", response_model=ScanApiV1Envelope)
def v1_daily_actions_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    generate_daily_actions(session, owner_user_id=int(current_user.id))
    body = get_daily_action_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
