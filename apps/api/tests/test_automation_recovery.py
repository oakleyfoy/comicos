from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import AutomationJob, AutomationWorkerExecution, AutomationWorkerLease
from test_automation_jobs import _create_job
from test_automation_workers import _register_worker
from test_inventory import auth_headers, register_and_login


def _create_retry_policy(client: TestClient, token: str, *, name: str, retry_mode: str = "EXPONENTIAL_BACKOFF", max_attempts: int = 3):
    return client.post(
        "/api/v1/ops/automation/retry-policies",
        headers=auth_headers(token),
        json={
            "policy_name": name,
            "retry_mode": retry_mode,
            "max_attempts": max_attempts,
            "base_delay_seconds": 30,
            "max_delay_seconds": 120,
        },
    )


def test_automation_recovery_schedules_retry_deterministically(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "recovery-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "recovery-owner@example.com")
    ops = register_and_login(client, "recovery-ops@example.com")
    created = _create_job(client, owner, queue_key="recovery-retry", job_key="retry-target", priority="HIGH")
    assert created.status_code == 201, created.text
    job_id = created.json()["data"]["id"]
    job = session.get(AutomationJob, int(job_id))
    assert job is not None
    job.job_status = "FAILED"
    job.current_attempt_count = 1
    job.max_attempts = 3
    session.add(job)
    session.commit()

    policy = _create_retry_policy(client, ops, name="recovery-policy")
    assert policy.status_code == 201, policy.text
    retry = client.post(
        f"/api/v1/ops/automation/jobs/{job_id}/retry",
        headers=auth_headers(ops),
        json={"retry_policy_id": policy.json()["data"]["id"], "metadata_json": {"cause": "test"}},
    )
    assert retry.status_code == 200, retry.text
    retry_data = retry.json()["data"]
    assert retry_data["recovery_type"] == "RETRY"
    assert retry_data["recovery_status"] == "COMPLETED"
    assert retry_data["retry_policy"]["retry_mode"] == "EXPONENTIAL_BACKOFF"
    assert retry_data["recovery_manifest_json"]["recovery_metadata"]["retry_delay_seconds"] == 60

    refreshed = session.get(AutomationJob, int(job_id))
    assert refreshed is not None
    assert refreshed.job_status == "AVAILABLE"

    owner_runs = client.get("/api/v1/automation/recovery/runs", headers=auth_headers(owner))
    assert owner_runs.status_code == 200, owner_runs.text
    assert owner_runs.json()["data"]["items"][0]["recovery_checksum"] == retry_data["recovery_checksum"]
    get_settings.cache_clear()


def test_automation_recovery_dead_letter_and_replay_recovery_preserve_lineage(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "recovery-ops-2@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "recovery-owner-2@example.com")
    ops = register_and_login(client, "recovery-ops-2@example.com")
    created = _create_job(client, owner, queue_key="recovery-dead", job_key="dead-target", priority="CRITICAL")
    assert created.status_code == 201, created.text
    job_id = created.json()["data"]["id"]
    job = session.get(AutomationJob, int(job_id))
    assert job is not None
    job.job_status = "FAILED"
    job.current_attempt_count = 3
    job.max_attempts = 3
    session.add(job)
    session.commit()

    policy = _create_retry_policy(client, ops, name="dead-letter-policy", max_attempts=3)
    assert policy.status_code == 201, policy.text
    dead_letter = client.post(
        f"/api/v1/ops/automation/jobs/{job_id}/retry",
        headers=auth_headers(ops),
        json={"retry_policy_id": policy.json()["data"]["id"]},
    )
    assert dead_letter.status_code == 200, dead_letter.text
    dead_data = dead_letter.json()["data"]
    assert dead_data["recovery_type"] == "DEAD_LETTER_TRANSFER"
    assert dead_data["dead_letter"]["dead_letter_status"] == "ACTIVE"

    replay = client.post(
        f"/api/v1/ops/automation/jobs/{job_id}/replay-recovery",
        headers=auth_headers(ops),
        json={"metadata_json": {"mode": "replay"}},
    )
    assert replay.status_code == 200, replay.text
    replay_data = replay.json()["data"]
    assert replay_data["recovery_type"] == "REPLAY_RECOVERY"
    assert replay_data["recovery_manifest_json"]["replay_references"]["replay_job_id"]

    owner_dead_letter = client.get("/api/v1/automation/dead-letter", headers=auth_headers(owner))
    assert owner_dead_letter.status_code == 200, owner_dead_letter.text
    assert owner_dead_letter.json()["data"]["items"][0]["dead_letter_status"] == "RESOLVED"
    get_settings.cache_clear()


def test_automation_recovery_recovers_stale_execution_and_enforces_owner_isolation(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "recovery-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "recovery-owner-3@example.com")
    peer = register_and_login(client, "recovery-peer-3@example.com")
    ops = register_and_login(client, "recovery-ops-3@example.com")
    created = _create_job(client, owner, queue_key="recovery-stale", job_key="stale-target", priority="HIGH")
    assert created.status_code == 201, created.text
    worker = _register_worker(client, ops, worker_identifier="recovery-worker", queue_keys=["recovery-stale"])
    assert worker.status_code == 201, worker.text
    worker_id = worker.json()["data"]["id"]
    lease = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/lease",
        headers=auth_headers(ops),
        json={"reservation_token": "recovery-lease", "lease_seconds": 30},
    )
    assert lease.status_code == 200, lease.text
    started = client.post(
        f"/api/v1/ops/automation/workers/{worker_id}/execution/start",
        headers=auth_headers(ops),
        json={"reservation_token": "recovery-lease"},
    )
    assert started.status_code == 200, started.text
    execution_id = started.json()["data"]["id"]

    lease_row = session.exec(select(AutomationWorkerLease).where(AutomationWorkerLease.reservation_token == "recovery-lease")).first()
    execution_row = session.get(AutomationWorkerExecution, int(execution_id))
    assert lease_row is not None
    assert execution_row is not None
    lease_row.lease_expires_at = lease_row.lease_expires_at - timedelta(minutes=5)
    session.add(lease_row)
    session.commit()

    recovered = client.post(
        f"/api/v1/ops/automation/executions/{execution_id}/recover",
        headers=auth_headers(ops),
        json={"metadata_json": {"reason": "stale-test"}},
    )
    assert recovered.status_code == 200, recovered.text
    recovered_data = recovered.json()["data"]
    assert recovered_data["recovery_type"] == "EXECUTION_RECOVERY"
    assert any(event["worker_execution_id"] == execution_id for event in recovered_data["failure_events"])

    session.refresh(execution_row)
    assert execution_row.execution_status == "ABANDONED"
    assert client.get(f"/api/v1/automation/recovery/runs/{recovered_data['id']}", headers=auth_headers(peer)).status_code == 404
    get_settings.cache_clear()
