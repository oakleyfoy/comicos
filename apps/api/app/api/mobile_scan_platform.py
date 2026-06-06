"""P80-01 collector mobile scan platform (`/api/v1/mobile/*`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.mobile_scan_platform import (
    P80MobileScanCreateRequest,
    P80MobileScanListResponse,
    P80MobileScanResultRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.p80_mobile_certification import (
    P80MobileCertificationDashboardRead,
    P80MobileCertificationRead,
)
from app.services.mobile_scan_platform_service import (
    create_mobile_scan,
    get_book_intelligence,
    get_mobile_scan,
    list_mobile_scans,
)
from app.services.mobile_scanning_certification import (
    build_mobile_certification_dashboard,
    run_mobile_scanning_certification,
)

mobile_scan_platform_v1_router = APIRouter(prefix="/api/v1/mobile", tags=["Mobile Scan Platform API v1 (P80-01)"])


def attach_mobile_scan_platform_layer(app: FastAPI) -> None:
    app.include_router(mobile_scan_platform_v1_router)


@mobile_scan_platform_v1_router.post("/scan", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_mobile_scan_create(
    payload: P80MobileScanCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_mobile_scan(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_scan_platform_v1_router.get("/scan/{scan_id}", response_model=ScanApiV1Envelope)
def v1_mobile_scan_get(
    scan_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_mobile_scan(session, owner_user_id=int(current_user.id), scan_id=scan_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_scan_platform_v1_router.get("/book/{inventory_id}", response_model=ScanApiV1Envelope)
def v1_mobile_book_lookup(
    inventory_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_book_intelligence(session, owner_user_id=int(current_user.id), inventory_id=inventory_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_scan_platform_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_mobile_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P80MobileCertificationRead = run_mobile_scanning_certification(
        session,
        owner_user_id=int(current_user.id),
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_scan_platform_v1_router.get("/certification-dashboard", response_model=ScanApiV1Envelope)
def v1_mobile_certification_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P80MobileCertificationDashboardRead = build_mobile_certification_dashboard(
        session,
        owner_user_id=int(current_user.id),
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_scan_platform_v1_router.get("/scans", response_model=ScanApiV1Envelope)
def v1_mobile_scan_history(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_mobile_scans(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = P80MobileScanListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
