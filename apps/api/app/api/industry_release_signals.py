from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.industry_release_signal import IndustryReleaseSignalListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.industry_release_signals import (
    classify_latest_industry_release_signals,
    get_latest_industry_release_signals_read,
    list_industry_release_signals,
)

industry_release_signal_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Release Signals API v1 (P59-03)"],
)


def attach_industry_release_signal_layer(app: FastAPI) -> None:
    app.include_router(industry_release_signal_v1_router)


@industry_release_signal_v1_router.get("/industry-release-signals", response_model=ScanApiV1Envelope)
def v1_list_industry_release_signals(
    scan_run_id: int | None = None,
    signal_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_industry_release_signals(
        session,
        owner_user_id=int(current_user.id),
        scan_run_id=scan_run_id,
        signal_type=signal_type,
        limit=limit,
        offset=offset,
    )
    body = IndustryReleaseSignalListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@industry_release_signal_v1_router.get("/industry-release-signals/latest", response_model=ScanApiV1Envelope)
def v1_latest_industry_release_signals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_industry_release_signals_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_release_signal_v1_router.post("/industry-release-signals/refresh", response_model=ScanApiV1Envelope)
def v1_refresh_industry_release_signals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = classify_latest_industry_release_signals(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
