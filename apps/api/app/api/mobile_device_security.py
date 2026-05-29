"""P44-07 `/api/v1/organizations/*/mobile-security` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Response, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.mobile_device_security import (
    MobileDeviceSecurityPolicyCreateRequest,
    MobileDeviceSecurityPolicyUpdateRequest,
    MobileDeviceTrustStateCreateRequest,
    MobileDeviceTrustStateUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.mobile_device_security_registry import TRUST_STATUS_SUSPENDED
from app.services.mobile_device_security_service import (
    build_mobile_device_security_dashboard,
    create_security_policy,
    list_device_access_logs,
    list_device_security_events,
    list_device_trust_states,
    list_security_policies,
    set_device_trust_state,
    suspend_mobile_device,
    unsuspend_mobile_device,
    update_security_policy,
)

mobile_device_security_v1_router = APIRouter(prefix="/api/v1", tags=["Mobile Device Security API v1 (P44-07)"])


def attach_mobile_device_security_layer(app: FastAPI) -> None:
    app.include_router(mobile_device_security_v1_router)


@mobile_device_security_v1_router.get("/organizations/{organization_id}/mobile-security", response_model=ScanApiV1Envelope)
def v1_get_mobile_device_security_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_mobile_device_security_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@mobile_device_security_v1_router.get("/organizations/{organization_id}/mobile-security/trust-states", response_model=ScanApiV1Envelope)
def v1_list_mobile_device_trust_states(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_device_trust_states(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_device_security_v1_router.get("/organizations/{organization_id}/mobile-security/policies", response_model=ScanApiV1Envelope)
def v1_list_mobile_device_security_policies(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_security_policies(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_device_security_v1_router.get("/organizations/{organization_id}/mobile-security/access-logs", response_model=ScanApiV1Envelope)
def v1_list_mobile_device_access_logs(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_device_access_logs(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_device_security_v1_router.get("/organizations/{organization_id}/mobile-security/events", response_model=ScanApiV1Envelope)
def v1_list_mobile_device_security_events(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_device_security_events(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_device_security_v1_router.post(
    "/organizations/{organization_id}/mobile-security/trust-states",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_mobile_device_trust_state(
    organization_id: int,
    payload: MobileDeviceTrustStateCreateRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = set_device_trust_state(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_device_security_v1_router.patch(
    "/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_mobile_device_trust_state(
    organization_id: int,
    trust_state_id: int,
    payload: MobileDeviceTrustStateUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if payload.trust_status == TRUST_STATUS_SUSPENDED:
        body = suspend_mobile_device(
            session,
            organization_id=organization_id,
            actor_user_id=int(current_user.id),
            trust_state_id=trust_state_id,
            payload=payload,
        )
    else:
        body = unsuspend_mobile_device(
            session,
            organization_id=organization_id,
            actor_user_id=int(current_user.id),
            trust_state_id=trust_state_id,
            payload=payload,
        )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_device_security_v1_router.post(
    "/organizations/{organization_id}/mobile-security/policies",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_mobile_device_security_policy(
    organization_id: int,
    payload: MobileDeviceSecurityPolicyCreateRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_security_policy(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_device_security_v1_router.patch(
    "/organizations/{organization_id}/mobile-security/policies/{policy_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_mobile_device_security_policy(
    organization_id: int,
    policy_id: int,
    payload: MobileDeviceSecurityPolicyUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_security_policy(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        policy_id=policy_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
