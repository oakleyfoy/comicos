from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.data_integrity import MigrationSafetyValidateRequest
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.audit_trail import get_audit_event, list_audit_events
from app.services.data_integrity import get_integrity_check, list_integrity_checks, list_integrity_issues, run_integrity_check
from app.services.migration_safety import list_migration_safety_checks, validate_migration_result
from app.services.ops_admin import ensure_ops_admin_access

data_integrity_v1_router = APIRouter(prefix="/api/v1", tags=["Data Integrity API v1 (P48-02)"])


def attach_data_integrity_layer(app: FastAPI) -> None:
    app.include_router(data_integrity_v1_router)


@data_integrity_v1_router.get("/data-integrity/checks", response_model=ScanApiV1Envelope)
def v1_list_data_integrity_checks(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_integrity_checks(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.get("/data-integrity/checks/{check_id}", response_model=ScanApiV1Envelope)
def v1_get_data_integrity_check(
    check_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_integrity_check(session, owner_user_id=int(current_user.id), check_id=check_id)
    if body is None:
        raise HTTPException(status_code=404, detail="Integrity check not found.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.get("/data-integrity/issues", response_model=ScanApiV1Envelope)
def v1_list_data_integrity_issues(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_integrity_issues(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.post("/data-integrity/run", response_model=ScanApiV1Envelope)
def v1_run_data_integrity_check(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_integrity_check(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.get("/data-integrity/migration-safety", response_model=ScanApiV1Envelope)
def v1_list_migration_safety_checks(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_migration_safety_checks(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.post("/data-integrity/migration-safety/validate", response_model=ScanApiV1Envelope)
def v1_validate_migration_safety(
    payload: MigrationSafetyValidateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body = validate_migration_result(
        session,
        owner_user_id=int(current_user.id),
        migration_revision=payload.migration_revision,
        pre_count_json=payload.pre_count_json,
        post_count_json=payload.post_count_json,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.get("/data-integrity/audit-events", response_model=ScanApiV1Envelope)
def v1_list_data_audit_events(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_audit_events(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@data_integrity_v1_router.get("/data-integrity/audit-events/{audit_event_id}", response_model=ScanApiV1Envelope)
def v1_get_data_audit_event(
    audit_event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_audit_event(session, owner_user_id=int(current_user.id), audit_event_id=audit_event_id)
    return wrap_object(body, owner_user_id=int(current_user.id))
