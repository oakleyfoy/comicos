from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MobileFoundationEvent
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _register_device(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    device_identifier: str,
    device_name: str,
    device_type: str = "tablet",
):
    return client.post(
        f"/api/v1/organizations/{organization_id}/mobile/devices",
        headers=auth_headers(token),
        json={
            "device_identifier": device_identifier,
            "device_name": device_name,
            "device_type": device_type,
        },
    )


def test_mobile_device_registration_and_deterministic_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "mobile-owner@example.com")
    organization_id = _create_organization(client, owner, slug="mobile-org")

    alpha = _register_device(client, owner, organization_id, device_identifier="dev-alpha", device_name="Alpha Pad")
    zeta = _register_device(client, owner, organization_id, device_identifier="dev-zeta", device_name="Zeta Phone", device_type="phone")

    assert alpha.status_code == 201, alpha.text
    assert zeta.status_code == 201, zeta.text

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/mobile/devices?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    payload = listing.json()["data"]
    assert [row["device_identifier"] for row in payload["items"]] == ["dev-alpha", "dev-zeta"]
    assert payload["permissions"]["can_view"] is True
    assert payload["permissions"]["can_manage"] is True


def test_mobile_device_register_idempotent_and_session_contract_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "mobile-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="mobile-lineage-org")

    first = _register_device(client, owner, organization_id, device_identifier="dev-idem", device_name="Idempotent")
    second = _register_device(client, owner, organization_id, device_identifier="dev-idem", device_name="Idempotent Updated")

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    device_id = first.json()["data"]["id"]
    assert second.json()["data"]["id"] == device_id

    session_resp = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(owner),
        json={"device_id": device_id},
    )
    assert session_resp.status_code == 201, session_resp.text

    contract_resp = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/contracts",
        headers=auth_headers(owner),
        json={"contract_type": "metadata", "contract_payload_json": {"schema_version": 1}},
    )
    assert contract_resp.status_code == 201, contract_resp.text

    events = session.exec(
        select(MobileFoundationEvent)
        .where(MobileFoundationEvent.organization_id == organization_id)
        .order_by(MobileFoundationEvent.created_at.asc(), MobileFoundationEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "mobile_device_registered",
        "mobile_device_seen",
        "mobile_session_started",
        "offline_contract_created",
    ]


def test_mobile_org_isolation_and_unauthorized_access_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "mobile-isolation-owner@example.com")
    outsider = register_and_login(client, "mobile-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="mobile-isolation-org")
    _create_organization(client, outsider, slug="mobile-outsider-org")

    registered = _register_device(client, owner, organization_id, device_identifier="dev-owner", device_name="Owner Device")
    assert registered.status_code == 201, registered.text
    device_id = registered.json()["data"]["id"]

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile", headers=auth_headers(outsider))
    denied_devices = client.get(f"/api/v1/organizations/{organization_id}/mobile/devices", headers=auth_headers(outsider))
    denied_patch = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile/devices/{device_id}",
        headers=auth_headers(outsider),
        json={"device_status": "inactive"},
    )

    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_devices.status_code == 403, denied_devices.text
    assert denied_patch.status_code == 403, denied_patch.text

    attempts = session.exec(
        select(MobileFoundationEvent)
        .where(MobileFoundationEvent.organization_id == organization_id)
        .where(MobileFoundationEvent.event_type == "unauthorized_mobile_access_attempt")
        .order_by(MobileFoundationEvent.id.asc())
    ).all()
    assert len(attempts) >= 3
    assert all(row.event_payload_json.get("action", "").startswith("mobile:") for row in attempts)
