from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.models import AutomationWorkflowStep
from app.services.automation_scheduling import resolve_workflow_dependencies
from test_inventory import auth_headers, register_and_login


def test_automation_scheduling_creates_schedules_processes_due_runs_and_keeps_order(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "schedule-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "schedule-owner@example.com")
    ops = register_and_login(client, "schedule-ops@example.com")
    now = datetime.now(timezone.utc)
    late_payload = {
        "schedule_name": "Late maintenance",
        "schedule_type": "ONE_TIME",
        "next_run_at": (now - timedelta(minutes=1)).isoformat(),
        "workflow_key": "maintenance_schedule_workflow",
    }
    early_payload = {
        "schedule_name": "Early maintenance",
        "schedule_type": "ONE_TIME",
        "next_run_at": (now - timedelta(minutes=2)).isoformat(),
        "workflow_key": "maintenance_schedule_workflow",
    }
    late = client.post("/api/v1/automation/schedules", headers=auth_headers(owner), json=late_payload)
    early = client.post("/api/v1/automation/schedules", headers=auth_headers(owner), json=early_payload)
    duplicate = client.post("/api/v1/automation/schedules", headers=auth_headers(owner), json=early_payload)
    assert late.status_code == 201, late.text
    assert early.status_code == 201, early.text
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["data"]["schedule_checksum"] == early.json()["data"]["schedule_checksum"]

    processed = client.post("/api/v1/ops/automation/process-schedules", headers=auth_headers(ops))
    assert processed.status_code == 200, processed.text
    items = processed.json()["data"]["items"]
    assert [item["execution_manifest_json"]["schedule_snapshot"]["schedule_name"] for item in items] == [
        "Early maintenance",
        "Late maintenance",
    ]
    assert all(item["execution_status"] == "COMPLETED" for item in items)

    workflows = client.get("/api/v1/automation/workflows", headers=auth_headers(owner))
    assert workflows.status_code == 200, workflows.text
    workflow = workflows.json()["data"]["items"][0]
    direct_first = client.post(f"/api/v1/ops/automation/workflows/{workflow['id']}/execute", headers=auth_headers(ops))
    direct_second = client.post(f"/api/v1/ops/automation/workflows/{workflow['id']}/execute", headers=auth_headers(ops))
    assert direct_first.status_code == 200, direct_first.text
    assert direct_second.status_code == 200, direct_second.text
    assert direct_first.json()["data"]["execution_checksum"] == direct_second.json()["data"]["execution_checksum"]
    get_settings.cache_clear()


def test_automation_scheduling_deduplicates_triggers_and_surfaces_blocked_workflows(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "trigger-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "trigger-owner@example.com")
    ops = register_and_login(client, "trigger-ops@example.com")
    payload = {
        "trigger_type": "MANUAL_TRIGGER",
        "source_event_type": "manual-test",
        "trigger_payload_json": {"scan_image_id": 101},
        "workflow_key": "blocked_test_workflow",
    }
    first = client.post("/api/v1/automation/triggers", headers=auth_headers(owner), json=payload)
    second = client.post("/api/v1/automation/triggers", headers=auth_headers(owner), json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["trigger_checksum"] == second.json()["data"]["trigger_checksum"]

    processed = client.post("/api/v1/ops/automation/process-triggers", headers=auth_headers(ops))
    assert processed.status_code == 200, processed.text
    processed_items = processed.json()["data"]["items"]
    assert len(processed_items) == 1
    assert processed_items[0]["execution_status"] == "BLOCKED"

    blocked = client.get("/api/v1/ops/automation/workflows/blocked", headers=auth_headers(ops))
    issues = client.get("/api/v1/ops/automation/workflows/issues", headers=auth_headers(ops))
    assert blocked.status_code == 200, blocked.text
    assert issues.status_code == 200, issues.text
    assert blocked.json()["data"]["blocked_workflow_count"] >= 1
    assert any(item["issue_type"] == "BLOCKED_WORKFLOW_STEP" for item in issues.json()["data"]["items"])
    get_settings.cache_clear()


def test_automation_scheduling_enforces_owner_isolation_and_rejects_cycles(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "workflow-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "workflow-owner@example.com")
    peer = register_and_login(client, "workflow-peer@example.com")
    ops = register_and_login(client, "workflow-ops@example.com")
    trigger = client.post(
        "/api/v1/automation/triggers",
        headers=auth_headers(owner),
        json={
            "trigger_type": "SCAN_COMPLETED",
            "source_event_type": "scan-finished",
            "source_record_type": "scan_image",
            "source_record_id": 202,
            "source_checksum": "abc123",
            "trigger_payload_json": {"scan_image_id": 202},
        },
    )
    assert trigger.status_code == 201, trigger.text
    processed = client.post("/api/v1/ops/automation/process-triggers", headers=auth_headers(ops))
    assert processed.status_code == 200, processed.text

    owner_workflows = client.get("/api/v1/automation/workflows", headers=auth_headers(owner))
    assert owner_workflows.status_code == 200, owner_workflows.text
    workflow_id = owner_workflows.json()["data"]["items"][0]["id"]
    detail = client.get(f"/api/v1/automation/workflows/{workflow_id}", headers=auth_headers(owner))
    history = client.get(f"/api/v1/automation/workflows/{workflow_id}/history", headers=auth_headers(owner))
    executions = client.get(f"/api/v1/automation/workflows/{workflow_id}/executions", headers=auth_headers(owner))
    assert detail.status_code == 200, detail.text
    assert history.status_code == 200, history.text
    assert executions.status_code == 200, executions.text
    assert client.get(f"/api/v1/automation/workflows/{workflow_id}", headers=auth_headers(peer)).status_code == 404
    assert any(row["event_type"] == "TRIGGER_PROCESSED" for row in history.json()["data"]["items"])
    assert executions.json()["data"]["items"][0]["execution_manifest_json"]["generated_jobs"][0]["job_checksum"]

    step_a = AutomationWorkflowStep(id=1, workflow_id=1, step_rank=1, step_key="a", job_type="FUTURE_RESERVED", dependency_mode="OPTIONAL", required_success=True, metadata_json={"depends_on_step_key": "b"})
    step_b = AutomationWorkflowStep(id=2, workflow_id=1, step_rank=2, step_key="b", job_type="FUTURE_RESERVED", dependency_mode="OPTIONAL", required_success=True, metadata_json={"depends_on_step_key": "a"})
    with pytest.raises(HTTPException, match="Cyclic workflow dependency detected"):
        resolve_workflow_dependencies([step_a, step_b])
    get_settings.cache_clear()
