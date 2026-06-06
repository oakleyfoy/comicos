"""P80-02 mobile inventory operations (`/api/v1/mobile/intake|storage|audit|operations`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.mobile_operations import (
    P80AuditCompleteRead,
    P80AuditCompleteRequest,
    P80AuditScanRead,
    P80AuditScanRequest,
    P80AuditStartRead,
    P80AuditStartRequest,
    P80IntakeCompleteRead,
    P80IntakeCompleteRequest,
    P80IntakeScanRequest,
    P80IntakeScanResultRead,
    P80IntakeSessionRead,
    P80IntakeStartRequest,
    P80OperationsDashboardRead,
    P80StorageAssignRequest,
    P80StorageSuggestionRead,
    P80StorageSuggestRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.mobile_operations_service import (
    audit_scan,
    build_operations_dashboard,
    complete_intake_session,
    complete_mobile_audit,
    get_mobile_audit,
    intake_scan,
    mobile_storage_assign,
    start_intake_session,
    start_mobile_audit,
    suggest_storage,
)

mobile_operations_v1_router = APIRouter(prefix="/api/v1/mobile", tags=["Mobile Operations API v1 (P80-02)"])


def attach_mobile_operations_layer(app: FastAPI) -> None:
    app.include_router(mobile_operations_v1_router)


@mobile_operations_v1_router.post("/intake/start", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_mobile_intake_start(
    payload: P80IntakeStartRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = start_intake_session(
        session,
        owner_user_id=int(current_user.id),
        intake_mode=payload.intake_mode,
        order_id=payload.order_id,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/intake/scan", response_model=ScanApiV1Envelope)
def v1_mobile_intake_scan(
    payload: P80IntakeScanRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    body = intake_scan(
        session,
        current_user=current_user,
        session_id=payload.session_id,
        barcode=payload.barcode,
    )
    session.commit()
    assert current_user.id is not None
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/intake/complete", response_model=ScanApiV1Envelope)
def v1_mobile_intake_complete(
    payload: P80IntakeCompleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_intake_session(
        session,
        owner_user_id=int(current_user.id),
        session_id=payload.session_id,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/storage/suggest", response_model=ScanApiV1Envelope)
def v1_mobile_storage_suggest(
    payload: P80StorageSuggestRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = suggest_storage(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=payload.inventory_copy_id,
        box_id=payload.box_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/storage/assign", response_model=ScanApiV1Envelope)
def v1_mobile_storage_assign(
    payload: P80StorageAssignRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    inventory_copy_id = payload.inventory_copy_id
    if payload.barcode and inventory_copy_id <= 0:
        from app.services.mobile_operations_service import _resolve_copy_id_from_barcode

        resolved, _title = _resolve_copy_id_from_barcode(
            session,
            owner_user_id=int(current_user.id),
            barcode=payload.barcode,
        )
        if resolved is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail="Could not resolve inventory from barcode.")
        inventory_copy_id = resolved
    body = mobile_storage_assign(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
        box_id=payload.box_id,
        slot_number=payload.slot_number,
        use_suggested_slot=payload.use_suggested_slot,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/audit/start", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_mobile_audit_start(
    payload: P80AuditStartRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = start_mobile_audit(
        session,
        owner_user_id=int(current_user.id),
        audit_name=payload.audit_name,
        scope_box_id=payload.scope_box_id,
        scope_location_id=payload.scope_location_id,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/audit/scan", response_model=ScanApiV1Envelope)
def v1_mobile_audit_scan(
    payload: P80AuditScanRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = audit_scan(
        session,
        owner_user_id=int(current_user.id),
        audit_id=payload.audit_id,
        barcode=payload.barcode,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.post("/audit/complete", response_model=ScanApiV1Envelope)
def v1_mobile_audit_complete(
    payload: P80AuditCompleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_mobile_audit(session, owner_user_id=int(current_user.id), audit_id=payload.audit_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.get("/audit/{audit_id}", response_model=ScanApiV1Envelope)
def v1_mobile_audit_get(
    audit_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_mobile_audit(session, owner_user_id=int(current_user.id), audit_id=audit_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@mobile_operations_v1_router.get("/operations", response_model=ScanApiV1Envelope)
def v1_mobile_operations_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_operations_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
