from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.future_release_match import FutureReleaseMatchListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_standard_list
from app.services.future_release_matches import (
    list_future_release_matches,
    refresh_and_list_latest_future_release_matches,
)

future_release_match_v1_router = APIRouter(prefix="/api/v1", tags=["Future Release Matches API v1 (P58-03)"])


def attach_future_release_match_layer(app: FastAPI) -> None:
    app.include_router(future_release_match_v1_router)


@future_release_match_v1_router.get("/future-release-matches", response_model=ScanApiV1Envelope)
def v1_list_future_release_matches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_future_release_matches(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = FutureReleaseMatchListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@future_release_match_v1_router.get("/future-release-matches/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_future_release_matches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_future_release_matches(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = FutureReleaseMatchListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
