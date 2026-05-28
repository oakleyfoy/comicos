from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    AutomationJob,
    AutomationQueue,
    AutomationRuleHistory,
    AutomationRuleVersion,
    AutomationWorkflow,
    User,
)
from test_inventory import auth_headers, register_and_login


def _owner_user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None and user.id is not None
    return int(user.id)


def test_automation_rules_evaluation_is_deterministic_and_actions_are_ordered(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "rules-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "rules-owner@example.com")
    ops = register_and_login(client, "rules-ops@example.com")
    owner_user_id = _owner_user_id(session, "rules-owner@example.com")

    queue = AutomationQueue(queue_key="rules-primary", queue_name="Rules primary", queue_category="OPS", queue_status="ACTIVE", max_concurrency=2)
    workflow = AutomationWorkflow(
        owner_user_id=owner_user_id,
        workflow_key="rules-review-workflow",
        workflow_name="Rules review workflow",
        workflow_status="ACTIVE",
        workflow_category="OPS",
    )
    session.add(queue)
    session.add(workflow)
    session.commit()

    created = client.post(
        "/api/v1/ops/automation/rules/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "rule_name": "Queue overload responder",
            "rule_category": "QUEUE",
            "condition_expression": "queue_depth > 100 and dead_letter_count >= 1",
            "action_definition_json": [
                {"action_rank": 30, "action_type": "CREATE_NOTIFICATION", "target_scope": "ops"},
                {"action_rank": 10, "action_type": "PAUSE_QUEUE", "target_scope": "rules-primary"},
                {"action_rank": 20, "action_type": "EXECUTE_WORKFLOW", "target_scope": "rules-review-workflow"},
            ],
            "evaluation_scope": "system",
            "replay_key": "rules-create-001",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    first_eval = client.post(
        f"/api/v1/ops/automation/rules/{rule_id}/evaluate",
        headers=auth_headers(ops),
        json={
            "evaluation_type": "QUEUE_RULE",
            "evaluation_scope": "system",
            "evaluation_input_json": {"queue_depth": 101, "dead_letter_count": 2},
            "evaluation_rank": 10,
            "replay_key": "rules-eval-001",
        },
    )
    second_eval = client.post(
        f"/api/v1/ops/automation/rules/{rule_id}/evaluate",
        headers=auth_headers(ops),
        json={
            "evaluation_type": "QUEUE_RULE",
            "evaluation_scope": "system",
            "evaluation_input_json": {"queue_depth": 101, "dead_letter_count": 2},
            "evaluation_rank": 10,
            "replay_key": "rules-eval-001",
        },
    )
    assert first_eval.status_code == 201, first_eval.text
    assert second_eval.status_code == 200, second_eval.text
    assert first_eval.json()["data"]["id"] == second_eval.json()["data"]["id"]
    assert first_eval.json()["data"]["evaluation_checksum"] == second_eval.json()["data"]["evaluation_checksum"]

    owner_actions = client.get(f"/api/v1/automation/rules/{rule_id}/actions", headers=auth_headers(owner), params={"limit": 50})
    assert owner_actions.status_code == 200, owner_actions.text
    action_rows = owner_actions.json()["data"]["items"]
    ordering = [(row["action_rank"], row["action_type"]) for row in action_rows]
    assert ordering == [(10, "PAUSE_QUEUE"), (20, "EXECUTE_WORKFLOW"), (30, "CREATE_NOTIFICATION")]

    session.expire_all()
    paused_queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == "rules-primary")).first()
    assert paused_queue is not None
    assert paused_queue.queue_status == "PAUSED"
    get_settings.cache_clear()


