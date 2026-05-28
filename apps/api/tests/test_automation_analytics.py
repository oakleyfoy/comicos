from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    AutomationAlert,
    AutomationAnalyticsHistory,
    AutomationAnalyticsSnapshot,
    AutomationBatchRun,
    AutomationDeadLetterJob,
    AutomationJob,
    AutomationNotification,
    AutomationNotificationDelivery,
    AutomationQueue,
    AutomationRecoveryRun,
    AutomationWorker,
    AutomationWorkflow,
    AutomationWorkflowExecution,
    ScanReplayIssue,
    ScanReplayRun,
    User,
)
from test_inventory import auth_headers, register_and_login


def _owner_user_id(session: Session, email: str) -> int:
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None and user.id is not None
    return int(user.id)


def _seed_analytics_inputs(session: Session, *, owner_user_id: int, suffix: str) -> None:
    queue = AutomationQueue(
        queue_key=f"analytics-queue-{suffix}",
        queue_name=f"Analytics queue {suffix}",
        queue_category="OPS",
        queue_status="ACTIVE",
        deterministic_ordering_enabled=True,
        max_concurrency=2,
    )
    workflow = AutomationWorkflow(
        owner_user_id=owner_user_id,
        workflow_key=f"analytics-workflow-{suffix}",
        workflow_name=f"Analytics workflow {suffix}",
        workflow_status="ACTIVE",
        workflow_category="OPS",
    )
    session.add(queue)
    session.add(workflow)
    session.commit()
    session.refresh(queue)
    session.refresh(workflow)

    job = AutomationJob(
        owner_user_id=owner_user_id,
        queue_id=int(queue.id),
        job_key=f"analytics-job-{suffix}",
        job_type="ANALYTICS",
        job_status="FAILED",
        priority="HIGH",
        deterministic_rank=10,
        payload_snapshot_json={"suffix": suffix},
        payload_checksum=f"payload-{suffix}",
        job_checksum=f"job-{suffix}",
        current_attempt_count=1,
        max_attempts=2,
        replay_safe=True,
    )
    worker = AutomationWorker(
        worker_key=f"analytics-worker-{suffix}",
        worker_identifier=f"analytics-worker-id-{suffix}",
        worker_type="OPS",
        worker_status="ACTIVE",
        queue_scope_json={"queue_key": queue.queue_key},
        max_concurrency=1,
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    batch_run = AutomationBatchRun(
        owner_user_id=owner_user_id,
        batch_key=f"analytics-batch-{suffix}",
        batch_type="MAINTENANCE",
        batch_status="COMPLETED",
        source_scope="automation",
        total_item_count=3,
        completed_item_count=3,
        failed_item_count=0,
        batch_checksum=f"batch-{suffix}",
        manifest_json={"suffix": suffix},
    )
    notification = AutomationNotification(
        owner_user_id=owner_user_id,
        notification_key=f"analytics-notification-{suffix}",
        notification_type="OPS",
        notification_status="DELIVERED",
        source_event_type="ANALYTICS",
        source_record_type="automation_job",
        source_record_id=1,
        source_checksum=f"notification-source-{suffix}",
        notification_payload_json={"suffix": suffix},
        notification_checksum=f"notification-{suffix}",
        replay_safe=True,
    )
    replay_run = ScanReplayRun(
        owner_user_id=owner_user_id,
        replay_scope="automation",
        source_checksum=f"replay-source-{suffix}",
        replay_checksum=f"replay-{suffix}",
        replay_status="COMPLETED",
        engine_version="P41-09-v1",
        input_manifest_json={"suffix": suffix},
        output_manifest_json={"suffix": suffix},
        completed_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.add(worker)
    session.add(batch_run)
    session.add(notification)
    session.add(replay_run)
    session.commit()
    session.refresh(job)
    session.refresh(worker)
    session.refresh(notification)
    session.refresh(replay_run)

    session.add(
        AutomationNotificationDelivery(
            notification_id=int(notification.id),
            delivery_channel="email",
            delivery_status="DELIVERED",
            delivery_rank=10,
            destination_key=f"analytics-destination-{suffix}",
            attempted_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
            delivery_checksum=f"delivery-{suffix}",
            metadata_json={"suffix": suffix},
        )
    )
    session.add(
        AutomationDeadLetterJob(
            original_job_id=int(job.id),
            dead_letter_reason="deterministic test failure",
            dead_letter_status="OPEN",
            failure_count=1,
            source_checksum=f"dead-letter-source-{suffix}",
            dead_letter_checksum=f"dead-letter-{suffix}",
            metadata_json={"suffix": suffix},
        )
    )
    session.add(
        AutomationRecoveryRun(
            owner_user_id=owner_user_id,
            job_id=int(job.id),
            recovery_status="COMPLETED",
            recovery_type="RETRY",
            recovery_rank=1,
            recovery_checksum=f"recovery-{suffix}",
            recovery_manifest_json={"suffix": suffix},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        AutomationWorkflowExecution(
            workflow_id=int(workflow.id),
            execution_status="COMPLETED",
            execution_checksum=f"workflow-execution-{suffix}",
            execution_manifest_json={"suffix": suffix},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        AutomationAlert(
            alert_key=f"analytics-alert-{suffix}",
            alert_type="ANALYTICS",
            alert_severity="WARNING",
            alert_status="ACTIVE",
            source_notification_id=int(notification.id),
            escalation_level="L1",
            alert_checksum=f"alert-{suffix}",
            metadata_json={"suffix": suffix},
        )
    )
    session.add(
        ScanReplayIssue(
            owner_user_id=owner_user_id,
            replay_run_id=int(replay_run.id),
            issue_type="REPLAY_DRIFT",
            severity="WARNING",
            issue_message="Deterministic replay drift warning.",
            issue_checksum=f"replay-issue-{suffix}",
            metadata_json={"suffix": suffix},
        )
    )
    session.commit()


def test_analytics_snapshot_is_deterministic_and_ordered(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "analytics-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "analytics-owner@example.com")
    ops = register_and_login(client, "analytics-ops@example.com")
    owner_user_id = _owner_user_id(session, "analytics-owner@example.com")
    _seed_analytics_inputs(session, owner_user_id=owner_user_id, suffix="primary")

    first = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "analytics_type": "SYSTEM_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-snapshot-001",
            "metadata_json": {"source": "pytest"},
        },
    )
    repeat = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "analytics_type": "SYSTEM_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-snapshot-001",
            "metadata_json": {"source": "pytest"},
        },
    )
    assert first.status_code == 201, first.text
    assert repeat.status_code == 200, repeat.text
    assert first.json()["data"]["id"] == repeat.json()["data"]["id"]
    assert first.json()["data"]["snapshot_checksum"] == repeat.json()["data"]["snapshot_checksum"]

    snapshot_id = first.json()["data"]["id"]
    metrics = client.get(f"/api/v1/automation/analytics/metrics?snapshot_id={snapshot_id}&limit=50", headers=auth_headers(owner))
    trends = client.get(f"/api/v1/automation/analytics/trends?snapshot_id={snapshot_id}&limit=50", headers=auth_headers(owner))
    comparisons = client.get(f"/api/v1/automation/analytics/comparisons?snapshot_id={snapshot_id}&limit=50", headers=auth_headers(owner))
    issues = client.get(f"/api/v1/automation/analytics/issues?snapshot_id={snapshot_id}&limit=50", headers=auth_headers(owner))

    assert metrics.status_code == 200, metrics.text
    metric_rows = metrics.json()["data"]["items"]
    assert [(row["metric_category"], row["metric_rank"], row["metric_key"]) for row in metric_rows] == sorted(
        (row["metric_category"], row["metric_rank"], row["metric_key"]) for row in metric_rows
    )

    assert trends.status_code == 200, trends.text
    trend_rows = trends.json()["data"]["items"]
    assert [(row["trend_type"], row["historical_window"], row["trend_key"]) for row in trend_rows] == sorted(
        (row["trend_type"], row["historical_window"], row["trend_key"]) for row in trend_rows
    )

    assert comparisons.status_code == 200, comparisons.text
    comparison_rows = comparisons.json()["data"]["items"]
    assert [(row["comparison_type"], row["comparison_key"]) for row in comparison_rows] == sorted(
        (row["comparison_type"], row["comparison_key"]) for row in comparison_rows
    )

    assert issues.status_code == 200, issues.text
    issue_types = {row["issue_type"] for row in issues.json()["data"]["items"]}
    assert "REPLAY_ANALYTICS_DRIFT" in issue_types

    history_count = session.exec(select(AutomationAnalyticsHistory).where(AutomationAnalyticsHistory.snapshot_id == snapshot_id)).all()
    assert len(history_count) >= 1
    get_settings.cache_clear()


def test_analytics_history_is_append_only_and_baselines_are_stable(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "analytics-ops-2@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "analytics-owner-2@example.com")
    ops = register_and_login(client, "analytics-ops-2@example.com")
    owner_user_id = _owner_user_id(session, "analytics-owner-2@example.com")
    _seed_analytics_inputs(session, owner_user_id=owner_user_id, suffix="alpha")

    first = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "analytics_type": "QUEUE_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-snapshot-a",
            "metadata_json": {"source": "pytest"},
        },
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["id"]

    second = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "analytics_type": "QUEUE_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-snapshot-b",
            "metadata_json": {"source": "pytest"},
        },
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["data"]["id"]

    comparisons = client.get(f"/api/v1/automation/analytics/comparisons?snapshot_id={second_id}&limit=50", headers=auth_headers(owner))
    assert comparisons.status_code == 200, comparisons.text
    comparison_rows = comparisons.json()["data"]["items"]
    assert comparison_rows and all(row["baseline_snapshot_id"] == first_id for row in comparison_rows)

    history_rows = session.exec(select(AutomationAnalyticsHistory).where(AutomationAnalyticsHistory.snapshot_id.in_([first_id, second_id]))).all()
    assert len(history_rows) >= 2
    assert {row.event_type for row in history_rows} == {"ANALYTICS_SNAPSHOT_CREATED"}
    get_settings.cache_clear()


