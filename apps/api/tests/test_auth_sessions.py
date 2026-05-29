from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import UserAuthSession, UserAuthSessionEvent
from app.security.session_manager import expire_stale_sessions, utc_now
from app.services.organization_service import remove_member
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


def _session_rows(session: Session, *, user_id: int) -> list[UserAuthSession]:
    return session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.user_id == user_id)
        .order_by(UserAuthSession.issued_at.asc(), UserAuthSession.id.asc())
    ).all()


def _session_events(session: Session, *, user_id: int) -> list[UserAuthSessionEvent]:
    return session.exec(
        select(UserAuthSessionEvent)
        .where(UserAuthSessionEvent.user_id == user_id)
        .order_by(UserAuthSessionEvent.created_at.asc(), UserAuthSessionEvent.id.asc())
    ).all()


def test_auth_sessions_create_list_and_switch_active_organization(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "session-owner@example.com")
    org_one = _create_organization(client, token, display_name="Security One", slug="security-one")
    org_two = _create_organization(client, token, display_name="Security Two", slug="security-two")

    listing = client.get("/api/v1/auth/sessions", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["is_current"] is True
    assert items[0]["session_status"] == "ACTIVE"

    initial_context = client.get("/api/v1/auth/security-context", headers=auth_headers(token))
    assert initial_context.status_code == 200, initial_context.text
    assert initial_context.json()["data"]["active_organization_id"] is None

    switched_one = client.post(
        "/api/v1/auth/security-context/switch-organization",
        headers=auth_headers(token),
        json={"organization_id": org_one["id"]},
    )
    assert switched_one.status_code == 200, switched_one.text
    assert switched_one.json()["data"]["active_organization_id"] == org_one["id"]
    assert "organization:archive" in switched_one.json()["data"]["permission_keys"]

    switched_two = client.post(
        "/api/v1/auth/security-context/switch-organization",
        headers=auth_headers(token),
        json={"organization_id": org_two["id"]},
    )
    assert switched_two.status_code == 200, switched_two.text
    assert switched_two.json()["data"]["active_organization_id"] == org_two["id"]

    user_id = int(org_one["owner_user_id"])
    events = _session_events(session, user_id=user_id)
    assert any(row.event_type == "session_created" for row in events)
    assert [row.event_type for row in events if row.event_type == "organization_switched"] == [
        "organization_switched",
        "organization_switched",
    ]


def test_revoke_single_session_denies_future_use(client: TestClient, session: Session) -> None:
    token_one = register_and_login(client, "revoke-one@example.com")
    token_two = register_and_login(client, "revoke-one@example.com")

    listing = client.get("/api/v1/auth/sessions", headers=auth_headers(token_one))
    session_rows = listing.json()["data"]["items"]
    target = next(row for row in session_rows if row["is_current"] is False)

    revoked = client.post(
        "/api/v1/auth/sessions/revoke",
        headers=auth_headers(token_one),
        json={"session_id": target["id"]},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["session_status"] == "REVOKED"

    denied = client.get("/auth/me", headers=auth_headers(token_two))
    assert denied.status_code == 401, denied.text

    current_user_id = listing.json()["meta"]["owner_user_id"]
    events = _session_events(session, user_id=int(current_user_id))
    assert any(row.event_type == "session_revoked" for row in events)
    assert any(row.event_type == "invalid_access_attempt" for row in events)


def test_revoke_all_sessions_revokes_current_and_other_tokens(client: TestClient) -> None:
    token_one = register_and_login(client, "revoke-all@example.com")
    token_two = register_and_login(client, "revoke-all@example.com")

    response = client.post("/api/v1/auth/sessions/revoke-all", headers=auth_headers(token_one))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pagination"]["total_count"] >= 2

    assert client.get("/auth/me", headers=auth_headers(token_one)).status_code == 401
    assert client.get("/auth/me", headers=auth_headers(token_two)).status_code == 401


def test_expire_stale_sessions_blocks_access_and_writes_events(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "expire-session@example.com")
    listing = client.get("/api/v1/auth/sessions", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    session_id = int(listing.json()["data"]["items"][0]["id"])

    auth_session = session.get(UserAuthSession, session_id)
    assert auth_session is not None
    auth_session.expires_at = utc_now() - timedelta(minutes=5)
    session.add(auth_session)
    session.commit()

    expired = expire_stale_sessions(session)
    assert any(int(row.id or 0) == session_id for row in expired)

    denied = client.get("/auth/me", headers=auth_headers(token))
    assert denied.status_code == 401, denied.text


def test_cross_org_session_isolation_and_invalid_membership_handling(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "context-owner@example.com")
    member = register_and_login(client, "context-member@example.com")
    org_one = _create_organization(client, owner, display_name="Context One", slug="context-one")
    org_two = _create_organization(client, owner, display_name="Context Two", slug="context-two")

    accepted = _invite_and_accept(client, owner, member, organization_id=int(org_one["id"]), email="context-member@example.com")
    switch = client.post(
        "/api/v1/auth/security-context/switch-organization",
        headers=auth_headers(member),
        json={"organization_id": org_one["id"]},
    )
    assert switch.status_code == 200, switch.text

    cross_org = client.get(f"/api/v1/organizations/{org_two['id']}", headers=auth_headers(member))
    assert cross_org.status_code == 403, cross_org.text

    remove_member(
        session,
        owner_user_id=int(org_one["owner_user_id"]),
        organization_id=int(org_one["id"]),
        member_user_id=int(accepted["user_id"]),
    )

    context = client.get("/api/v1/auth/security-context", headers=auth_headers(member))
    assert context.status_code == 200, context.text
    assert context.json()["data"]["active_organization_id"] is None
    denied_members = client.get(f"/api/v1/organizations/{org_one['id']}/members", headers=auth_headers(member))
    assert denied_members.status_code == 403, denied_members.text

    session_rows = _session_rows(session, user_id=int(accepted["user_id"]))
    assert session_rows[0].organization_id is None
    events = _session_events(session, user_id=int(accepted["user_id"]))
    assert any(row.event_type == "membership_validation_failed" for row in events)
