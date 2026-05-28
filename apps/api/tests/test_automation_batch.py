from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import User
from test_inventory import auth_headers, register_and_login


def test_automation_batch_partitioning_and_checksums_are_deterministic(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "batch-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "batch-owner@example.com")
    ops = register_and_login(client, "batch-ops@example.com")
    owner_user = session.exec(select(User).where(User.email == "batch-owner@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    payload = {
        "owner_user_id": int(owner_user.id),
        "batch_type": "REPLAY_SWEEP",
        "source_scope": "scan-replay",
        "item_ids": [9, 2, 5, 1, 7, 3],
        "chunk_size": 2,
        "metadata_json": {"deterministic_rank": [1, 2, 3]},
    }
    first = client.post("/api/v1/ops/automation/batch/create", headers=auth_headers(ops), json=payload)
    second = client.post("/api/v1/ops/automation/batch/create", headers=auth_headers(ops), json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["batch_checksum"] == second_data["batch_checksum"]

    chunks = client.get(f"/api/v1/automation/batch/runs/{first_data['id']}/chunks", headers=auth_headers(owner))
    assert chunks.status_code == 200, chunks.text
    chunk_items = chunks.json()["data"]["items"]
    assert [(row["item_start"], row["item_end"]) for row in chunk_items] == [(1, 2), (3, 5), (7, 9)]
    assert len({row["chunk_checksum"] for row in chunk_items}) == 3

    detail = client.get(f"/api/v1/automation/batch/runs/{first_data['id']}", headers=auth_headers(owner))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["batch_status"] == "QUEUED"
    get_settings.cache_clear()


def test_automation_batch_execution_and_maintenance_audits_surface_warnings(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "batch-ops-2@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "batch-owner-2@example.com")
    ops = register_and_login(client, "batch-ops-2@example.com")
    owner_user = session.exec(select(User).where(User.email == "batch-owner-2@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    created = client.post(
        "/api/v1/ops/automation/batch/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": int(owner_user.id),
            "batch_type": "INTEGRITY_AUDIT",
            "source_scope": "batch-integrity",
            "item_ids": [1, 2, 3, 4],
            "chunk_size": 2,
            "metadata_json": {"orphan_artifact_paths": ["missing/a.json"], "force_failed_chunk_ranks": [2]},
        },
    )
    assert created.status_code == 201, created.text
    batch_id = created.json()["data"]["id"]

    executed = client.post(f"/api/v1/ops/automation/batch/{batch_id}/execute", headers=auth_headers(ops))
    assert executed.status_code == 200, executed.text
    data = executed.json()["data"]
    assert data["batch_status"] == "PARTIALLY_COMPLETED"
    assert data["failed_item_count"] == 2
    artifact_types = {row["artifact_type"] for row in data["artifacts"]}
    assert {"BATCH_REPORT", "CHUNK_EXPORT", "BATCH_MANIFEST", "BATCH_DEBUG_PREVIEW"}.issubset(artifact_types)

    maintenance = client.get("/api/v1/automation/maintenance/jobs", headers=auth_headers(owner))
    issues = client.get("/api/v1/automation/batch/issues", headers=auth_headers(owner))
    assert maintenance.status_code == 200, maintenance.text
    assert issues.status_code == 200, issues.text
    assert maintenance.json()["data"]["items"][0]["maintenance_type"] == "CHECKSUM_AUDIT"
    issue_types = {row["issue_type"] for row in issues.json()["data"]["items"]}
    assert "BATCH_EXECUTION_FAILURE" in issue_types or "ORPHAN_ARTIFACT_DETECTED" in issue_types
    get_settings.cache_clear()


def test_automation_batch_owner_isolation_and_ops_audit_routes(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "batch-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "batch-owner-3@example.com")
    peer = register_and_login(client, "batch-peer-3@example.com")
    ops = register_and_login(client, "batch-ops-3@example.com")
    owner_user = session.exec(select(User).where(User.email == "batch-owner-3@example.com")).first()
    assert owner_user is not None and owner_user.id is not None
    created = client.post(
        "/api/v1/ops/automation/batch/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": int(owner_user.id),
            "batch_type": "STORAGE_AUDIT",
            "source_scope": "storage-scope",
            "item_ids": [11, 12, 13],
            "chunk_size": 2,
        },
    )
    assert created.status_code == 201, created.text
    batch_id = created.json()["data"]["id"]
    maintenance = client.post(
        "/api/v1/ops/automation/maintenance/run",
        headers=auth_headers(ops),
        json={
            "owner_user_id": int(owner_user.id),
            "maintenance_type": "STORAGE_AUDIT",
            "maintenance_scope": "storage-scope",
            "metadata_json": {"orphan_artifact_paths": ["orphan/file.json"]},
        },
    )
    assert maintenance.status_code == 200, maintenance.text

    assert client.get(f"/api/v1/automation/batch/runs/{batch_id}", headers=auth_headers(peer)).status_code == 404
    storage = client.get("/api/v1/ops/automation/storage-audit", headers=auth_headers(ops))
    integrity = client.get("/api/v1/ops/automation/integrity-audit", headers=auth_headers(ops))
    failed = client.get("/api/v1/ops/automation/batch/failed", headers=auth_headers(ops))
    assert storage.status_code == 200, storage.text
    assert integrity.status_code == 200, integrity.text
    assert failed.status_code == 200, failed.text
    assert storage.json()["data"]["items"][0]["maintenance_type"] == "STORAGE_AUDIT"
    get_settings.cache_clear()