def test_analytics_owner_isolation_and_system_intelligence(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "analytics-ops-3@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "analytics-owner-3@example.com")
    other_owner = register_and_login(client, "analytics-owner-3b@example.com")
    ops = register_and_login(client, "analytics-ops-3@example.com")
    owner_user_id = _owner_user_id(session, "analytics-owner-3@example.com")
    other_owner_user_id = _owner_user_id(session, "analytics-owner-3b@example.com")
    _seed_analytics_inputs(session, owner_user_id=owner_user_id, suffix="owner-a")
    _seed_analytics_inputs(session, owner_user_id=other_owner_user_id, suffix="owner-b")

    owner_snapshot = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": owner_user_id,
            "analytics_type": "WORKFLOW_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-owner-a",
            "metadata_json": {"source": "pytest"},
        },
    )
    other_snapshot = client.post(
        "/api/v1/ops/automation/analytics/create",
        headers=auth_headers(ops),
        json={
            "owner_user_id": other_owner_user_id,
            "analytics_type": "WORKFLOW_ANALYTICS",
            "analytics_scope": "automation",
            "replay_key": "analytics-owner-b",
            "metadata_json": {"source": "pytest"},
        },
    )
    assert owner_snapshot.status_code == 201, owner_snapshot.text
    assert other_snapshot.status_code == 201, other_snapshot.text

    owner_list = client.get("/api/v1/automation/analytics/snapshots?limit=50", headers=auth_headers(owner))
    assert owner_list.status_code == 200, owner_list.text
    owner_ids = {row["id"] for row in owner_list.json()["data"]["items"]}
    assert other_snapshot.json()["data"]["id"] not in owner_ids

    forbidden = client.get(
        f"/api/v1/automation/analytics/snapshots/{other_snapshot.json()['data']['id']}",
        headers=auth_headers(owner),
    )
    assert forbidden.status_code == 404, forbidden.text

    system_intelligence = client.get(
        "/api/v1/ops/automation/analytics/system-intelligence",
        headers=auth_headers(ops),
        params={"owner_user_id": owner_user_id},
    )
    assert system_intelligence.status_code == 200, system_intelligence.text
    assert system_intelligence.json()["data"]["latest_snapshot_id"] == owner_snapshot.json()["data"]["id"]

    drift = client.get("/api/v1/ops/automation/analytics/drift?limit=50", headers=auth_headers(ops))
    assert drift.status_code == 200, drift.text
    assert drift.json()["data"]["replay_drift_count"] >= 1
    get_settings.cache_clear()
