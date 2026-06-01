from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.future_release_action import FutureReleaseActionListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_standard_list
from app.services.future_release_actions import (
    list_future_release_actions,
    refresh_and_list_latest_future_release_actions,
)

future_release_action_v1_router = APIRouter(prefix="/api/v1", tags=["Future Release Actions API v1 (P58-04)"])


def attach_future_release_action_layer(app: FastAPI) -> None:
    app.include_router(future_release_action_v1_router)


@future_release_action_v1_router.get("/future-release-actions", response_model=ScanApiV1Envelope)
def v1_list_future_release_actions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_future_release_actions(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = FutureReleaseActionListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@future_release_action_v1_router.get("/future-release-actions/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_future_release_actions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_future_release_actions(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = FutureReleaseActionListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
