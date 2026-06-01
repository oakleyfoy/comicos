from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.industry_release_scan import (
    IndustryReleaseCandidateListRead,
    IndustryReleaseScanRunListRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.industry_release_scanner import scan_industry_releases
from app.services.industry_release_scans import list_industry_release_candidates, list_industry_release_scans

industry_release_scan_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Release Scanner API v1 (P59-02)"],
)


def attach_industry_release_scan_layer(app: FastAPI) -> None:
    app.include_router(industry_release_scan_v1_router)


@industry_release_scan_v1_router.get("/industry-release-scans", response_model=ScanApiV1Envelope)
def v1_list_industry_release_scans(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_industry_release_scans(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = IndustryReleaseScanRunListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@industry_release_scan_v1_router.post(
    "/industry-release-scans/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_industry_release_scan(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = scan_industry_releases(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_release_scan_v1_router.get("/industry-release-candidates", response_model=ScanApiV1Envelope)
def v1_list_industry_release_candidates(
    scan_run_id: int | None = None,
    publisher_code: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_industry_release_candidates(
        session,
        owner_user_id=int(current_user.id),
        scan_run_id=scan_run_id,
        publisher_code=publisher_code,
        limit=limit,
        offset=offset,
    )
    body = IndustryReleaseCandidateListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
