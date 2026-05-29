from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OrganizationReviewDecision, OrganizationReviewEvent
from app.services.review_permissions import validate_review_access
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


def test_review_creation_assignment_and_inventory_hydration(client: TestClient) -> None:
    owner = register_and_login(client, "review-owner@example.com")
    staff = register_and_login(client, "review-staff@example.com")
    organization_id = _create_organization(client, owner, slug="review-org")
    inventory_item_id = _inventory_copy_id(client, owner)

    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "review-staff@example.com"},
    )
    token = invite.json()["data"]["invitation_token"]
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(staff))
    staff_user_id = int(accepted.json()["data"]["user_id"])

    created = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={
            "inventory_item_id": inventory_item_id,
            "review_type": "grading",
            "assigned_user_id": staff_user_id,
            "queue_name": "grading_review",
        },
    )
    assert created.status_code == 201, created.text
    review_id = int(created.json()["data"]["id"])
    assert created.json()["data"]["review_status"] == "ASSIGNED"
    assert created.json()["data"]["approval_queue_name"] == "grading_review"

    listing = client.get(
        f"/inventory?organization_id={organization_id}&page=1&page_size=10",
        headers=auth_headers(owner),
    )
    row = listing.json()["items"][0]
    assert row["organization_active_review_id"] == review_id
    assert row["organization_review_status"] == "ASSIGNED"
    assert row["organization_review_type"] == "grading"

    assigned = client.post(
        f"/api/v1/organizations/{organization_id}/reviews/{review_id}/assign",
        headers=auth_headers(owner),
        json={"assigned_user_id": staff_user_id},
    )
    assert assigned.status_code == 200, assigned.text


def test_approval_and_rejection_append_only_decisions(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "review-approve-owner@example.com")
    organization_id = _create_organization(client, owner, slug="review-approve-org")
    inventory_item_id = _inventory_copy_id(client, owner)

    created = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "review_type": "authentication"},
    )
    review_id = int(created.json()["data"]["id"])

    approved = client.post(
        f"/api/v1/organizations/{organization_id}/reviews/{review_id}/approve",
        headers=auth_headers(owner),
        json={"decision_notes": "Looks good"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["review_status"] == "APPROVED"

    decisions = client.get(
        f"/api/v1/organizations/{organization_id}/reviews/{review_id}/decisions",
        headers=auth_headers(owner),
    )
    assert decisions.status_code == 200, decisions.text
    assert len(decisions.json()["data"]["items"]) == 1
    assert decisions.json()["data"]["items"][0]["decision_type"] == "APPROVED"

    decision_count = len(session.exec(select(OrganizationReviewDecision)).all())
    assert decision_count == 1

    rejected_review = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={"inventory_item_id": inventory_item_id, "review_type": "marketplace"},
    )
    rejected_id = int(rejected_review.json()["data"]["id"])
    rejected = client.post(
        f"/api/v1/organizations/{organization_id}/reviews/{rejected_id}/reject",
        headers=auth_headers(owner),
        json={"decision_notes": "Needs work"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["review_status"] == "REJECTED"
    assert len(session.exec(select(OrganizationReviewDecision)).all()) == decision_count + 1


def test_review_queue_movement_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "review-queue-owner@example.com")
    organization_id = _create_organization(client, owner, slug="review-queue-org")
    first_item = _inventory_copy_id(client, owner)
    create_order(client, owner, items=[
        {
            "title": "Saga",
            "publisher": "Image",
            "issue_number": "2",
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 6.00,
        }
    ])
    second_item = int(
        client.get("/inventory?page=1&page_size=10", headers=auth_headers(owner)).json()["items"][-1]["inventory_copy_id"]
    )

    first_review = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={"inventory_item_id": first_item, "review_type": "intake"},
    )
    second_review = client.post(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(owner),
        json={"inventory_item_id": second_item, "review_type": "intake"},
    )
    review_one = int(first_review.json()["data"]["id"])
    review_two = int(second_review.json()["data"]["id"])

    moved = client.post(
        f"/api/v1/organizations/{organization_id}/reviews/queues/move",
        headers=auth_headers(owner),
        json={"review_id": review_two, "queue_name": "marketplace_approval", "queue_position": 1},
    )
    assert moved.status_code == 200, moved.text

    queues = client.get(
        f"/api/v1/organizations/{organization_id}/reviews/queues",
        headers=auth_headers(owner),
    )
    assert queues.status_code == 200, queues.text
    marketplace_rows = [row for row in queues.json()["data"]["items"] if row["queue_name"] == "marketplace_approval"]
    assert [row["review_id"] for row in marketplace_rows] == [review_two]
    assert marketplace_rows[0]["queue_position"] == 1

    intake_rows = [row for row in queues.json()["data"]["items"] if row["queue_name"] == "intake_review"]
    assert any(row["review_id"] == review_one for row in intake_rows)


def test_org_isolation_and_unauthorized_review_access(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "review-isolation-owner@example.com")
    outsider = register_and_login(client, "review-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="review-isolation-org")

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/reviews",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    outsider_user = client.get("/auth/me", headers=auth_headers(outsider))
    outsider_user_id = int(outsider_user.json()["id"])
    before = len(session.exec(select(OrganizationReviewEvent)).all())
    with pytest.raises(HTTPException) as exc:
        validate_review_access(
            session,
            organization_id=organization_id,
            actor_user_id=outsider_user_id,
            action_key="operations:view",
        )
    assert exc.value.status_code == 403
    session.commit()
    after = session.exec(select(OrganizationReviewEvent)).all()
    assert len(after) == before + 1
    assert after[-1].event_type == "unauthorized_review_access_attempt"
