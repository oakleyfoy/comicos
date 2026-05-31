from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.platform_health import check_platform_health
from app.services.recovery_recommendations import generate_recovery_recommendations
from app.services.reliability_monitor import run_reliability_monitor
from test_inventory import auth_headers, register_and_login


def test_operations_reliability_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "ops-rel-owner@example.com"
    outsider_email = "ops-rel-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        check_platform_health(session, owner_user_id=owner_user_id)
        run_reliability_monitor(session, owner_user_id=owner_user_id)
        generate_recovery_recommendations(session, owner_user_id=owner_user_id)

    health = client.get("/api/v1/operations-reliability/health", headers=auth_headers(owner_token))
    issues = client.get("/api/v1/operations-reliability/issues", headers=auth_headers(owner_token))
    jobs = client.get("/api/v1/operations-reliability/jobs", headers=auth_headers(owner_token))
    queues = client.get("/api/v1/operations-reliability/queues", headers=auth_headers(owner_token))
    recommendations = client.get("/api/v1/operations-reliability/recommendations", headers=auth_headers(owner_token))
    run_health = client.post("/api/v1/operations-reliability/run/health", headers=auth_headers(owner_token))
    run_reliability = client.post("/api/v1/operations-reliability/run/reliability", headers=auth_headers(owner_token))
    run_recommendations = client.post("/api/v1/operations-reliability/run/recommendations", headers=auth_headers(owner_token))
    outsider_health = client.get("/api/v1/operations-reliability/health", headers=auth_headers(outsider_token))

    assert health.status_code == 200, health.text
    assert issues.status_code == 200, issues.text
    assert jobs.status_code == 200, jobs.text
    assert queues.status_code == 200, queues.text
    assert recommendations.status_code == 200, recommendations.text
    assert run_health.status_code == 200, run_health.text
    assert run_reliability.status_code == 200, run_reliability.text
    assert run_recommendations.status_code == 200, run_recommendations.text
    assert len(health.json()["data"]["health_checks"]) >= 1
    assert health.json()["data"]["summary"]["readiness_score"] >= 0
    assert outsider_health.json()["data"]["health_checks"] == []
