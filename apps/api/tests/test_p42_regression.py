from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    DealerStorefrontEvent,
    OrganizationActivityEvent,
    OrganizationAuditLedger,
    OrganizationComplianceEvent,
    OrganizationDealerDashboardEvent,
    OrganizationDealerDashboardSnapshot,
    OrganizationDealerOperationalMetric,
)
from app.schemas.organization_activity import LINEAGE_ACTIVITY_PREFIX
from app.schemas.organization_audit import LINEAGE_COMPLIANCE_PREFIX
from app.schemas.organization_dealer_dashboard import LINEAGE_DASHBOARD_PREFIX
from app.services.activity_feed_service import create_activity_event
from app.services.audit_ledger_service import create_audit_entry, create_compliance_event
from app.services.dealer_dashboard_service import (
    _require_dashboard_access,
    generate_dashboard_snapshot,
    generate_operational_metrics,
)
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


def _bootstrap_public_storefront(client: TestClient, owner: str, organization_id: int, inventory_item_id: int) -> str:
    profile = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={
            "public_slug": "p42-regression-dealer",
            "display_name": "P42 Regression Dealer",
            "tagline": "Regression coverage",
            "profile_status": "ACTIVE",
        },
    )
    assert profile.status_code == 200, profile.text

    settings = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(owner),
        json={
            "storefront_visibility": "PUBLIC",
            "public_inventory_enabled": True,
            "featured_inventory_limit": 1,
            "featured_inventory_sort": "manually_selected",
            "featured_manual_inventory_ids": [inventory_item_id],
        },
    )
    assert settings.status_code == 200, settings.text
    return "p42-regression-dealer"