def test_automation_rules_versions_are_immutable_and_invalid_expressions_fail(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "rules-ops-2@example.com")
    get_settings.cache_clear()

    ops = register_and_login(client, "rules-ops-2@example.com")
    ops_user_id = _owner_user_id(session, "rules-ops-2@example.com")
    created = client.post(
        "/api/v1/ops/automation/rules/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": ops_user_id,
            "rule_name": "Replay warning responder",
            "rule_category": "REPLAY",
            "condition_expression": "replay_warning_count > 0",
            "action_definition_json": [{"action_type": "REPLAY_VERIFY", "target_scope": "scan-replay"}],
            "evaluation_scope": "system",
            "replay_key": "rules-create-002",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    version = client.post(
        f"/api/v1/ops/automation/rules/{rule_id}/version",
        headers=auth_headers(ops),
        json={
            "version_status": "ACTIVE",
            "condition_expression": "replay_warning_count >= 2",
            "action_definition_json": [{"action_type": "REPLAY_VERIFY", "target_scope": "scan-replay", "action_rank": 10}],
            "evaluation_scope": "system",
            "replay_key": "rules-version-002",
        },
    )
    assert version.status_code == 201, version.text

    versions = client.get(f"/api/v1/automation/rules/{rule_id}/versions", headers=auth_headers(ops), params={"limit": 50})
    assert versions.status_code == 200, versions.text
    version_rows = versions.json()["data"]["items"]
    assert [row["version_number"] for row in version_rows] == [1, 2]
    assert version_rows[0]["version_checksum"] != version_rows[1]["version_checksum"]
    assert len(session.exec(select(AutomationRuleVersion).where(AutomationRuleVersion.rule_id == rule_id)).all()) == 2

    invalid = client.post(
        "/api/v1/ops/automation/rules/create",
        headers=auth_headers(ops),
        json={
            "rule_name": "Bad expression",
            "rule_category": "OPS",
            "condition_expression": "queue_depth + 1",
            "action_definition_json": [{"action_type": "REPLAY_VERIFY", "target_scope": "scan-replay"}],
            "evaluation_scope": "system",
            "replay_key": "rules-bad-expression",
        },
    )
    assert invalid.status_code == 422
    get_settings.cache_clear()


def test_automation_rules_system_evaluation_history_and_owner_isolation(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "rules-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "rules-owner-3@example.com")
    peer = register_and_login(client, "rules-peer-3@example.com")
    ops = register_and_login(client, "rules-ops-3@example.com")
    owner_user_id = _owner_user_id(session, "rules-owner-3@example.com")

    queue = AutomationQueue(queue_key="rules-system", queue_name="Rules system", queue_category="OPS", queue_status="ACTIVE", max_concurrency=1)
    session.add(queue)
    session.flush()
    session.add(
        AutomationJob(
            owner_user_id=owner_user_id,
            queue_id=int(queue.id or 0),
            job_key="rules-system-job",
            job_type="SYSTEM_CHECK",
            job_status="QUEUED",
            priority="NORMAL",
            deterministic_rank=10,
            payload_snapshot_json={"source": "test"},
            payload_checksum="rules-system-job-payload",
            replay_safe=True,
            job_checksum="rules-system-job-checksum",
            metadata_json={},
        )
    )
    session.commit()

    created = client.post(
        "/api/v1/ops/automation/rules/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "rule_name": "System queue rule",
            "rule_category": "QUEUE",
            "condition_expression": "queue_depth >= 1",
            "action_definition_json": [{"action_type": "REPLAY_VERIFY", "target_scope": "scan-replay"}],
            "evaluation_scope": "system",
            "replay_key": "rules-create-003",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    system_eval = client.post(
        "/api/v1/ops/automation/rules/evaluate-system",
        headers=auth_headers(ops),
        json={"owner_user_id": owner_user_id, "evaluation_scope": "system", "replay_key": "rules-system-eval-001"},
    )
    assert system_eval.status_code == 200, system_eval.text
    assert len(system_eval.json()["data"]["items"]) >= 1

    assert client.get(f"/api/v1/automation/rules/{rule_id}", headers=auth_headers(owner)).status_code == 200
    assert client.get(f"/api/v1/automation/rules/{rule_id}", headers=auth_headers(peer)).status_code == 404

    failures = client.get("/api/v1/ops/automation/rules/failures", headers=auth_headers(ops))
    drift = client.get("/api/v1/ops/automation/rules/drift", headers=auth_headers(ops))
    assert failures.status_code == 200, failures.text
    assert drift.status_code == 200, drift.text
    assert len(session.exec(select(AutomationRuleHistory)).all()) >= 3
    get_settings.cache_clear()
