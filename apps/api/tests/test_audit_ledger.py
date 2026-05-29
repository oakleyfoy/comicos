from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OrganizationAuditAccessLog, OrganizationAuditLedger, OrganizationComplianceEvent
from app.schemas.organization_audit import LINEAGE_COMPLIANCE_PREFIX
from app.services.organization_service import remove_member
from app.services.audit_ledger_service import create_audit_access_log, create_audit_entry, create_compliance_event
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _invite_staff(client: TestClient, owner: str, organization_id: int, email: str) -> tuple[str, int]:
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": email},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["data"]["invitation_token"]
    staff = register_and_login(client, email)
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(staff))
    assert accepted.status_code == 200, accepted.text
    return staff, int(accepted.json()["data"]["user_id"])


def test_audit_creation_and_notification_ack_projection(client: TestClient) -> None:
    owner = register_and_login(client, "audit-owner@example.com")
    organization_id = _create_organization(client, owner, slug="audit-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "audit-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner)

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert assigned.status_code in {200, 201}, assigned.text

    notifications = client.get(
        f"/api/v1/organizations/{organization_id}/notifications",
        headers=auth_headers(staff),
    )
    assert notifications.status_code == 200, notifications.text
    notification_id = int(notifications.json()["data"]["items"][0]["id"])

    acknowledged = client.post(
        f"/api/v1/organizations/{organization_id}/notifications/{notification_id}/acknowledge",
        headers=auth_headers(staff),
    )
    assert acknowledged.status_code == 200, acknowledged.text

    audit = client.get(
        f"/api/v1/organizations/{organization_id}/audit?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    assert audit.status_code == 200, audit.text
    items = audit.json()["data"]["items"]
    actions = [row["audit_action"] for row in items]
    assert "inventory_assigned" in actions
    assert "notification_acknowledged" in actions


def test_org_isolation_compliance_visibility_and_access_logs(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "audit-isolation-owner@example.com")
    outsider = register_and_login(client, "audit-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="audit-isolation-org")
    other_org_id = _create_organization(client, outsider, slug="audit-isolation-other-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "audit-isolation-staff@example.com")
    owner_user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])

    denied = client.get(f"/api/v1/organizations/{organization_id}/audit", headers=auth_headers(staff))
    assert denied.status_code == 403, denied.text

    removed = remove_member(
        session,
        owner_user_id=owner_user_id,
        organization_id=organization_id,
        member_user_id=staff_user_id,
    )
    assert removed.user_id == staff_user_id

    compliance = client.get(
        f"/api/v1/organizations/{organization_id}/compliance-events?severity=critical",
        headers=auth_headers(owner),
    )
    assert compliance.status_code == 200, compliance.text
    compliance_items = compliance.json()["data"]["items"]
    assert any(row["compliance_event_type"] == "organization.member_removed" for row in compliance_items)

    access_logs = client.get(
        f"/api/v1/organizations/{organization_id}/audit/access-log?limit=100&offset=0",
        headers=auth_headers(owner),
    )
    assert access_logs.status_code == 200, access_logs.text
    log_items = access_logs.json()["data"]["items"]
    assert any(row["actor_user_id"] == staff_user_id and row["access_result"] == "DENIED" for row in log_items)

    cross_org = client.get(f"/api/v1/organizations/{other_org_id}/audit", headers=auth_headers(owner))
    assert cross_org.status_code == 403, cross_org.text


def test_deterministic_ordering_and_category_severity_filters(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "audit-filter-owner@example.com")
    organization_id = _create_organization(client, owner, slug="audit-filter-org")
    user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])

    base_time = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
    first = create_audit_entry(
        session,
        organization_id=organization_id,
        actor_user_id=user_id,
        audit_category="inventory",
        audit_action="inventory_checked",
        resource_type="inventory_copy",
        resource_id="100",
        audit_payload_json={"label": "first"},
    )
    first.created_at = base_time
    session.add(first)
    second = create_audit_entry(
        session,
        organization_id=organization_id,
        actor_user_id=user_id,
        audit_category="permissions",
        audit_action="permission_synced",
        resource_type="permission_assignment",
        resource_id="200",
        audit_payload_json={"label": "second"},
    )
    second.created_at = base_time
    session.add(second)
    elevated = create_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type="security.session_revoked",
        severity_level="elevated",
        event_payload_json={"label": "elevated"},
    )
    elevated.created_at = base_time
    session.add(elevated)
    session.commit()

    audit = client.get(
        f"/api/v1/organizations/{organization_id}/audit?category=permissions&actor={user_id}&resource_type=permission_assignment",
        headers=auth_headers(owner),
    )
    assert audit.status_code == 200, audit.text
    audit_items = audit.json()["data"]["items"]
    assert [row["audit_action"] for row in audit_items] == ["permission_synced"]

    full_audit = client.get(
        f"/api/v1/organizations/{organization_id}/audit?limit=10&offset=0",
        headers=auth_headers(owner),
    )
    assert full_audit.status_code == 200, full_audit.text
    ids = [row["id"] for row in full_audit.json()["data"]["items"][:2]]
    assert ids == sorted(ids, reverse=True)

    compliance = client.get(
        f"/api/v1/organizations/{organization_id}/compliance-events?severity=elevated",
        headers=auth_headers(owner),
    )
    assert compliance.status_code == 200, compliance.text
    assert all(row["severity_level"] == "elevated" for row in compliance.json()["data"]["items"])


def test_append_only_audit_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "audit-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="audit-lineage-org")
    staff, _ = _invite_staff(client, owner, organization_id, "audit-lineage-staff@example.com")
    owner_user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])

    create_audit_entry(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        audit_category="organization",
        audit_action="organization_viewed",
        resource_type="organization",
        resource_id=organization_id,
        audit_payload_json={"reason": "test"},
    )
    create_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type="security.session_revoked",
        severity_level="elevated",
        event_payload_json={"reason": "test"},
    )
    create_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type="organization.member_removed",
        severity_level="critical",
        event_payload_json={"reason": "test"},
    )
    create_audit_access_log(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        accessed_resource_type="audit_ledger",
        accessed_resource_id=organization_id,
        access_result="GRANTED",
    )
    session.commit()

    denied = client.get(f"/api/v1/organizations/{organization_id}/audit", headers=auth_headers(staff))
    assert denied.status_code == 403, denied.text

    lineage = session.exec(
        select(OrganizationComplianceEvent)
        .where(OrganizationComplianceEvent.organization_id == organization_id)
        .where(OrganizationComplianceEvent.compliance_event_type.like(f"{LINEAGE_COMPLIANCE_PREFIX}%"))
        .order_by(OrganizationComplianceEvent.id.asc())
    ).all()
    lineage_types = [row.compliance_event_type for row in lineage]
    assert "lineage.audit_entry_created" in lineage_types
    assert "lineage.compliance_event_created" in lineage_types
    assert "lineage.audit_access_logged" in lineage_types
    assert "lineage.unauthorized_audit_access_attempt" in lineage_types
    assert "lineage.elevated_security_event" in lineage_types
    assert "lineage.critical_org_action" in lineage_types

    assert session.exec(select(OrganizationAuditLedger).where(OrganizationAuditLedger.organization_id == organization_id)).all()
    assert session.exec(select(OrganizationAuditAccessLog).where(OrganizationAuditAccessLog.organization_id == organization_id)).all()
