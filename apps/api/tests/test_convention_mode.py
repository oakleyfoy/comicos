from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ConventionActivity, ConventionModeEvent
from app.services.convention_mode_service import remove_inventory
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def test_convention_session_booth_staging_and_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "convention-owner@example.com")
    organization_id = _create_organization(client, owner, slug="convention-org")

    alpha = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Alpha Con"},
    )
    zeta = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Zeta Con"},
    )
    assert alpha.status_code == 201, alpha.text
    assert zeta.status_code == 201, zeta.text

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    assert [row["session_name"] for row in listing.json()["data"]["items"]] == ["Alpha Con", "Zeta Con"]

    session_id = alpha.json()["data"]["id"]
    booth = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/booths",
        headers=auth_headers(owner),
        json={"convention_session_id": session_id, "booth_name": "Aisle 12"},
    )
    assert booth.status_code == 201, booth.text

    staged = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/inventory",
        headers=auth_headers(owner),
        json={"convention_session_id": session_id, "inventory_item_id": 9001},
    )
    assert staged.status_code == 201, staged.text


def test_convention_lineage_and_activity_logging(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "convention-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="convention-lineage-org")

    created = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Lineage Con"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["data"]["id"]

    started = client.patch(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions/{session_id}",
        headers=auth_headers(owner),
        json={"session_status": "active"},
    )
    booth = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/booths",
        headers=auth_headers(owner),
        json={"convention_session_id": session_id, "booth_name": "Main"},
    )
    assert started.status_code == 200, started.text
    assert booth.status_code == 201, booth.text
    booth_id = booth.json()["data"]["id"]

    opened = client.patch(
        f"/api/v1/organizations/{organization_id}/convention-mode/booths/{booth_id}",
        headers=auth_headers(owner),
        json={"booth_status": "active"},
    )
    staged = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/inventory",
        headers=auth_headers(owner),
        json={"convention_session_id": session_id, "inventory_item_id": 42},
    )
    assert opened.status_code == 200, opened.text
    assert staged.status_code == 201, staged.text
    stage_id = staged.json()["data"]["id"]

    owner_user_id = int(client.get("/auth/me", headers=auth_headers(owner)).json()["id"])
    remove_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=owner_user_id,
        stage_id=stage_id,
    )

    events = session.exec(
        select(ConventionModeEvent)
        .where(ConventionModeEvent.organization_id == organization_id)
        .order_by(ConventionModeEvent.created_at.asc(), ConventionModeEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "convention_session_created",
        "convention_session_started",
        "booth_created",
        "booth_opened",
        "inventory_staged",
        "inventory_removed",
    ]

    activities = session.exec(
        select(ConventionActivity)
        .where(ConventionActivity.organization_id == organization_id)
        .order_by(ConventionActivity.created_at.asc(), ConventionActivity.id.asc())
    ).all()
    assert [row.activity_type for row in activities] == [
        "session_created",
        "booth_opened",
        "inventory_staged",
        "inventory_removed",
    ]


def test_convention_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "convention-isolation-owner@example.com")
    outsider = register_and_login(client, "convention-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="convention-isolation-org")
    _create_organization(client, outsider, slug="convention-outsider-org")

    created = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(owner),
        json={"session_name": "Private Con"},
    )
    assert created.status_code == 201, created.text

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/convention-mode", headers=auth_headers(outsider))
    denied_create = client.post(
        f"/api/v1/organizations/{organization_id}/convention-mode/sessions",
        headers=auth_headers(outsider),
        json={"session_name": "Hack Con"},
    )

    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_create.status_code == 403, denied_create.text

    attempts = session.exec(
        select(ConventionModeEvent)
        .where(ConventionModeEvent.organization_id == organization_id)
        .where(ConventionModeEvent.event_type == "unauthorized_convention_access_attempt")
        .order_by(ConventionModeEvent.id.asc())
    ).all()
    assert len(attempts) >= 2
