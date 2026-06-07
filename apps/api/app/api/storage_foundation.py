"""P79-01 / P79-02 storage foundation, locator, and audit API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.storage_foundation import (
    P79StorageAssignPayload,
    P79StorageBoxCreate,
    P79StorageBoxListResponse,
    P79StorageLocationCreate,
    P79StorageLocationListResponse,
    P79StorageSearchResponse,
)
from app.schemas.storage_locator_audit import (
    P79StorageAuditActionPayload,
    P79StorageAuditCreate,
    P79StorageAuditListResponse,
)
from app.services.storage_assignment_service import StorageAssignmentError, assign_inventory_copy
from app.services.storage_dashboard_service import build_storage_dashboard
from app.services.storage_location_service import (
    StorageLocationError,
    create_storage_box,
    create_storage_location,
    list_storage_boxes,
    list_storage_locations,
    seed_office_template,
)
from app.services.storage_search_service import search_storage
from app.services.inventory_locator_service import locate_inventory
from app.services.box_contents_service import get_box_contents
from app.services.storage_audit_service import (
    StorageAuditError,
    complete_audit,
    create_audit_session,
    get_audit_detail,
    list_audit_sessions,
    mark_missing,
    mark_verified,
    record_unexpected,
)
from app.services.storage_label_service import build_storage_label
from app.schemas.storage_analytics import P79StorageCertificationRead
from app.services.storage_analytics_service import (
    build_analytics_dashboard,
    build_analytics_read,
    build_audit_analytics_read,
    build_health_read,
    build_unassigned_dashboard,
    build_utilization_response,
)
from app.services.storage_intelligence_certification import run_storage_intelligence_certification

storage_v1_router = APIRouter(prefix="/api/v1", tags=["Storage API v1 (P79-01 / P79-02 / P79-03)"])


def attach_storage_foundation_layer(app: FastAPI) -> None:
    app.include_router(storage_v1_router)


@storage_v1_router.get("/storage/locations", response_model=ScanApiV1Envelope)
def v1_storage_locations_list(
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import safe_storage_locations_list

    body = safe_storage_locations_list(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/locations", response_model=ScanApiV1Envelope)
def v1_storage_locations_create(
    payload: P79StorageLocationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    try:
        if payload.seed_office_template:
            row = seed_office_template(session, owner_user_id=owner_id)
        else:
            row = create_storage_location(
                session,
                owner_user_id=owner_id,
                parent_id=payload.parent_id,
                location_kind=payload.location_kind,
                name=payload.name,
                description=payload.description,
                capacity=payload.capacity,
                is_active=payload.is_active,
                sort_order=payload.sort_order,
            )
    except StorageLocationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from app.schemas.storage_foundation import P79StorageLocationRead
    from app.services.storage_capacity import location_tree_metrics

    occ, rem, util = location_tree_metrics(session, owner_user_id=owner_id, location_id=int(row.id or 0))
    body = P79StorageLocationRead(
        id=int(row.id or 0),
        parent_id=row.parent_id,
        location_kind=row.location_kind,
        name=row.name,
        description=row.description,
        capacity=row.capacity,
        is_active=row.is_active,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
        utilization_pct=util,
        current_occupancy=occ,
        remaining_capacity=rem,
    )
    return wrap_object(body, owner_user_id=owner_id)


@storage_v1_router.get("/storage/boxes", response_model=ScanApiV1Envelope)
def v1_storage_boxes_list(
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_storage_boxes(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = P79StorageBoxListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/boxes", response_model=ScanApiV1Envelope)
def v1_storage_boxes_create(
    payload: P79StorageBoxCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    try:
        box = create_storage_box(
            session,
            owner_user_id=owner_id,
            shelf_location_id=payload.shelf_location_id,
            name=payload.name,
            description=payload.description,
            capacity=payload.capacity,
            is_active=payload.is_active,
        )
    except StorageLocationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, _ = list_storage_boxes(session, owner_user_id=owner_id, limit=1, offset=0)
    match = next((b for b in items if b.id == int(box.id or 0)), items[0] if items else None)
    if match is None:
        from app.services.storage_capacity import box_metrics
        from app.services.storage_assignment_service import suggest_next_slot_number
        from app.schemas.storage_foundation import P79StorageBoxRead

        m = box_metrics(session, box=box)
        match = P79StorageBoxRead(
            id=int(box.id or 0),
            shelf_location_id=box.shelf_location_id,
            name=box.name,
            description=box.description,
            capacity=box.capacity,
            is_active=box.is_active,
            current_occupancy=int(m["current_occupancy"]),
            remaining_capacity=int(m["remaining_capacity"]),
            utilization_pct=float(m["utilization_pct"]),
            suggested_next_slot=suggest_next_slot_number(session, box_id=int(box.id or 0)),
            created_at=box.created_at,
            updated_at=box.updated_at,
        )
    return wrap_object(match, owner_user_id=owner_id)


@storage_v1_router.post("/storage/assign", response_model=ScanApiV1Envelope)
def v1_storage_assign(
    payload: P79StorageAssignPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    try:
        body = assign_inventory_copy(
            session,
            owner_user_id=owner_id,
            inventory_copy_id=payload.inventory_copy_id,
            box_id=payload.box_id,
            slot_number=payload.slot_number,
            use_suggested_slot=payload.use_suggested_slot,
            assigned_by_user_id=owner_id,
        )
    except StorageAssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=owner_id)


@storage_v1_router.get("/storage/search", response_model=ScanApiV1Envelope)
def v1_storage_search(
    q: str = Query("", min_length=0),
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P79StorageSearchResponse = search_storage(
        session, owner_user_id=int(current_user.id), query=q, limit=limit
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/dashboard", response_model=ScanApiV1Envelope)
def v1_storage_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import safe_storage_dashboard

    body = safe_storage_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/locator", response_model=ScanApiV1Envelope)
def v1_storage_locator(
    q: str = Query("", min_length=0),
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = locate_inventory(session, owner_user_id=int(current_user.id), query=q, limit=limit)
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/boxes/{box_id}/contents", response_model=ScanApiV1Envelope)
def v1_storage_box_contents(
    box_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_box_contents(session, owner_user_id=int(current_user.id), box_id=box_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/audits", response_model=ScanApiV1Envelope)
def v1_storage_audits_create(
    payload: P79StorageAuditCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    try:
        row = create_audit_session(
            session,
            owner_user_id=owner_id,
            audit_name=payload.audit_name,
            scope_box_id=payload.scope_box_id,
            scope_location_id=payload.scope_location_id,
        )
        body = get_audit_detail(session, owner_user_id=owner_id, audit_id=int(row.id or 0))
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=owner_id)


@storage_v1_router.get("/storage/audits", response_model=ScanApiV1Envelope)
def v1_storage_audits_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_audit_sessions(session, owner_user_id=int(current_user.id))
    body = P79StorageAuditListResponse(items=items, total_items=len(items))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/audits/{audit_id}", response_model=ScanApiV1Envelope)
def v1_storage_audits_get(
    audit_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_audit_detail(session, owner_user_id=int(current_user.id), audit_id=audit_id)
    except StorageAuditError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/audits/{audit_id}/verify", response_model=ScanApiV1Envelope)
def v1_storage_audits_verify(
    audit_id: int,
    payload: P79StorageAuditActionPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.entry_id is None:
        raise HTTPException(status_code=400, detail="entry_id required")
    try:
        body = mark_verified(
            session,
            owner_user_id=int(current_user.id),
            audit_id=audit_id,
            entry_id=payload.entry_id,
        )
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/audits/{audit_id}/missing", response_model=ScanApiV1Envelope)
def v1_storage_audits_missing(
    audit_id: int,
    payload: P79StorageAuditActionPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.entry_id is None:
        raise HTTPException(status_code=400, detail="entry_id required")
    try:
        body = mark_missing(
            session,
            owner_user_id=int(current_user.id),
            audit_id=audit_id,
            entry_id=payload.entry_id,
            notes=payload.notes,
        )
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/audits/{audit_id}/unexpected", response_model=ScanApiV1Envelope)
def v1_storage_audits_unexpected(
    audit_id: int,
    payload: P79StorageAuditActionPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.inventory_copy_id is None or payload.storage_box_id is None:
        raise HTTPException(status_code=400, detail="inventory_copy_id and storage_box_id required")
    try:
        body = record_unexpected(
            session,
            owner_user_id=int(current_user.id),
            audit_id=audit_id,
            inventory_copy_id=payload.inventory_copy_id,
            storage_box_id=payload.storage_box_id,
            slot_number=payload.slot_number,
            notes=payload.notes,
            move_to_box=payload.move_to_box,
        )
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.post("/storage/audits/{audit_id}/complete", response_model=ScanApiV1Envelope)
def v1_storage_audits_complete(
    audit_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = complete_audit(session, owner_user_id=int(current_user.id), audit_id=audit_id)
    except StorageAuditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/labels/{entity_type}/{entity_id}", response_model=ScanApiV1Envelope)
def v1_storage_labels(
    entity_type: str,
    entity_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = build_storage_label(
            session,
            owner_user_id=int(current_user.id),
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/analytics", response_model=ScanApiV1Envelope)
def v1_storage_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_analytics_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/utilization", response_model=ScanApiV1Envelope)
def v1_storage_utilization(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_utilization_response(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/audit-analytics", response_model=ScanApiV1Envelope)
def v1_storage_audit_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_audit_analytics_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/unassigned", response_model=ScanApiV1Envelope)
def v1_storage_unassigned(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_unassigned_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/health", response_model=ScanApiV1Envelope)
def v1_storage_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_health_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/certification", response_model=ScanApiV1Envelope)
def v1_storage_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P79StorageCertificationRead = run_storage_intelligence_certification(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@storage_v1_router.get("/storage/analytics-dashboard", response_model=ScanApiV1Envelope)
def v1_storage_analytics_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_analytics_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
