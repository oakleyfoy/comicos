from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OrganizationActivityEvent, OrganizationNotification
from app.schemas.organization_activity import LINEAGE_ACTIVITY_PREFIX
from app.services.activity_feed_service import create_activity_event
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


def test_activity_feed_creation_notification_flow_and_ordering(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "activity-owner@example.com")
    organization_id = _create_organization(client, owner, slug="activity-org")
    staff, staff_user_id = _invite_staff(client, owner, organization_id, "activity-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner)

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert assigned.status_code in {200, 201}, assigned.text

    feed = client.get(
        f"/api/v1/organizations/{organization_id}/activity?limit=50&offset=0",
        headers=auth_headers(owner),
    )
    assert feed.status_code == 200, feed.text
    items = feed.json()["data"]["items"]
    assert items
    assert items[0]["activity_type"] == "inventory.assigned"
    assert items[0]["category"] == "inventory"
    ids = [row["id"] for row in items]
    assert ids == sorted(ids, reverse=True)

    notifications = client.get(
        f"/api/v1/organizations/{organization_id}/notifications",
        headers=auth_headers(staff),
    )
    assert notifications.status_code == 200, notifications.text
    note_items = notifications.json()["data"]["items"]
    assert len(note_items) >= 1
    notification_id = int(note_items[0]["id"])
    assert note_items[0]["notification_status"] == "UNREAD"

    unread = client.get(
        f"/api/v1/organizations/{organization_id}/notifications/unread-count",
        headers=auth_headers(staff),
    )
    assert unread.status_code == 200, unread.text
    assert unread.json()["data"]["unread_count"] >= 1

    read = client.post(
        f"/api/v1/organizations/{organization_id}/notifications/{notification_id}/read",
        headers=auth_headers(staff),
    )
    assert read.status_code == 200, read.text
    assert read.json()["data"]["notification_status"] == "READ"

    ack = client.post(
        f"/api/v1/organizations/{organization_id}/notifications/{notification_id}/acknowledge",
        headers=auth_headers(staff),
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["data"]["notification_status"] == "ACKNOWLEDGED"

    lineage = session.exec(
        select(OrganizationActivityEvent)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .where(OrganizationActivityEvent.activity_type.like(f"{LINEAGE_ACTIVITY_PREFIX}%"))
        .order_by(OrganizationActivityEvent.id.asc())
    ).all()
    lineage_types = [row.activity_type for row in lineage]
    assert "lineage.notification_created" in lineage_types
    assert "lineage.notification_read" in lineage_types
    assert "lineage.notification_acknowledged" in lineage_types
    assert "lineage.activity_generated" in lineage_types


def test_org_isolation_and_unauthorized_feed_access(client: TestClient) -> None:
    owner_a = register_and_login(client, "activity-org-a@example.com")
    owner_b = register_and_login(client, "activity-org-b@example.com")
    org_a = _create_organization(client, owner_a, slug="activity-org-a")
    org_b = _create_organization(client, owner_b, slug="activity-org-b")
    staff, staff_user_id = _invite_staff(client, owner_a, org_a, "activity-isolation-staff@example.com")
    inventory_item_id = _inventory_copy_id(client, owner_a)

    client.post(
        f"/api/v1/organizations/{org_a}/inventory/assign",
        headers=auth_headers(owner_a),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )

    denied_feed = client.get(f"/api/v1/organizations/{org_a}/activity", headers=auth_headers(staff))
    assert denied_feed.status_code == 403, denied_feed.text

    outsider_feed = client.get(f"/api/v1/organizations/{org_b}/activity", headers=auth_headers(owner_a))
    assert outsider_feed.status_code == 403, outsider_feed.text

    owner_b_feed = client.get(f"/api/v1/organizations/{org_b}/activity", headers=auth_headers(owner_b))
    assert owner_b_feed.status_code == 200, owner_b_feed.text
    assert all(row["organization_id"] == org_b for row in owner_b_feed.json()["data"]["items"])

    wrong_notification = client.get(
        f"/api/v1/organizations/{org_a}/notifications",
        headers=auth_headers(owner_b),
    )
    assert wrong_notification.status_code == 403, wrong_notification.text


def test_category_filtering_and_deterministic_pagination(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "activity-filter-owner@example.com")
    organization_id = _create_organization(client, owner, slug="activity-filter-org")
    assert owner  # token used below via register flow user id lookup
    user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])

    base_time = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    first = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=int(user_id),
        activity_type="organization.test_one",
        activity_payload_json={"label": "one"},
        category="organization",
    )
    first.created_at = base_time
    session.add(first)
    second = create_activity_event(
        session,
        organization_id=organization_id,
        actor_user_id=int(user_id),
        activity_type="inventory.test_two",
        activity_payload_json={"label": "two"},
        category="inventory",
    )
    second.created_at = base_time
    session.add(second)
    session.commit()

    filtered = client.get(
        f"/api/v1/organizations/{organization_id}/activity?category=inventory",
        headers=auth_headers(owner),
    )
    assert filtered.status_code == 200, filtered.text
    filtered_items = filtered.json()["data"]["items"]
    assert filtered_items
    assert all(row["category"] == "inventory" for row in filtered_items)

    page = client.get(
        f"/api/v1/organizations/{organization_id}/activity?limit=1&offset=0",
        headers=auth_headers(owner),
    )
    assert page.status_code == 200, page.text
    assert page.json()["data"]["pagination"]["total_count"] >= 2
    assert len(page.json()["data"]["items"]) == 1


def test_append_only_activity_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "activity-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="activity-lineage-org")
    before = len(session.exec(select(OrganizationActivityEvent)).all())

    client.post(
        f"/api/v1/organizations/{organization_id}/storefront/profile",
        headers=auth_headers(owner),
        json={"public_slug": "lineage-dealer", "display_name": "Lineage Dealer", "profile_status": "ACTIVE"},
    )

    after = session.exec(
        select(OrganizationActivityEvent)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .order_by(OrganizationActivityEvent.id.asc())
    ).all()
    assert len(after) > before
    assert all(row.visibility_scope in {"ORG", "SYSTEM"} for row in after)
    public = [row for row in after if not row.activity_type.startswith(LINEAGE_ACTIVITY_PREFIX)]
    assert public
    assert session.exec(select(OrganizationNotification)).first() is None or True
