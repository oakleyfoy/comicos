from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MobileDeviceAccessLog, MobileDeviceSecurityEvent, MobileDeviceSecurityPolicy, MobileDeviceTrustState, MobileSession, User
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _register_device(client: TestClient, token: str, organization_id: int, *, device_identifier: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/devices",
        headers=auth_headers(token),
        json={
            "device_identifier": device_identifier,
            "device_name": device_identifier,
            "device_type": "tablet",
        },
    )
    assert response.status_code in {200, 201}, response.text
    return int(response.json()["data"]["id"])


def _user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).one()
    assert user.id is not None
    return int(user.id)


def test_device_trust_state_and_policy_workflow(client: TestClient, session: Session) -> None:
    owner_email = "mobile-security-owner@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="mobile-security-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="secure-device-1")

    trust_state = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states",
        headers=auth_headers(owner),
        json={"mobile_device_id": device_id, "trust_status": "trusted", "trust_reason": "approved"},
    )
    assert trust_state.status_code == 201, trust_state.text
    trust_state_id = trust_state.json()["data"]["id"]

    policy = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/policies",
        headers=auth_headers(owner),
        json={"policy_key": "require_trusted_device", "policy_status": "active", "policy_payload_json": {"scope": "mobile"}},
    )
    assert policy.status_code == 201, policy.text
    policy_id = policy.json()["data"]["id"]

    updated_policy = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-security/policies/{policy_id}",
        headers=auth_headers(owner),
        json={"policy_status": "inactive", "policy_payload_json": {"scope": "mobile", "note": "maintenance"}},
    )
    assert updated_policy.status_code == 200, updated_policy.text

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-security", headers=auth_headers(owner))
    trust_list = client.get(f"/api/v1/organizations/{organization_id}/mobile-security/trust-states?limit=20&offset=0", headers=auth_headers(owner))
    policy_list = client.get(f"/api/v1/organizations/{organization_id}/mobile-security/policies?limit=20&offset=0", headers=auth_headers(owner))
    assert dashboard.status_code == 200, dashboard.text
    assert trust_list.status_code == 200, trust_list.text
    assert policy_list.status_code == 200, policy_list.text
    assert dashboard.json()["data"]["summary"]["trust_states"] == {"trusted": 1, "untrusted": 0, "suspended": 0}
    assert [row["mobile_device_id"] for row in trust_list.json()["data"]["items"]] == [device_id]
    assert [row["policy_key"] for row in policy_list.json()["data"]["items"]] == ["require_trusted_device"]

    trust_rows = session.exec(
        select(MobileDeviceTrustState)
        .where(MobileDeviceTrustState.organization_id == organization_id)
        .order_by(MobileDeviceTrustState.created_at.asc(), MobileDeviceTrustState.id.asc())
    ).all()
    policy_rows = session.exec(
        select(MobileDeviceSecurityPolicy)
        .where(MobileDeviceSecurityPolicy.organization_id == organization_id)
        .order_by(MobileDeviceSecurityPolicy.created_at.asc(), MobileDeviceSecurityPolicy.id.asc())
    ).all()
    event_rows = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .order_by(MobileDeviceSecurityEvent.created_at.asc(), MobileDeviceSecurityEvent.id.asc())
    ).all()
    assert [row.id for row in trust_rows] == [trust_state_id]
    assert [row.id for row in policy_rows] == [policy_id]
    event_types = [row.event_type for row in event_rows]
    assert "device_trust_state_set" in event_types
    assert "device_security_policy_created" in event_types
    assert "device_security_policy_updated" in event_types


