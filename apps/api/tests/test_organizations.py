from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.organization_service import remove_member
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, display_name: str, slug: str):
    return client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={
            "display_name": display_name,
            "slug": slug,
            "organization_type": "DEALER",
        },
    )


def test_organization_creation_duplicate_slug_and_listing_order(client: TestClient) -> None:
    owner = register_and_login(client, "org-owner@example.com")

    alpha = _create_organization(client, owner, display_name="Alpha Comics", slug="alpha-comics")
    beta = _create_organization(client, owner, display_name="Beta Comics", slug="beta-comics")
    duplicate = _create_organization(client, owner, display_name="Duplicate", slug="alpha-comics")

    assert alpha.status_code == 201, alpha.text
    assert beta.status_code == 201, beta.text
    assert duplicate.status_code == 409, duplicate.text

    listing = client.get("/api/v1/organizations?limit=10&offset=0", headers=auth_headers(owner))
    assert listing.status_code == 200, listing.text
    items = listing.json()["data"]["items"]
    assert [row["slug"] for row in items] == ["alpha-comics", "beta-comics"]
    assert all(row["active_member_count"] == 1 for row in items)


def test_organization_invitation_is_duplicate_safe_and_event_order_is_deterministic(client: TestClient) -> None:
    owner = register_and_login(client, "org-invite-owner@example.com")
    create = _create_organization(client, owner, display_name="Invite Org", slug="invite-org")
    organization_id = create.json()["data"]["id"]

    first_invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "staff@example.com", "expires_in_days": 10},
    )
    second_invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "staff@example.com", "expires_in_days": 10},
    )

    assert first_invite.status_code == 201, first_invite.text
    assert second_invite.status_code == 200, second_invite.text
    assert first_invite.json()["data"]["id"] == second_invite.json()["data"]["id"]
    assert first_invite.json()["data"]["invitation_token"] == second_invite.json()["data"]["invitation_token"]

    events = client.get(f"/api/v1/organizations/{organization_id}/events", headers=auth_headers(owner))
    assert events.status_code == 200, events.text
    assert [row["event_type"] for row in events.json()["data"]["items"]] == ["organization_created", "member_invited"]


def test_organization_invitation_acceptance_member_listing_and_access_control(client: TestClient) -> None:
    owner = register_and_login(client, "org-accept-owner@example.com")
    invited = register_and_login(client, "org-member@example.com")
    outsider = register_and_login(client, "org-outsider@example.com")

    create = _create_organization(client, owner, display_name="Acceptance Org", slug="acceptance-org")
    organization_id = create.json()["data"]["id"]
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "org-member@example.com"},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["data"]["invitation_token"]

    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(invited))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["user_email"] == "org-member@example.com"

    invited_orgs = client.get("/api/v1/organizations", headers=auth_headers(invited))
    assert invited_orgs.status_code == 200, invited_orgs.text
    assert [row["slug"] for row in invited_orgs.json()["data"]["items"]] == ["acceptance-org"]

    members = client.get(f"/api/v1/organizations/{organization_id}/members", headers=auth_headers(invited))
    assert members.status_code == 200, members.text
    member_rows = members.json()["data"]["items"]
    assert [row["user_email"] for row in member_rows] == ["org-accept-owner@example.com", "org-member@example.com"]
    assert client.get(f"/api/v1/organizations/{organization_id}", headers=auth_headers(outsider)).status_code == 403


def test_organization_member_removal_and_append_only_events(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "org-remove-owner@example.com")
    invited = register_and_login(client, "org-remove-member@example.com")

    create = _create_organization(client, owner, display_name="Removal Org", slug="removal-org")
    organization_id = create.json()["data"]["id"]
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "org-remove-member@example.com"},
    )
    token = invite.json()["data"]["invitation_token"]
    accepted = client.post(f"/api/v1/organizations/invitations/{token}/accept", headers=auth_headers(invited))
    assert accepted.status_code == 200, accepted.text
    owner_user_id = create.json()["data"]["owner_user_id"]
    member_user_id = accepted.json()["data"]["user_id"]

    removed = remove_member(
        session,
        owner_user_id=owner_user_id,
        organization_id=organization_id,
        member_user_id=member_user_id,
    )
    assert removed.membership_status == "REMOVED"
    assert removed.removed_at is not None

    events = client.get(f"/api/v1/organizations/{organization_id}/events", headers=auth_headers(owner))
    event_types = [row["event_type"] for row in events.json()["data"]["items"]]
    assert event_types == ["organization_created", "member_invited", "invitation_accepted", "member_removed"]


def test_archived_organization_rejects_new_invitations(client: TestClient) -> None:
    owner = register_and_login(client, "org-archive-owner@example.com")
    create = _create_organization(client, owner, display_name="Archive Org", slug="archive-org")
    organization_id = create.json()["data"]["id"]

    archived = client.post(
        f"/api/v1/organizations/{organization_id}/archive",
        headers=auth_headers(owner),
        json={"reason": "Archive for test"},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["status"] == "ARCHIVED"

    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invite",
        headers=auth_headers(owner),
        json={"email": "late-member@example.com"},
    )
    assert invite.status_code == 409, invite.text

    events = client.get(f"/api/v1/organizations/{organization_id}/events", headers=auth_headers(owner))
    assert [row["event_type"] for row in events.json()["data"]["items"]] == ["organization_created", "organization_archived"]
