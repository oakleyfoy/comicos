from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OrganizationPermissionAudit
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, display_name: str, slug: str) -> dict:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": display_name, "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _invite_and_accept(client: TestClient, owner_token: str, member_token: str, *, organization_id: int, email: str) -> dict:
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner_token),
        json={"email": email},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["data"]["invitation_token"]
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(member_token))
    assert accepted.status_code == 200, accepted.text
    return accepted.json()["data"]


def _member_id_by_email(client: TestClient, token: str, organization_id: int, email: str) -> int:
    members = client.get(f"/api/v1/organizations/{organization_id}/members", headers=auth_headers(token))
    assert members.status_code == 200, members.text
    row = next(item for item in members.json()["data"]["items"] if item["user_email"] == email)
    return int(row["id"])


def _member_roles(client: TestClient, token: str, organization_id: int, member_id: int) -> list[dict]:
    response = client.get(
        f"/api/v1/organizations/{organization_id}/members/{member_id}/roles",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def _audit_rows(session: Session, organization_id: int) -> list[OrganizationPermissionAudit]:
    return session.exec(
        select(OrganizationPermissionAudit)
        .where(OrganizationPermissionAudit.organization_id == organization_id)
        .order_by(OrganizationPermissionAudit.created_at.asc(), OrganizationPermissionAudit.id.asc())
    ).all()


def test_owner_role_seed_and_default_viewer_role_assignment(client: TestClient) -> None:
    owner = register_and_login(client, "auth-owner@example.com")
    viewer = register_and_login(client, "auth-viewer@example.com")
    organization = _create_organization(client, owner, display_name="Auth Org", slug="auth-org")
    organization_id = int(organization["id"])

    owner_member_id = _member_id_by_email(client, owner, organization_id, "auth-owner@example.com")
    owner_roles = _member_roles(client, owner, organization_id, owner_member_id)
    assert [row["role_key"] for row in owner_roles] == ["owner"]

    accepted_member = _invite_and_accept(
        client,
        owner,
        viewer,
        organization_id=organization_id,
        email="auth-viewer@example.com",
    )
    assert accepted_member["role_keys"] == ["viewer"]
    viewer_member_id = int(accepted_member["id"])
    viewer_roles = _member_roles(client, owner, organization_id, viewer_member_id)
    assert [row["role_key"] for row in viewer_roles] == ["viewer"]


def test_tenant_isolation_and_deny_by_default_generate_permission_audit(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "tenant-owner@example.com")
    peer_owner = register_and_login(client, "tenant-peer-owner@example.com")
    outsider = register_and_login(client, "tenant-outsider@example.com")
    member = register_and_login(client, "tenant-member@example.com")

    first_org = _create_organization(client, owner, display_name="Tenant One", slug="tenant-one")
    second_org = _create_organization(client, peer_owner, display_name="Tenant Two", slug="tenant-two")
    first_org_id = int(first_org["id"])
    second_org_id = int(second_org["id"])

    _invite_and_accept(client, owner, member, organization_id=first_org_id, email="tenant-member@example.com")

    cross_org = client.get(f"/api/v1/organizations/{second_org_id}/roles", headers=auth_headers(member))
    assert cross_org.status_code == 403, cross_org.text

    denied_invite = client.post(
        f"/api/v1/organizations/{first_org_id}/invite",
        headers=auth_headers(member),
        json={"email": "blocked@example.com"},
    )
    assert denied_invite.status_code == 403, denied_invite.text

    outsider_read = client.get(f"/api/v1/organizations/{first_org_id}", headers=auth_headers(outsider))
    assert outsider_read.status_code == 403, outsider_read.text

    audit_rows = _audit_rows(session, first_org_id)
    assert any(row.permission_result == "DENIED" and row.action_key == "members:invite" for row in audit_rows)
    second_org_audits = _audit_rows(session, second_org_id)
    assert any(row.permission_result == "DENIED" and row.action_key == "members:view" for row in second_org_audits)


def test_owner_can_assign_and_remove_roles_with_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "role-owner@example.com")
    member = register_and_login(client, "role-member@example.com")
    organization = _create_organization(client, owner, display_name="Role Org", slug="role-org")
    organization_id = int(organization["id"])

    accepted_member = _invite_and_accept(client, owner, member, organization_id=organization_id, email="role-member@example.com")
    member_id = int(accepted_member["id"])

    manager = client.post(
        f"/api/v1/organizations/{organization_id}/members/{member_id}/roles",
        headers=auth_headers(owner),
        json={"role_key": "manager"},
    )
    staff = client.post(
        f"/api/v1/organizations/{organization_id}/members/{member_id}/roles",
        headers=auth_headers(owner),
        json={"role_key": "staff"},
    )
    assert manager.status_code == 201, manager.text
    assert staff.status_code == 201, staff.text

    roles = _member_roles(client, owner, organization_id, member_id)
    assert [row["role_key"] for row in roles] == ["manager", "staff", "viewer"]

    removed = client.delete(
        f"/api/v1/organizations/{organization_id}/members/{member_id}/roles/{manager.json()['data']['organization_role_id']}",
        headers=auth_headers(owner),
    )
    assert removed.status_code == 200, removed.text
    roles_after_remove = _member_roles(client, owner, organization_id, member_id)
    assert [row["role_key"] for row in roles_after_remove] == ["staff", "viewer"]

    audit_rows = _audit_rows(session, organization_id)
    assert any(row.permission_result == "ASSIGNED" and row.action_key == "role:assign" for row in audit_rows)
    assert any(row.permission_result == "REMOVED" and row.action_key == "role:remove" for row in audit_rows)


