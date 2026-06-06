"""P44 organization mobile scanning tests (dealer capture workflows)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ScanEvent
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _register_device(client: TestClient, token: str, organization_id: int, *, device_identifier: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/devices",
        headers=auth_headers(token),
        json={
            "device_identifier": device_identifier,
            "device_name": device_identifier,
            "device_type": "tablet",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _start_mobile_session(client: TestClient, token: str, organization_id: int, *, device_id: int) -> None:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/mobile/sessions",
        headers=auth_headers(token),
        json={"device_id": device_id},
    )
    assert response.status_code == 201, response.text


def test_scan_capture_normalization_and_lookup(client: TestClient) -> None:
    owner = register_and_login(client, "scan-owner@example.com")
    organization_id = _create_organization(client, owner, slug="scan-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="scan-dev-1")
    _start_mobile_session(client, owner, organization_id, device_id=device_id)

    capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": device_id, "scan_type": "upc", "scan_value": " 012345678905 "},
    )
    assert capture.status_code == 201, capture.text
    body = capture.json()["data"]
    assert body["capture"]["normalized_value"] == "012345678905"
    assert body["capture"]["scan_status"] == "lookup_complete"
    assert any(row["lookup_type"] == "known_upc" for row in body["lookup_results"])

    listing = client.get(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/scans?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert listing.status_code == 200, listing.text
    assert [row["normalized_value"] for row in listing.json()["data"]["items"]] == ["012345678905"]


def test_intake_staging_and_append_only_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "scan-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="scan-lineage-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="scan-dev-lineage")
    _start_mobile_session(client, owner, organization_id, device_id=device_id)

    capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(owner),
        json={"device_id": device_id, "scan_type": "qr", "scan_value": "INTAKE-QR-001"},
    )
    assert capture.status_code == 201, capture.text
    capture_id = capture.json()["data"]["capture"]["id"]

    staging = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/staging",
        headers=auth_headers(owner),
        json={"scan_capture_id": capture_id, "staging_payload_json": {"note": "intake"}},
    )
    assert staging.status_code == 201, staging.text
    staging_id = staging.json()["data"]["id"]

    approved = client.patch(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/staging/{staging_id}",
        headers=auth_headers(owner),
        json={"staging_status": "approved"},
    )
    assert approved.status_code == 200, approved.text

    events = session.exec(
        select(ScanEvent)
        .where(ScanEvent.organization_id == organization_id)
        .order_by(ScanEvent.created_at.asc(), ScanEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "scan_captured",
        "scan_normalized",
        "inventory_lookup_completed",
        "intake_record_created",
        "intake_record_approved",
    ]


def test_mobile_scanning_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "scan-isolation-owner@example.com")
    outsider = register_and_login(client, "scan-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="scan-isolation-org")
    _create_organization(client, outsider, slug="scan-outsider-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="scan-dev-iso")

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/mobile-scanning", headers=auth_headers(outsider))
    denied_capture = client.post(
        f"/api/v1/organizations/{organization_id}/mobile-scanning/capture",
        headers=auth_headers(outsider),
        json={"device_id": device_id, "scan_type": "barcode", "scan_value": "123"},
    )

    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_capture.status_code == 403, denied_capture.text

    attempts = session.exec(
        select(ScanEvent)
        .where(ScanEvent.organization_id == organization_id)
        .where(ScanEvent.event_type == "unauthorized_scan_access_attempt")
        .order_by(ScanEvent.id.asc())
    ).all()
    assert len(attempts) >= 2
