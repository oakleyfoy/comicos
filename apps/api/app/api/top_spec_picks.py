from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.top_spec_pick import TopSpecPickLatestRead, TopSpecPickListRead
from app.services.top_spec_picks import (
    build_top_spec_pick_summary,
    get_latest_top_spec_picks_read,
    list_top_spec_picks,
    refresh_latest_top_spec_picks,
)

top_spec_picks_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Top Spec Picks API v1 (P60-04)"],
)


def attach_top_spec_picks_layer(app: FastAPI) -> None:
    app.include_router(top_spec_picks_v1_router)


@top_spec_picks_v1_router.get("/top-spec-picks", response_model=ScanApiV1Envelope)
def v1_list_top_spec_picks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_top_spec_picks(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = TopSpecPickListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@top_spec_picks_v1_router.get("/top-spec-picks/latest", response_model=ScanApiV1Envelope)
def v1_latest_top_spec_picks(
    limit: int = Query(20, ge=1, le=20),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_top_spec_picks_read(session, owner_user_id=int(current_user.id), limit=limit)
    return wrap_object(body, owner_user_id=int(current_user.id))


@top_spec_picks_v1_router.post("/top-spec-picks/run", response_model=ScanApiV1Envelope)
def v1_run_top_spec_picks(
    limit: int = Query(20, ge=1, le=20),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = refresh_latest_top_spec_picks(session, owner_user_id=int(current_user.id), limit=limit)
    return wrap_object(body, owner_user_id=int(current_user.id))


@top_spec_picks_v1_router.get("/top-spec-picks/summary", response_model=ScanApiV1Envelope)
def v1_top_spec_pick_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_top_spec_pick_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