def test_p42_regression_smoke_and_deterministic_rendering(client: TestClient) -> None:
    owner = register_and_login(client, "p42-regression-owner@example.com")
    staff = register_and_login(client, "p42-regression-staff@example.com")
    organization_id = _create_organization(client, owner, slug="p42-regression-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "p42-regression-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner)
    public_slug = _bootstrap_public_storefront(client, owner, organization_id, inventory_item_id)

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert assigned.status_code in {200, 201}, assigned.text

    review = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_id,
            "review_type": "grading",
            "assigned_user_id": staff_user_id,
            "queue_name": "grading_review",
        },
    )
    assert review.status_code == 201, review.text
    review_id = int(review.json()["data"]["id"])

    approved = client.post(
        f"/api/v1/organizations/{organization_id}/reviews/{review_id}/approve",
        headers=auth_headers(owner),
        json={"decision_notes": "Regression approval"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["review_status"] == "APPROVED"

    feed = client.get(f"/api/v1/organizations/{organization_id}/activity?limit=50&offset=0", headers=auth_headers(owner))
    assert feed.status_code == 200, feed.text
    feed_items = feed.json()["data"]["items"]
    assert feed_items
    assert [row["id"] for row in feed_items] == sorted((row["id"] for row in feed_items), reverse=True)

    notifications = client.get(
        f"/api/v1/organizations/{organization_id}/notifications",
        headers=auth_headers(staff),
    )
    assert notifications.status_code == 200, notifications.text
    notification_items = notifications.json()["data"]["items"]
    assert notification_items
    notification_id = int(notification_items[0]["id"])
    assert notification_items[0]["notification_status"] == "UNREAD"

    read = client.post(
        f"/api/v1/organizations/{organization_id}/notifications/{notification_id}/read",
        headers=auth_headers(staff),
    )
    assert read.status_code == 200, read.text

    acknowledged = client.post(
        f"/api/v1/organizations/{organization_id}/notifications/{notification_id}/acknowledge",
        headers=auth_headers(staff),
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["data"]["notification_status"] == "ACKNOWLEDGED"

    audit = client.get(f"/api/v1/organizations/{organization_id}/audit?limit=100&offset=0", headers=auth_headers(owner))
    assert audit.status_code == 200, audit.text
    audit_items = audit.json()["data"]["items"]
    assert audit_items
    assert [row["id"] for row in audit_items] == sorted((row["id"] for row in audit_items), reverse=True)
    audit_actions = [row["audit_action"] for row in audit_items]
    assert "inventory_assigned" in audit_actions
    assert "notification_acknowledged" in audit_actions

    storefront = client.get(f"/api/v1/storefronts/{public_slug}/inventory?limit=10&offset=0")
    assert storefront.status_code == 200, storefront.text
    storefront_item = storefront.json()["data"]["items"][0]
    assert "acquisition_cost" not in storefront_item
    assert "organization_review_status" not in storefront_item

    dashboard = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard?refresh=true",
        headers=auth_headers(owner),
    )
    assert dashboard.status_code == 200, dashboard.text
    dashboard_data = dashboard.json()["data"]
    assert dashboard_data["organization_id"] == organization_id
    assert [row["section_key"] for row in dashboard_data["sections"]] == [
        "inventory",
        "reviews",
        "activity",
        "storefront",
        "notifications",
        "security",
    ]
    inventory_section = next(row for row in dashboard_data["sections"] if row["section_key"] == "inventory")
    assert inventory_section["metrics"]["active_inventory_count"] >= 1
    assert inventory_section["metrics"]["active_staff_count"] >= 2

    metrics = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard/metrics?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    assert metrics.status_code == 200, metrics.text
    metric_items = metrics.json()["data"]["items"]
    assert [row["id"] for row in metric_items] == sorted((row["id"] for row in metric_items), reverse=True)
    assert "assigned_inventory_count" in {row["metric_key"] for row in metric_items}

    snapshots = client.get(
        f"/api/v1/organizations/{organization_id}/dashboard/snapshots?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert snapshots.status_code == 200, snapshots.text
    snapshot_items = snapshots.json()["data"]["items"]
    assert snapshot_items
    assert [row["id"] for row in snapshot_items] == sorted((row["id"] for row in snapshot_items), reverse=True)


def test_p42_tenant_isolation_and_negative_paths(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "p42-tenant-owner@example.com")
    outsider = register_and_login(client, "p42-tenant-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="p42-tenant-org")
    other_org_id = _create_organization(client, outsider, slug="p42-tenant-other")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "p42-tenant-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner)
    outsider_user_id = int(client.get("/auth/me", headers=auth_headers(outsider)).json()["id"])

    assert client.get(f"/api/v1/organizations/{organization_id}/inventory", headers=auth_headers(outsider)).status_code == 404
    assert client.get(f"/api/v1/organizations/{organization_id}/reviews", headers=auth_headers(outsider)).status_code == 403
    assert client.get(f"/api/v1/organizations/{organization_id}/activity", headers=auth_headers(outsider)).status_code == 403
    assert client.get(f"/api/v1/organizations/{organization_id}/audit", headers=auth_headers(staff)).status_code == 403
    assert client.get(f"/api/v1/organizations/{organization_id}/dashboard", headers=auth_headers(staff)).status_code == 403
    assert client.get(f"/api/v1/organizations/{other_org_id}/dashboard", headers=auth_headers(owner)).status_code == 403

    hidden_slug = _bootstrap_public_storefront(client, owner, organization_id, inventory_item_id)
    private = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(owner),
        json={"storefront_visibility": "PRIVATE", "public_inventory_enabled": True},
    )
    assert private.status_code == 200, private.text
    assert client.get(f"/api/v1/storefronts/{hidden_slug}/inventory").status_code == 404

    denied_member = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(staff),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert denied_member.status_code == 403, denied_member.text

    denied_storefront = client.post(
        f"/api/v1/organizations/{organization_id}/storefront/settings",
        headers=auth_headers(outsider),
        json={"storefront_visibility": "PUBLIC", "public_inventory_enabled": True},
    )
    assert denied_storefront.status_code == 403, denied_storefront.text

    denied_inventory = client.get(f"/api/v1/organizations/{other_org_id}/inventory", headers=auth_headers(owner))
    assert denied_inventory.status_code == 404, denied_inventory.text

    with pytest.raises(HTTPException):
        _require_dashboard_access(
            session,
            organization_id=organization_id,
            actor_user_id=outsider_user_id,
            record_access=False,
        )


def test_p42_replay_safe_service_lineage_and_append_only_history(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "p42-replay-owner@example.com")
    organization_id = _create_organization(client, owner, slug="p42-replay-org")
    inventory_item_id = _inventory_copy_id(client, owner)
    owner_user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])

    create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        activity_type="inventory.replay_projection",
        activity_payload_json={"inventory_item_id": inventory_item_id},
        visibility_scope="ORG",
        category="inventory",
    )
    create_audit_entry(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        audit_category="inventory",
        audit_action="inventory_replayed",
        resource_type="inventory_copy",
        resource_id=inventory_item_id,
        audit_payload_json={"replay": True},
    )
    create_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type="security.replay_validation",
        severity_level="critical",
        event_payload_json={"inventory_item_id": inventory_item_id},
    )
    generate_operational_metrics(session, organization_id=organization_id)
    snapshot_one = generate_dashboard_snapshot(session, organization_id=organization_id)
    snapshot_two = generate_dashboard_snapshot(session, organization_id=organization_id)
    fixed_time = datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)
    snapshot_one.generated_at = fixed_time
    snapshot_two.generated_at = fixed_time
    session.add(snapshot_one)
    session.add(snapshot_two)
    session.commit()

    activity_rows = session.exec(
        select(OrganizationActivityEvent)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .order_by(OrganizationActivityEvent.id.asc())
    ).all()
    assert activity_rows[-2].activity_type == "inventory.replay_projection"
    assert activity_rows[-1].activity_type == f"{LINEAGE_ACTIVITY_PREFIX}activity_generated"

    audit_rows = session.exec(
        select(OrganizationAuditLedger)
        .where(OrganizationAuditLedger.organization_id == organization_id)
        .order_by(OrganizationAuditLedger.id.asc())
    ).all()
    assert audit_rows[-1].audit_action == "inventory_replayed"

    compliance_rows = session.exec(
        select(OrganizationComplianceEvent)
        .where(OrganizationComplianceEvent.organization_id == organization_id)
        .order_by(OrganizationComplianceEvent.id.asc())
    ).all()
    compliance_types = [row.compliance_event_type for row in compliance_rows]
    assert "security.replay_validation" in compliance_types
    assert f"{LINEAGE_COMPLIANCE_PREFIX}compliance_event_created" in compliance_types
    assert f"{LINEAGE_COMPLIANCE_PREFIX}critical_org_action" in compliance_types

    dashboard_events = session.exec(
        select(OrganizationDealerDashboardEvent)
        .where(OrganizationDealerDashboardEvent.organization_id == organization_id)
        .order_by(OrganizationDealerDashboardEvent.id.asc())
    ).all()
    dashboard_types = [row.event_type for row in dashboard_events]
    assert f"{LINEAGE_DASHBOARD_PREFIX}dashboard_metric_generated" in dashboard_types
    assert f"{LINEAGE_DASHBOARD_PREFIX}dashboard_snapshot_generated" in dashboard_types

    snapshots = session.exec(
        select(OrganizationDealerDashboardSnapshot)
        .where(OrganizationDealerDashboardSnapshot.organization_id == organization_id)
        .order_by(OrganizationDealerDashboardSnapshot.generated_at.desc(), OrganizationDealerDashboardSnapshot.id.desc())
    ).all()
    assert snapshots[0].id == snapshot_two.id
    assert snapshots[1].id == snapshot_one.id

    metrics = session.exec(
        select(OrganizationDealerOperationalMetric)
        .where(OrganizationDealerOperationalMetric.organization_id == organization_id)
        .order_by(OrganizationDealerOperationalMetric.generated_at.desc(), OrganizationDealerOperationalMetric.id.desc())
    ).all()
    assert metrics
    assert [row.id for row in metrics] == sorted((row.id for row in metrics), reverse=True)

    assert session.exec(select(DealerStorefrontEvent).where(DealerStorefrontEvent.organization_id == organization_id)).all() == []

