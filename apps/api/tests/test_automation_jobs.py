from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.models import AutomationJob
from app.services.automation_jobs import (
    create_job_dependency,
    mark_automation_job_failed,
    release_automation_job_reservation,
    reserve_automation_job,
    transition_automation_job_status,
)
from test_inventory import auth_headers, register_and_login


def _create_job(
    client: TestClient,
    token: str,
    *,
    queue_key: str = "replay-jobs",
    queue_category: str = "REPLAY",
    job_key: str,
    job_type: str = "REPLAY_RUN",
    priority: str = "NORMAL",
    payload_snapshot_json: dict | None = None,
):
    return client.post(
        "/api/v1/automation/jobs",
        headers=auth_headers(token),
        json={
            "queue_key": queue_key,
            "queue_category": queue_category,
            "job_key": job_key,
            "job_type": job_type,
            "priority": priority,
            "payload_snapshot_json": payload_snapshot_json or {"job_key": job_key, "priority": priority},
        },
    )


def test_automation_jobs_are_deterministic_and_preserve_payload_artifacts(
    client: TestClient,
) -> None:
    token = register_and_login(client, "automation-jobs-det@example.com")

    first = _create_job(
        client,
        token,
        queue_key="scan-pipeline",
        queue_category="SCAN_PIPELINE",
        job_key="scan-101",
        job_type="SCAN_PIPELINE_RUN",
        payload_snapshot_json={"scan_image_id": 101, "stages": ["ingestion", "feed"]},
    )
    second = _create_job(
        client,
        token,
        queue_key="scan-pipeline",
        queue_category="SCAN_PIPELINE",
        job_key="scan-101",
        job_type="SCAN_PIPELINE_RUN",
        payload_snapshot_json={"scan_image_id": 101, "stages": ["ingestion", "feed"]},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text

    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["job_checksum"] == second_data["job_checksum"]
    assert first_data["payload_checksum"] == second_data["payload_checksum"]
    artifact_types = {row["artifact_type"] for row in first_data["artifacts"]}
    assert artifact_types == {"JOB_PAYLOAD_SNAPSHOT", "JOB_MANIFEST", "JOB_DEBUG_PREVIEW"}

    payload_artifact = next(row for row in first_data["artifacts"] if row["artifact_type"] == "JOB_PAYLOAD_SNAPSHOT")
    artifact_detail = client.get(
        f"/api/v1/automation/jobs/{first_data['id']}/artifacts/{payload_artifact['id']}",
        headers=auth_headers(token),
    )
    assert artifact_detail.status_code == 200, artifact_detail.text
    assert '"scan_image_id":101' in (artifact_detail.json()["data"]["text_preview"] or "")


def test_automation_jobs_order_reservations_and_reject_invalid_transitions(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "automation-jobs-order@example.com")
    low = _create_job(client, token, queue_key="worker-queue", job_key="low", priority="LOW")
    critical = _create_job(client, token, queue_key="worker-queue", job_key="critical", priority="CRITICAL")
    high = _create_job(client, token, queue_key="worker-queue", job_key="high", priority="HIGH")
    assert low.status_code == 201, low.text
    assert critical.status_code == 201, critical.text
    assert high.status_code == 201, high.text

    listing = client.get("/api/v1/automation/jobs?queue_key=worker-queue&limit=10&offset=0", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    listed_keys = [row["job_key"] for row in listing.json()["data"]["items"]]
    assert listed_keys[:3] == ["critical", "high", "low"]

    reserved = reserve_automation_job(session, queue_key="worker-queue", reservation_token="worker-a")
    assert reserved is not None
    assert reserved.job_key == "critical"
    assert reserve_automation_job(session, queue_key="worker-queue", reservation_token="worker-b").job_key == "high"
    released = release_automation_job_reservation(session, job_id=int(reserved.id), reservation_token="worker-a")
    assert released.job_status == "AVAILABLE"

    job = session.get(AutomationJob, int(released.id))
    assert job is not None
    with pytest.raises(ValueError):
        transition_automation_job_status(
            session,
            job=job,
            to_status="COMPLETED",
            event_type="INVALID_TEST",
            event_message="invalid",
            metadata_json={},
        )

    history = client.get(f"/api/v1/automation/jobs/{released.id}/history", headers=auth_headers(token))
    assert history.status_code == 200, history.text
    history_types = [row["event_type"] for row in history.json()["data"]["items"]]
    assert history_types[:4] == ["JOB_CREATED", "STATUS_TRANSITION", "JOB_RESERVED", "RESERVATION_RELEASED"]


def test_automation_jobs_dependency_cycle_isolation_and_ops_routes(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "automation-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "automation-owner@example.com")
    peer = register_and_login(client, "automation-peer@example.com")
    ops = register_and_login(client, "automation-ops@example.com")

    first = _create_job(client, owner, queue_key="replay-jobs", job_key="replay-1", priority="NORMAL")
    second = _create_job(client, owner, queue_key="replay-jobs", job_key="replay-2", priority="HIGH")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]

    dependency = create_job_dependency(session, job_id=first_id, depends_on_job_id=second_id)
    assert dependency.dependency_status == "BLOCKING"
    with pytest.raises(Exception):
        create_job_dependency(session, job_id=second_id, depends_on_job_id=first_id)

    reserved = reserve_automation_job(session, queue_key="replay-jobs", reservation_token="ops-worker")
    assert reserved is not None
    failed = mark_automation_job_failed(session, job_id=int(reserved.id), reservation_token="ops-worker", failure_reason="deterministic failure")
    assert failed.job_status == "FAILED"

    owner_detail = client.get(f"/api/v1/automation/jobs/{first_id}", headers=auth_headers(owner))
    assert owner_detail.status_code == 200, owner_detail.text
    assert client.get(f"/api/v1/automation/jobs/{first_id}", headers=auth_headers(peer)).status_code == 404
    owner_artifact = owner_detail.json()["data"]["artifacts"][0]
    assert (
        client.get(
            f"/api/v1/automation/jobs/{first_id}/artifacts/{owner_artifact['id']}",
            headers=auth_headers(peer),
        ).status_code
        == 404
    )

    owner_jobs = client.get("/api/v1/automation/jobs?limit=10&offset=0", headers=auth_headers(owner))
    peer_jobs = client.get("/api/v1/automation/jobs?limit=10&offset=0", headers=auth_headers(peer))
    assert owner_jobs.status_code == 200, owner_jobs.text
    assert peer_jobs.status_code == 200, peer_jobs.text
    assert owner_jobs.json()["data"]["pagination"]["total_count"] == 2
    assert peer_jobs.json()["data"]["pagination"]["total_count"] == 0

    ops_queues = client.get("/api/v1/ops/automation/queues", headers=auth_headers(ops))
    ops_jobs = client.get("/api/v1/ops/automation/jobs", headers=auth_headers(ops))
    ops_failed = client.get("/api/v1/ops/automation/jobs/failed", headers=auth_headers(ops))
    ops_dead = client.get("/api/v1/ops/automation/jobs/dead-letter", headers=auth_headers(ops))
    ops_issues = client.get("/api/v1/ops/automation/issues", headers=auth_headers(ops))
    ops_health = client.get("/api/v1/ops/automation/queue-health", headers=auth_headers(ops))
    assert ops_queues.status_code == 200, ops_queues.text
    assert ops_jobs.status_code == 200, ops_jobs.text
    assert ops_failed.status_code == 200, ops_failed.text
    assert ops_dead.status_code == 200, ops_dead.text
    assert ops_issues.status_code == 200, ops_issues.text
    assert ops_health.status_code == 200, ops_health.text
    assert any(int(row["id"]) == int(failed.id) for row in ops_failed.json()["data"]["items"])
    assert client.post("/api/v1/ops/automation/jobs", headers=auth_headers(ops), json={}).status_code == 405
    get_settings.cache_clear()
