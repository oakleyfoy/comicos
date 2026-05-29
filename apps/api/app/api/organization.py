from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status, Query, FastAPI
from sqlmodel import Session

from app.api.dependencies.organization_auth import require_org_permission
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.organization import (
    OrganizationArchiveRequest,
    OrganizationCreateRequest,
    OrganizationEventListResponse,
    OrganizationInviteRequest,
    OrganizationListResponse,
    OrganizationMembershipRoleListResponse,
    OrganizationRoleAssignmentRequest,
    OrganizationRoleListResponse,
    OrganizationMemberListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.authorization_service import assign_role, list_member_roles, list_organization_roles, remove_role
from app.services.organization_service import (
    accept_invitation,
    archive_organization,
    create_organization,
    get_organization,
    invite_member,
    list_organization_events,
    list_organization_members,
    list_organizations,
)

organization_v1_router = APIRouter(prefix="/api/v1", tags=["Organizations API v1 (P42)"])


def attach_organization_layer(app: FastAPI) -> None:
    app.include_router(organization_v1_router)


@organization_v1_router.post("/organizations", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_organization(
    payload: OrganizationCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_organization(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@organization_v1_router.get("/organizations", response_model=ScanApiV1Envelope)
def v1_list_organizations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: OrganizationListResponse = list_organizations(session, user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@organization_v1_router.get("/organizations/{organization_id}", response_model=ScanApiV1Envelope)
def v1_get_organization(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("organization:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_organization(session, user_id=int(current_user.id), organization_id=organization_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@organization_v1_router.post("/organizations/{organization_id}/invite", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_invite_member(
    organization_id: int,
    payload: OrganizationInviteRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("members:invite")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = invite_member(session, owner_user_id=int(current_user.id), organization_id=organization_id, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@organization_v1_router.post("/organizations/{organization_id}/archive", response_model=ScanApiV1Envelope)
def v1_archive_organization(
    organization_id: int,
    payload: OrganizationArchiveRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("organization:archive")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = archive_organization(session, owner_user_id=int(current_user.id), organization_id=organization_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@organization_v1_router.post("/organizations/invitations/{token}/accept", response_model=ScanApiV1Envelope)
def v1_accept_organization_invitation(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    body = accept_invitation(session, current_user=current_user, token=token)
    return wrap_object(body, owner_user_id=current_user.id, snapshot_id=body.id)


@organization_v1_router.get("/organizations/{organization_id}/members", response_model=ScanApiV1Envelope)
def v1_list_organization_members(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("members:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: OrganizationMemberListResponse = list_organization_members(
        session,
        user_id=int(current_user.id),
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@organization_v1_router.get("/organizations/{organization_id}/events", response_model=ScanApiV1Envelope)
def v1_list_organization_events(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("audit:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: OrganizationEventListResponse = list_organization_events(
        session,
        user_id=int(current_user.id),
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@organization_v1_router.get("/organizations/{organization_id}/roles", response_model=ScanApiV1Envelope)
def v1_list_organization_roles(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("members:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: OrganizationRoleListResponse = list_organization_roles(
        session,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@organization_v1_router.get("/organizations/{organization_id}/members/{member_id}/roles", response_model=ScanApiV1Envelope)
def v1_list_member_roles(
    organization_id: int,
    member_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("members:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: OrganizationMembershipRoleListResponse = list_member_roles(
        session,
        organization_id=organization_id,
        member_id=member_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@organization_v1_router.post("/organizations/{organization_id}/members/{member_id}/roles", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_assign_member_role(
    organization_id: int,
    member_id: int,
    payload: OrganizationRoleAssignmentRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("members:roles:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = assign_role(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        member_id=member_id,
        role_key=payload.role_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@organization_v1_router.delete("/organizations/{organization_id}/members/{member_id}/roles/{role_id}", response_model=ScanApiV1Envelope)
def v1_remove_member_role(
    organization_id: int,
    member_id: int,
    role_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_org_permission("members:roles:update")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = remove_role(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        member_id=member_id,
        role_id=role_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