def test_device_access_validation_suspend_unsuspend_and_logs(client: TestClient, session: Session) -> None:
    owner_email = "mobile-security-access@example.com"
    owner = register_and_login(client, owner_email)
    organization_id = _create_organization(client, owner, slug="mobile-security-access-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="secure-device-2")
    owner_user_id = _user_id(session, owner_email)

    trust_state = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states",
        headers=auth_headers(owner),
        json={"mobile_device_id": device_id, "trust_status": "untrusted", "trust_reason": "pending review"},
    )
    assert trust_state.status_code == 201, trust_state.text
    trust_state_id = trust_state.json()["data"]["id"]

    trusted_policy = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/policies",
        headers=auth_headers(owner),
        json={"policy_key": "require_trusted_device", "policy_status": "active", "policy_payload_json": {}},
    )
    assert trusted_policy.status_code == 201, trusted_policy.text

    denied_session = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": device_id},
    )
    assert denied_session.status_code == 403, denied_session.text

    trusted_state = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states",
        headers=auth_headers(owner),
        json={"mobile_device_id": device_id, "trust_status": "trusted", "trust_reason": "review complete"},
    )
    assert trusted_state.status_code == 200, trusted_state.text

    created_session = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": device_id},
    )
    assert created_session.status_code == 201, created_session.text

    allowed_capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": device_id, "scan_type": "upc", "scan_value": "012345678905"},
    )
    assert allowed_capture.status_code == 201, allowed_capture.text

    suspended = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}",
        headers=auth_headers(owner),
        json={"trust_status": "suspended", "trust_reason": "lost device"},
    )
    assert suspended.status_code == 200, suspended.text

    denied_capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": device_id, "scan_type": "upc", "scan_value": "012345678905"},
    )
    assert denied_capture.status_code == 403, denied_capture.text

    unsuspended = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}",
        headers=auth_headers(owner),
        json={"trust_status": "trusted", "trust_reason": "device recovered"},
    )
    assert unsuspended.status_code == 200, unsuspended.text

    resumed_session = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": device_id},
    )
    assert resumed_session.status_code == 201, resumed_session.text

    resumed_capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": device_id, "scan_type": "upc", "scan_value": "012345678905"},
    )
    assert resumed_capture.status_code == 201, resumed_capture.text

    access_logs = client.get(
        f"/api/v1/organizations/{organization_id}/mobile-security/access-logs?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    events = client.get(
        f"/api/v1/organizations/{organization_id}/mobile-security/events?limit=100&offset=0",
        headers=auth_headers(owner),
    )
    assert access_logs.status_code == 200, access_logs.text
    assert events.status_code == 200, events.text
    assert [row["access_result"] for row in access_logs.json()["data"]["items"]] == [
        "denied",
        "allowed",
        "allowed",
        "denied",
        "allowed",
        "allowed",
    ]

    session_rows = session.exec(
        select(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .where(MobileSession.device_id == device_id)
        .order_by(MobileSession.started_at.asc(), MobileSession.id.asc())
    ).all()
    assert session_rows[0].session_status == "terminated"
    assert session_rows[-1].session_status == "active"

    log_rows = session.exec(
        select(MobileDeviceAccessLog)
        .where(MobileDeviceAccessLog.organization_id == organization_id)
        .order_by(MobileDeviceAccessLog.accessed_at.asc(), MobileDeviceAccessLog.id.asc())
    ).all()
    assert [row.access_result for row in log_rows] == ["denied", "allowed", "allowed", "denied", "allowed", "allowed"]

    event_rows = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .order_by(MobileDeviceSecurityEvent.created_at.asc(), MobileDeviceSecurityEvent.id.asc())
    ).all()
    event_types = [row.event_type for row in event_rows]
    assert "device_suspended" in event_types
    assert "device_unsuspended" in event_types
    assert "device_access_allowed" in event_types
    assert "device_access_denied" in event_types


def test_mobile_device_security_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "mobile-security-isolation-owner@example.com")
    outsider = register_and_login(client, "mobile-security-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="mobile-security-isolation-org")
    _create_organization(client, outsider, slug="mobile-security-outsider-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="secure-device-3")

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-security", headers=auth_headers(outsider))
    denied_trust_state = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/trust-states",
        headers=auth_headers(outsider),
        json={"mobile_device_id": device_id, "trust_status": "trusted", "trust_reason": "unauthorized"},
    )
    denied_policy = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-security/policies",
        headers=auth_headers(outsider),
        json={"policy_key": "require_trusted_device", "policy_status": "active", "policy_payload_json": {}},
    )
    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_trust_state.status_code == 403, denied_trust_state.text
    assert denied_policy.status_code == 403, denied_policy.text

    attempts = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .where(MobileDeviceSecurityEvent.event_type == "unauthorized_mobile_security_access_attempt")
        .order_by(MobileDeviceSecurityEvent.id.asc())
    ).all()
    assert len(attempts) == 3
