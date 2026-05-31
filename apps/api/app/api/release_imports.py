from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.release_imports import (
    ReleaseImportErrorListResponse,
    ReleaseImportRunListResponse,
    ReleaseImportUploadRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.release_csv_import import import_csv_feed
from app.services.release_import_dashboard import (
    build_release_import_dashboard,
    get_import_run_detail,
    list_import_errors_for_owner,
    list_import_runs_for_owner,
)
from app.services.release_json_import import import_json_feed

release_imports_v1_router = APIRouter(prefix="/api/v1", tags=["Release Imports API v1 (P50-05)"])


def attach_release_imports_layer(app: FastAPI) -> None:
    app.include_router(release_imports_v1_router)


@release_imports_v1_router.post("/release-imports/json", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_release_import_json(
    payload: ReleaseImportUploadRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    raw_size = len(payload.feed.model_dump_json().encode("utf-8"))
    run, _ = import_json_feed(
        session,
        owner_user_id=int(current_user.id),
        file_name=payload.file_name,
        raw_feed={"feed": payload.feed.model_dump()},
        file_size=raw_size,
    )
    return wrap_object(run, owner_user_id=int(current_user.id))


@release_imports_v1_router.post("/release-imports/csv", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
async def v1_release_import_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    run, _ = import_csv_feed(
        session,
        owner_user_id=int(current_user.id),
        file_name=file.filename or "release-import.csv",
        csv_text=csv_text,
    )
    return wrap_object(run, owner_user_id=int(current_user.id))


@release_imports_v1_router.get("/release-imports/runs", response_model=ScanApiV1Envelope)
def v1_release_import_runs(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_import_runs_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseImportRunListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_imports_v1_router.get("/release-imports/runs/{run_id}", response_model=ScanApiV1Envelope)
def v1_release_import_run_detail(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_import_run_detail(session, owner_user_id=int(current_user.id), run_id=run_id)
    if body is None:
        raise HTTPException(status_code=404, detail="Import run not found")
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_imports_v1_router.get("/release-imports/errors", response_model=ScanApiV1Envelope)
def v1_release_import_errors(
    limit: int = 50,
    offset: int = 0,
    import_run_id: int | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_import_errors_for_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        import_run_id=import_run_id,
    )
    body = ReleaseImportErrorListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_imports_v1_router.get("/release-imports/dashboard", response_model=ScanApiV1Envelope)
def v1_release_import_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_import_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
