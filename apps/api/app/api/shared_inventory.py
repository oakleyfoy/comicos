from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.dependencies.organization_auth import require_org_permission
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.organization_inventory import (
    OrganizationInventoryAssignRequest,
    OrganizationInventoryCompleteRequest,
    OrganizationInventoryQueueMoveRequest,
    OrganizationInventoryUnassignRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.shared_inventory_service import (
    assign_inventory_item,
    complete_assignment,
    list_org_inventory_assignments,
    list_org_inventory_queues,
    list_org_inventory_workflow_events,
    move_inventory_queue,
    unassign_inventory_item,
)

shared_inventory_v1_router = APIRouter(prefix="/api/v1", tags=["Shared Inventory API v1 (P42-04)"])


def attach_shared_inventory_layer(app: FastAPI) -> None:
    app.include_router(shared_inventory_v1_router)


@shared_inventory_v1_router.get(
    "/organizations/{organization_id}/inventory/assignments",
    response_model=ScanApiV1Envelope,
)
def v1_list_org_inventory_assignments(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    assignment_status: str | None = Query(default=None),
    _: object = Depends(require_org_permission("inventory:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_org_inventory_assignments(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        assignment_status=assignment_status,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@shared_inventory_v1_router.get(
    "/organizations/{organization_id}/inventory/queues",
    response_model=ScanApiV1Envelope,
)
def v1_list_org_inventory_queues(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    queue_name: str | None = Query(default=None),
    _: object = Depends(require_org_permission("inventory:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_org_inventory_queues(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        queue_name=queue_name,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@shared_inventory_v1_router.get(
    "/organizations/{organization_id}/inventory/workflow-events",
    response_model=ScanApiV1Envelope,
)
def v1_list_org_inventory_workflow_events(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("audit:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_org_inventory_workflow_events(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@shared_inventory_v1_router.post(
    "/organizations/{organization_id}/inventory/assign",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_assign_org_inventory_item(
    organization_id: int,
    payload: OrganizationInventoryAssignRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("inventory:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = assign_inventory_item(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        inventory_item_id=payload.inventory_item_id,
        assigned_user_id=payload.assigned_user_id,
        assignment_notes=payload.assignment_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shared_inventory_v1_router.post(
    "/organizations/{organization_id}/inventory/unassign",
    response_model=ScanApiV1Envelope,
)
def v1_unassign_org_inventory_item(
    organization_id: int,
    payload: OrganizationInventoryUnassignRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("inventory:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = unassign_inventory_item(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        inventory_item_id=payload.inventory_item_id,
        assignment_notes=payload.assignment_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shared_inventory_v1_router.post(
    "/organizations/{organization_id}/inventory/complete",
    response_model=ScanApiV1Envelope,
)
def v1_complete_org_inventory_assignment(
    organization_id: int,
    payload: OrganizationInventoryCompleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("inventory:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_assignment(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        inventory_item_id=payload.inventory_item_id,
        assignment_notes=payload.assignment_notes,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shared_inventory_v1_router.post(
    "/organizations/{organization_id}/inventory/queues/move",
    response_model=ScanApiV1Envelope,
)
def v1_move_org_inventory_queue(
    organization_id: int,
    payload: OrganizationInventoryQueueMoveRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("inventory:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = move_inventory_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        inventory_item_id=payload.inventory_item_id,
        queue_name=payload.queue_name,
        queue_position=payload.queue_position,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
