from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.operations_reliability import JobHealthMetric, QueueHealthMetric, ReliabilityIssue
from app.services.platform_health import check_platform_health
from app.services.reliability_monitor import run_reliability_monitor
from test_inventory import register_and_login


def test_run_reliability_monitor_creates_metrics_and_issues_without_repair(client: TestClient) -> None:
    register_and_login(client, "reliability-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "reliability-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)
        check_platform_health(session, owner_user_id=owner_user_id)
        issue_before = len(session.exec(select(ReliabilityIssue)).all())
        result = run_reliability_monitor(session, owner_user_id=owner_user_id)
        issue_after = len(session.exec(select(ReliabilityIssue)).all())
        job_rows = session.exec(select(JobHealthMetric)).all()
        queue_rows = session.exec(select(QueueHealthMetric)).all()

    assert "job_metrics" in result
    assert "queue_metrics" in result
    assert len(job_rows) >= 1
    assert len(queue_rows) >= 1
    assert issue_after >= issue_before
