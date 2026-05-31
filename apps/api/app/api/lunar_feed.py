from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.lunar_feed import (
    LunarCredentialStatusRead,
    LunarFeedDashboardRead,
    LunarFeedImportSummaryRead,
    LunarRemoteDownloadRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, build_meta, wrap_object
from app.services.lunar_credentials import get_credential_status
from app.services.lunar_feed_dashboard import build_lunar_feed_dashboard
from app.services.lunar_feed_downloader import (
    download_latest_monthly_products_csv,
    download_monthly_products_csv,
)
from app.services.lunar_feed_import import import_latest_lunar_csv_from_remote, import_lunar_csv_bytes
from app.services.lunar_variant_repair import repair_lunar_variants_for_owner
from app.services.ops_admin import ensure_ops_admin_access

lunar_feed_v1_router = APIRouter(prefix="/api/v1", tags=["Lunar Feed API v1 (P50-04A)"])


def attach_lunar_feed_layer(app: FastAPI) -> None:
    app.include_router(lunar_feed_v1_router)


def _require_lunar_admin(current_user: User) -> None:
    ensure_ops_admin_access(current_user, get_settings())


@lunar_feed_v1_router.get("/lunar-feed/credential-status", response_model=ScanApiV1Envelope)
def v1_lunar_feed_credential_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    status = get_credential_status()
    body = LunarCredentialStatusRead(
        credential_available=status.credential_available,
        username_masked=status.username_masked,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.get("/lunar-feed/dashboard", response_model=ScanApiV1Envelope)
def v1_lunar_feed_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    body = build_lunar_feed_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.post("/lunar-feed/download/latest", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_lunar_feed_download_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    try:
        downloaded = download_latest_monthly_products_csv()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body = LunarRemoteDownloadRead(
        file_name=downloaded.file_name,
        file_period=downloaded.file_period,
        file_type=downloaded.file_type,
        source_url=downloaded.source_url,
        byte_size=len(downloaded.content_bytes),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.post("/lunar-feed/download/{period}", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_lunar_feed_download_period(
    period: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    try:
        downloaded = download_monthly_products_csv(period)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body = LunarRemoteDownloadRead(
        file_name=downloaded.file_name,
        file_period=downloaded.file_period,
        file_type=downloaded.file_type,
        source_url=downloaded.source_url,
        byte_size=len(downloaded.content_bytes),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.post("/lunar-feed/import/latest-remote", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_lunar_feed_import_latest_remote(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    try:
        body = import_latest_lunar_csv_from_remote(session, owner_user_id=int(current_user.id))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.post("/lunar-feed/import/upload", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
async def v1_lunar_feed_import_upload(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    content = await file.read()
    body = import_lunar_csv_bytes(
        session,
        owner_user_id=int(current_user.id),
        file_name=file.filename or "lunar-upload.csv",
        content_bytes=content,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@lunar_feed_v1_router.post("/lunar-feed/repair-variants", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_lunar_feed_repair_variants(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    _require_lunar_admin(current_user)
    summary = repair_lunar_variants_for_owner(session, owner_user_id=int(current_user.id))
    from dataclasses import asdict

    return ScanApiV1Envelope(
        data=asdict(summary),
        meta=build_meta(owner_user_id=int(current_user.id)),
    )
