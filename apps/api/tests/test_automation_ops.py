from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import AutomationOpsHistory, AutomationOpsMetric, AutomationOpsSnapshot, User
from test_inventory import auth_headers, register_and_login


def test_automation_ops_snapshot_checksums_and_metric_ordering(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dash@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "ops-dash-owner@example.com")
    ops = register_and_login(client, "ops-dash@example.com")
    owner_user = session.exec(select(User).where(User.email == "ops-dash-owner@example.com")).first()
    assert owner_user is not None and owner_user.id is not None

    payload = {
        "owner_user_id": int(owner_user.id),
        "snapshot_type": "SYSTEM_HEALTH",
        "replay_key": "ops-snapshot-001",
        "metadata_json": {"scope": "owner"},
    }
    first = client.post("/api/v1/ops/automation/snapshots/create", headers=auth_headers(ops), json=payload)
    second = client.post("/api/v1/ops/automation/snapshots/create", headers=auth_headers(ops), json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["snapshot_checksum"] == second_data["snapshot_checksum"]

    metrics = client.get(
        "/api/v1/automation/ops/metrics",
        headers=auth_headers(owner),
        params={"snapshot_id": first_data["id"], "limit": 100},
    )
    assert metrics.status_code == 200, metrics.text
    metric_rows = metrics.json()["data"]["items"]
    ordering = [(row["metric_category"], row["metric_rank"], row["metric_key"]) for row in metric_rows]
    assert ordering == sorted(ordering)
    assert len(session.exec(select(AutomationOpsMetric)).all()) >= 8
    get_settings.cache_clear()


def test_automation_ops_audit_and_safe_control_lineage(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dash-2@example.com")
    get_settings.cache_clear()

    ops = register_and_login(client, "ops-dash-2@example.com")
    snapshot = client.post(
        "/api/v1/ops/automation/snapshots/create",
        headers=auth_headers(ops),
        json={"snapshot_type": "QUEUE_STATE", "replay_key": "ops-audit-001"},
    )
    assert snapshot.status_code == 201, snapshot.text
    snapshot_id = snapshot.json()["data"]["id"]

    audit = client.post(
        "/api/v1/ops/automation/audits/run",
        headers=auth_headers(ops),
        json={"audit_type": "QUEUE_AUDIT", "audit_scope": "system", "snapshot_id": snapshot_id, "replay_key": "queue-audit-001"},
    )
    assert audit.status_code == 201, audit.text
    audit_repeat = client.post(
        "/api/v1/ops/automation/audits/run",
        headers=auth_headers(ops),
        json={"audit_type": "QUEUE_AUDIT", "audit_scope": "system", "snapshot_id": snapshot_id, "replay_key": "queue-audit-001"},
    )
    assert audit_repeat.status_code == 201, audit_repeat.text
    assert audit_repeat.json()["data"]["id"] == audit.json()["data"]["id"]

    control = client.post(
        "/api/v1/ops/automation/controls/apply",
        headers=auth_headers(ops),
        json={
            "control_type": "REPLAY_VERIFY",
            "target_scope": "scan-replay",
            "snapshot_id": snapshot_id,
            "replay_key": "replay-verify-001",
        },
    )
    assert control.status_code == 201, control.text
    assert control.json()["data"]["control_status"] == "APPLIED"

    forbidden = client.post(
        "/api/v1/ops/automation/controls/apply",
        headers=auth_headers(ops),
        json={"control_type": "DELETE_QUEUE", "target_scope": "default", "replay_key": "bad"},
    )
    assert forbidden.status_code == 403

    history_count = len(session.exec(select(AutomationOpsHistory)).all())
    assert history_count >= 3
    get_settings.cache_clear()


def test_automation_ops_owner_isolation_and_system_health(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dash-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "ops-dash-owner-3@example.com")
    peer = register_and_login(client, "ops-dash-peer-3@example.com")
    ops = register_and_login(client, "ops-dash-3@example.com")
    owner_user = session.exec(select(User).where(User.email == "ops-dash-owner-3@example.com")).first()
    assert owner_user is not None and owner_user.id is not None

    created = client.post(
        "/api/v1/ops/automation/snapshots/create",
        headers=auth_headers(ops),
        json={"owner_user_id": int(owner_user.id), "snapshot_type": "SYSTEM_HEALTH", "replay_key": "owner-scope-001"},
    )
    assert created.status_code == 201, created.text
    snapshot_id = created.json()["data"]["id"]

    assert client.get(f"/api/v1/automation/ops/snapshots/{snapshot_id}", headers=auth_headers(owner)).status_code == 200
    assert client.get(f"/api/v1/automation/ops/snapshots/{snapshot_id}", headers=auth_headers(peer)).status_code == 404

    owner_list = client.get("/api/v1/automation/ops/snapshots", headers=auth_headers(owner))
    peer_list = client.get("/api/v1/automation/ops/snapshots", headers=auth_headers(peer))
    assert owner_list.status_code == 200, owner_list.text
    assert peer_list.status_code == 200, peer_list.text
    assert len(owner_list.json()["data"]["items"]) >= 1
    assert all(row["owner_user_id"] == int(owner_user.id) for row in owner_list.json()["data"]["items"])
    assert len(peer_list.json()["data"]["items"]) == 0

    health = client.get("/api/v1/ops/automation/system-health", headers=auth_headers(ops))
    assert health.status_code == 200, health.text
    assert health.json()["data"]["snapshot_status"] in {"HEALTHY", "WARNING", "DEGRADED", "CRITICAL"}
    assert session.exec(select(AutomationOpsSnapshot)).first() is not None
    get_settings.cache_clear()
