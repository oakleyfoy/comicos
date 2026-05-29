import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OrganizationInventoryWorkflowEvent
from app.services.organization_inventory_access import validate_shared_inventory_access
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


def test_shared_inventory_visibility_and_assignment_flow(client: TestClient) -> None:
    owner = register_and_login(client, "shared-inv-owner@example.com")
    staff = register_and_login(client, "shared-inv-staff@example.com")
    organization_id = _create_organization(client, owner, slug="shared-inv-org")
    inventory_item_id = _inventory_copy_id(client, owner)

    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "shared-inv-staff@example.com"},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["data"]["invitation_token"]
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(staff))
    assert accepted.status_code == 200, accepted.text
    staff_user_id = int(accepted.json()["data"]["user_id"])

    shared = client.get(
        f"/inventory?organization_id={organization_id}&page=1&page_size=10",
        headers=auth_headers(staff),
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["total"] == 1
    assert shared.json()["items"][0]["inventory_copy_id"] == inventory_item_id

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["data"]["assignment_status"] == "ACTIVE"

    assignments = client.get(
        f"/api/v1/organizations/{organization_id}/inventory/assignments",
        headers=auth_headers(staff),
    )
    assert assignments.status_code == 200, assignments.text
    assert len(assignments.json()["data"]["items"]) == 1

    hydrated = client.get(
        f"/inventory?organization_id={organization_id}&page=1&page_size=10",
        headers=auth_headers(staff),
    )
    row = hydrated.json()["items"][0]
    assert row["organization_assignment_id"] == assigned.json()["data"]["id"]
    assert row["organization_assigned_user_id"] == staff_user_id
    assert row["organization_queue_name"] == "intake"


def test_queue_transitions_are_detinistic(client: TestClient) -> None:
    owner = register_and_login(client, "shared-queue-owner@example.com")
    organization_id = _create_organization(client, owner, slug="shared-queue-org")
    inventory_item_id = _inventory_copy_id(client, owner)

    first = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/queues/move",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "queue_name": "grading_review"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["queue_name"] == "grading_review"
    assert first.json()["data"]["queue_position"] == 1

    second = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/queues/move",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "queue_name": "scan_review", "queue_position": 1},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["queue_name"] == "scan_review"
    assert second.json()["data"]["queue_position"] == 1

    queues = client.get(
        f"/api/v1/organizations/{organization_id}/inventory/queues",
        headers=auth_headers(owner),
    )
    assert queues.status_code == 200, queues.text
    names = [row["queue_name"] for row in queues.json()["data"]["items"]]
    positions = [row["queue_position"] for row in queues.json()["data"]["items"]]
    assert names == ["scan_review"]
    assert positions == [1]


def test_org_isolation_and_unauthorized_access_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "shared-isolation-owner@example.com")
    outsider = register_and_login(client, "shared-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="shared-isolation-org")

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/inventory/assignments",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    outsider_user = client.get("/auth/me", headers=auth_headers(outsider))
    outsider_user_id = int(outsider_user.json()["id"])
    events_before = len(session.exec(select(OrganizationInventoryWorkflowEvent)).all())
    with pytest.raises(HTTPException) as exc:
        validate_shared_inventory_access(
            session,
            organization_id=organization_id,
            actor_user_id=outsider_user_id,
            action_key="inventory:view",
        )
    assert exc.value.status_code == 403
    session.commit()
    events_after = session.exec(select(OrganizationInventoryWorkflowEvent)).all()
    assert len(events_after) == events_before + 1
    assert events_after[-1].workflow_event_type == "unauthorized_inventory_access_attempt"


def test_assignment_completion_and_append_only_events(client: TestClient) -> None:
    owner = register_and_login(client, "shared-complete-owner@example.com")
    staff = register_and_login(client, "shared-complete-staff@example.com")
    organization_id = _create_organization(client, owner, slug="shared-complete-org")
    inventory_item_id = _inventory_copy_id(client, owner)

    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "shared-complete-staff@example.com"},
    )
    token = invite.json()["data"]["invitation_token"]
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(staff))
    staff_user_id = int(accepted.json()["data"]["user_id"])

    client.post(
        f"/api/v1/organizations/{organization_id}/inventory/assign",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "assigned_user_id": staff_user_id},
    )
    completed = client.post(
        f"/api/v1/organizations/{organization_id}/inventory/complete",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["assignment_status"] == "COMPLETED"
    assert completed.json()["data"]["completed_at"] is not None

    events = client.get(
        f"/api/v1/organizations/{organization_id}/inventory/workflow-events",
        headers=auth_headers(owner),
    )
    assert events.status_code == 200, events.text
    event_types = [row["workflow_event_type"] for row in events.json()["data"]["items"]]
    assert "assignment_completed" in event_types
    assert "inventory_assigned" in event_types
