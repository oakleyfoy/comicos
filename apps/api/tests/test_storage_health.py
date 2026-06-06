from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.storage_health_score import compute_storage_health_score
from app.services.storage_analytics_service import build_health_read, build_analytics_dashboard
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_health_score_and_dashboard(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-health@example.com")
    owner_id = _owner_id(session, "p79-health@example.com")
    score, status, _ = compute_storage_health_score(
        total_copies=10,
        assigned_count=8,
        audit_accuracy_pct=95.0,
        over_capacity_boxes=0,
        high_value_unassigned=0,
        duplicate_assignments=0,
        missing_books=0,
    )
    assert 0 <= score <= 100
    assert status in {"HEALTHY", "WATCH", "AT_RISK"}
    health = build_health_read(session, owner_user_id=owner_id)
    assert health.health_score >= 0
    dash = build_analytics_dashboard(session, owner_user_id=owner_id)
    assert dash.snapshot_id > 0
    resp = client.get("/api/v1/storage/analytics-dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "health" in body
    assert "utilization" in body