def test_owner_protection_and_no_self_escalation_paths(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "protect-owner@example.com")
    admin = register_and_login(client, "protect-admin@example.com")
    peer = register_and_login(client, "protect-peer@example.com")
    organization = _create_organization(client, owner, display_name="Protected Org", slug="protected-org")
    organization_id = int(organization["id"])

    admin_member = _invite_and_accept(client, owner, admin, organization_id=organization_id, email="protect-admin@example.com")
    peer_member = _invite_and_accept(client, owner, peer, organization_id=organization_id, email="protect-peer@example.com")
    admin_member_id = int(admin_member["id"])
    peer_member_id = int(peer_member["id"])

    promote_admin = client.post(
        f"/api/v1/organizations/{organization_id}/members/{admin_member_id}/roles",
        headers=auth_headers(owner),
        json={"role_key": "admin"},
    )
    assert promote_admin.status_code == 201, promote_admin.text

    self_promote = client.post(
        f"/api/v1/organizations/{organization_id}/members/{admin_member_id}/roles",
        headers=auth_headers(admin),
        json={"role_key": "manager"},
    )
    assert self_promote.status_code == 403, self_promote.text

    escalate_peer = client.post(
        f"/api/v1/organizations/{organization_id}/members/{peer_member_id}/roles",
        headers=auth_headers(admin),
        json={"role_key": "admin"},
    )
    assert escalate_peer.status_code == 403, escalate_peer.text

    owner_member_id = _member_id_by_email(client, owner, organization_id, "protect-owner@example.com")
    owner_roles = _member_roles(client, owner, organization_id, owner_member_id)
    owner_role_id = int(owner_roles[0]["organization_role_id"])
    remove_owner_role = client.delete(
        f"/api/v1/organizations/{organization_id}/members/{owner_member_id}/roles/{owner_role_id}",
        headers=auth_headers(owner),
    )
    assert remove_owner_role.status_code == 403, remove_owner_role.text

    audit_rows = _audit_rows(session, organization_id)
    denied_reasons = [row.evaluation_context_json.get("reason") for row in audit_rows if row.permission_result == "DENIED"]
    assert "self_escalation_denied" in denied_reasons or "self_role_mutation_denied" in denied_reasons
    assert "owner_role_protected" in denied_reasons
