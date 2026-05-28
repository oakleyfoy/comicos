from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import AutomationWorkerLease
from app.services.automation_workers import release_expired_leases
from test_automation_jobs import _create_job
from test_inventory import auth_headers, register_and_login


def _register_worker(client: TestClient, token: str, *, worker_identifier: str, queue_keys: list[str] | None = None):
    return client.post(
        "/api/v1/ops/automation/workers/register",
        headers=auth_headers(token),
        json={
            "worker_identifier": worker_identifier,
            "worker_type": "REPLAY_WORKER",
            "queue_scope_json": {"queue_keys": queue_keys or ["worker-runtime"]},
            "max_concurrency": 1,
        },
    )


def test_automation_workers_register_lease_heartbeat_and_execution_lineage(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "worker-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "worker-owner@example.com")
    ops = register_and_login(client, "worker-ops@example.com")
    low = _create_job(client, owner, queue_key="worker-runtime", job_key="runtime-low", priority="LOW")
    high = _create_job(client, owner, queue_key="worker-runtime", job_key="runtime-high", priority="CRITICAL")
    assert low.status_code == 201, low.text
    assert high.status_code == 201, high.text

    first = _register_worker(client, ops, worker_identifier="runtime-worker-1")
    second = _register_worker(client, ops, worker_identifier="runtime-worker-1")
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    worker_id = first.json()["data"]["id"]
    assert first.json()["data"]["worker_key"] == second.json()["data"]["worker_key"]

    stale_before = client.get("/api/v1/ops/automation/workers/stale", headers=auth_headers(ops))
    assert stale_before.status_code == 200, stale_before.text
    assert any(int(row["id"]) == int(worker_id) for row in stale_before.json()["data"]["items"])

    heartbeat = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/heartbeat",
        headers=auth_headers(ops),
        json={"heartbeat_status": "HEALTHY", "active_job_count": 0},
    )
    assert heartbeat.status_code == 200, heartbeat.text

    lease = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-a", "lease_seconds": 300},
    )
    assert lease.status_code == 200, lease.text
    assert lease.json()["data"]["job_id"] == high.json()["data"]["id"]

    renewed = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease/renew",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-a", "lease_seconds": 420},
    )
    assert renewed.status_code == 200, renewed.text

    started = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/execution/start",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-a", "metadata_json": {"mode": "test"}},
    )
    assert started.status_code == 200, started.text
    started_data = started.json()["data"]
    assert started_data["execution_status"] == "STARTED"
    assert started_data["execution_snapshot_json"]["job"]["job_checksum"] == high.json()["data"]["job_checksum"]

    completed = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/execution/complete",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-a", "metadata_json": {"result": "ok"}},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["execution_status"] == "COMPLETED"

    owner_workers = client.get("/api/v1/automation/workers", headers=auth_headers(owner))
    assert owner_workers.status_code == 200, owner_workers.text
    assert any(int(row["id"]) == int(worker_id) for row in owner_workers.json()["data"]["items"])
    owner_detail = client.get(f"/api/v1/automation/workers/{worker_id}", headers=auth_headers(owner))
    assert owner_detail.status_code == 200, owner_detail.text
    history_types = [row["event_type"] for row in owner_detail.json()["data"]["history"]]
    assert "WORKER_REGISTERED" in history_types
    assert "LEASE_ACQUIRED" in history_types
    assert "EXECUTION_COMPLETED" in history_types
    get_settings.cache_clear()


def test_automation_workers_enforce_concurrency_and_owner_isolation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "worker-ops-2@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "worker-owner-2@example.com")
    peer = register_and_login(client, "worker-peer-2@example.com")
    ops = register_and_login(client, "worker-ops-2@example.com")
    assert _create_job(client, owner, queue_key="worker-concurrency", job_key="c1", priority="HIGH").status_code == 201
    assert _create_job(client, owner, queue_key="worker-concurrency", job_key="c2", priority="NORMAL").status_code == 201

    registered = _register_worker(client, ops, worker_identifier="runtime-worker-2", queue_keys=["worker-concurrency"])
    assert registered.status_code == 201, registered.text
    worker_id = registered.json()["data"]["id"]

    first_lease = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-b", "lease_seconds": 300},
    )
    assert first_lease.status_code == 200, first_lease.text
    blocked = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-c", "lease_seconds": 300},
    )
    assert blocked.status_code == 409, blocked.text

    assert client.get(f"/api/v1/automation/workers/{worker_id}", headers=auth_headers(peer)).status_code == 404
    ops_workers = client.get("/api/v1/ops/automation/workers", headers=auth_headers(ops))
    ops_issues = client.get("/api/v1/ops/automation/workers/issues", headers=auth_headers(ops))
    assert ops_workers.status_code == 200, ops_workers.text
    assert ops_issues.status_code == 200, ops_issues.text
    assert client.post("/api/v1/ops/automation/workers", headers=auth_headers(ops), json={}).status_code == 405
    get_settings.cache_clear()


def test_automation_workers_release_expired_leases_and_fail_execution(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "worker-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "worker-owner-3@example.com")
    ops = register_and_login(client, "worker-ops-3@example.com")
    created = _create_job(client, owner, queue_key="worker-expire", job_key="expire-1", priority="HIGH")
    assert created.status_code == 201, created.text
    registered = _register_worker(client, ops, worker_identifier="runtime-worker-3", queue_keys=["worker-expire"])
    assert registered.status_code == 201, registered.text
    worker_id = registered.json()["data"]["id"]

    lease = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-expire", "lease_seconds": 30},
    )
    assert lease.status_code == 200, lease.text
    lease_row = session.exec(
        select(AutomationWorkerLease).where(AutomationWorkerLease.reservation_token == "lease-expire")
    ).first()
    assert lease_row is not None
    lease_row.lease_expires_at = lease_row.lease_expires_at - timedelta(seconds=90)
    session.add(lease_row)
    session.commit()

    released = release_expired_leases(session)
    assert released.total_items == 1
    assert released.items[0].lease_status == "EXPIRED"

    second_job = _create_job(client, owner, queue_key="worker-expire", job_key="expire-2", priority="CRITICAL")
    assert second_job.status_code == 201, second_job.text
    second_lease = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-fail", "lease_seconds": 300},
    )
    assert second_lease.status_code == 200, second_lease.text
    started = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/execution/start",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-fail"},
    )
    assert started.status_code == 200, started.text
    failed = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/execution/fail",
        headers=auth_headers(ops),
        json={"reservation_token": "lease-fail", "failure_reason": "timeout path"},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["data"]["execution_status"] == "FAILED"

    owner_issues = client.get(f"/api/v1/automation/workers/{worker_id}/issues", headers=auth_headers(owner))
    assert owner_issues.status_code == 200, owner_issues.text
    issue_types = {row["issue_type"] for row in owner_issues.json()["data"]["items"]}
    assert "LEASE_EXPIRED" in issue_types
    assert "WORKER_RUNTIME_FAILURE" in issue_types
    get_settings.cache_clear()
