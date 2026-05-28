from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import AutomationNotificationPreference, User
from test_inventory import auth_headers, register_and_login


def test_automation_notifications_create_deterministic_checksums(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "notify-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "notify-owner@example.com")
    ops = register_and_login(client, "notify-ops@example.com")
    owner_user = session.exec(select(User).where(User.email == "notify-owner@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    payload = {
        "owner_user_id": int(owner_user.id),
        "notification_type": "WORKFLOW_FAILURE",
        "source_event_type": "WORKFLOW_EXECUTION_FAILED",
        "source_record_id": 42,
        "notification_payload_json": {"workflow_key": "scan-pipeline"},
    }
    first = client.post("/api/v1/ops/automation/notifications/create", headers=auth_headers(ops), json=payload)
    second = client.post("/api/v1/ops/automation/notifications/create", headers=auth_headers(ops), json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["notification_checksum"] == second.json()["data"]["notification_checksum"]
    deliveries = first.json()["data"]["deliveries"]
    assert [row["delivery_rank"] for row in deliveries] == sorted(row["delivery_rank"] for row in deliveries)
    assert first.json()["data"]["alerts"][0]["escalation_level"] == "LEVEL_2"
    get_settings.cache_clear()


def test_automation_notifications_delivery_failure_and_alert_acknowledgement(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "notify-ops-2@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "notify-owner-2@example.com")
    ops = register_and_login(client, "notify-ops-2@example.com")
    owner_user = session.exec(select(User).where(User.email == "notify-owner-2@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    created = client.post(
        "/api/v1/ops/automation/notifications/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": int(owner_user.id),
            "notification_type": "DEAD_LETTER_ALERT",
            "source_event_type": "DEAD_LETTER_TRANSFER",
            "metadata_json": {"force_failed_channels": ["IN_APP"], "escalation_level": "LEVEL_3"},
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["notification_status"] == "FAILED"
    assert any(issue["issue_type"] == "DELIVERY_FAILURE" for issue in data["issues"])
    assert data["alerts"][0]["escalation_level"] == "LEVEL_3"
    alert_id = data["alerts"][0]["id"]
    ack = client.post(f"/api/v1/ops/automation/alerts/{alert_id}/acknowledge", headers=auth_headers(ops))
    assert ack.status_code == 200, ack.text
    assert ack.json()["data"]["alert_status"] == "ACKNOWLEDGED"
    get_settings.cache_clear()


def test_automation_notifications_preferences_and_owner_isolation(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "notify-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "notify-owner-3@example.com")
    peer = register_and_login(client, "notify-peer-3@example.com")
    ops = register_and_login(client, "notify-ops-3@example.com")
    owner_user = session.exec(select(User).where(User.email == "notify-owner-3@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    session.add(
        AutomationNotificationPreference(
            owner_user_id=int(owner_user.id),
            preference_key="pref-in-app-off",
            notification_type="REPLAY_WARNING",
            delivery_channel="IN_APP",
            enabled=False,
            escalation_enabled=True,
            metadata_json={},
        )
    )
    session.commit()

    created = client.post(
        "/api/v1/ops/automation/notifications/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": int(owner_user.id),
            "notification_type": "REPLAY_WARNING",
            "source_event_type": "REPLAY_DRIFT",
        },
    )
    assert created.status_code == 201, created.text
    notification_id = created.json()["data"]["id"]
    channels = {row["delivery_channel"] for row in created.json()["data"]["deliveries"]}
    assert "IN_APP" not in channels
    assert "OPS_CONSOLE" in channels

    detail = client.get(f"/api/v1/automation/notifications/{notification_id}", headers=auth_headers(owner))
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["data"]["history"]) >= 1
    assert client.get(f"/api/v1/automation/notifications/{notification_id}", headers=auth_headers(peer)).status_code == 404

    critical = client.get("/api/v1/ops/automation/alerts/critical", headers=auth_headers(ops))
    failures = client.get("/api/v1/ops/automation/delivery-failures", headers=auth_headers(ops))
    assert critical.status_code == 200, critical.text
    assert failures.status_code == 200, failures.text
    get_settings.cache_clear()
