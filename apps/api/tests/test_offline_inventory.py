from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import OfflineInventoryEvent, User
from app.schemas.offline_inventory import OfflineSyncConflictRegisterRequest
from app.services.offline_inventory_service import register_sync_conflict
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


def _user_id_for_email(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None and user.id is not None
    return int(user.id)


def test_offline_inventory_creation_and_deterministic_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "offline-inv-owner@example.com")
    organization_id = _create_organization(client, owner, slug="offline-inv-org")
    _register_device(client, owner, organization_id, device_identifier="offline-dev-1")

    alpha = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "local-alpha", "record_payload_json": {"sku": "A"}},
    )
    zeta = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "local-zeta", "record_payload_json": {"sku": "Z"}},
    )
    assert alpha.status_code == 201, alpha.text
    assert zeta.status_code == 201, zeta.text

    dashboard = client.get(f"/api/v1/organizations/{organization_id}/offline-inventory", headers=auth_headers(owner))
    assert dashboard.status_code == 200, dashboard.text
    records = dashboard.json()["data"]["recent_records"]
    assert [row["local_record_identifier"] for row in records] == ["local-alpha", "local-zeta"]


def test_offline_changes_queue_conflict_lineage(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "offline-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="offline-lineage-org")
    device_id = _register_device(client, owner, organization_id, device_identifier="offline-dev-lineage")
    _start_mobile_session(client, owner, organization_id, device_id=device_id)
    actor_user_id = _user_id_for_email(session, "offline-lineage-owner@example.com")

    record = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "local-lineage", "record_payload_json": {"qty": 1}},
    )
    assert record.status_code == 201, record.text

    change = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory/change",
        headers=auth_headers(owner),
        json={"device_id": device_id, "change_type": "update", "change_payload_json": {"qty": 2}},
    )
    queue = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory/queue",
        headers=auth_headers(owner),
        json={"device_id": device_id, "queue_payload_json": {"operation": "push_inventory"}},
    )
    assert change.status_code == 201, change.text
    assert queue.status_code == 201, queue.text

    conflict = register_sync_conflict(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        payload=OfflineSyncConflictRegisterRequest(
            conflict_type="payload_mismatch",
            local_payload_json={"qty": 2},
            server_payload_json={"qty": 5},
        ),
    )
    ack = client.patch(
        f"/api/v1/organizations/{organization_id}/offline-inventory/conflicts/{conflict.id}",
        headers=auth_headers(owner),
        json={"conflict_status": "acknowledged"},
    )
    assert ack.status_code == 200, ack.text

    events = session.exec(
        select(OfflineInventoryEvent)
        .where(OfflineInventoryEvent.organization_id == organization_id)
        .order_by(OfflineInventoryEvent.created_at.asc(), OfflineInventoryEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "offline_inventory_created",
        "offline_change_registered",
        "sync_queue_item_created",
        "sync_conflict_detected",
        "sync_conflict_acknowledged",
    ]


def test_offline_inventory_org_isolation_and_unauthorized_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "offline-isolation-owner@example.com")
    outsider = register_and_login(client, "offline-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="offline-isolation-org")
    _create_organization(client, outsider, slug="offline-outsider-org")
    _register_device(client, owner, organization_id, device_identifier="offline-dev-iso")

    created = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(owner),
        json={"local_record_identifier": "local-secret", "record_payload_json": {}},
    )
    assert created.status_code == 201, created.text

    denied_dashboard = client.get(f"/api/v1/organizations/{organization_id}/offline-inventory", headers=auth_headers(outsider))
    denied_queue = client.get(f"/api/v1/organizations/{organization_id}/offline-inventory/queue", headers=auth_headers(outsider))
    denied_create = client.post(
        f"/api/v1/organizations/{organization_id}/offline-inventory",
        headers=auth_headers(outsider),
        json={"local_record_identifier": "local-hack", "record_payload_json": {}},
    )

    assert denied_dashboard.status_code == 403, denied_dashboard.text
    assert denied_queue.status_code == 403, denied_queue.text
    assert denied_create.status_code == 403, denied_create.text

    attempts = session.exec(
        select(OfflineInventoryEvent)
        .where(OfflineInventoryEvent.organization_id == organization_id)
        .where(OfflineInventoryEvent.event_type == "unauthorized_offline_inventory_access_attempt")
        .order_by(OfflineInventoryEvent.id.asc())
    ).all()
    assert len(attempts) >= 3
