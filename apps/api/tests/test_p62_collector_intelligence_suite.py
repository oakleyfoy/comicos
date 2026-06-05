from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline
from tests.test_buy_queue_intelligence import _owner_id, _seed_catalog, register_and_login


def test_collector_platform_pipeline_and_cert(client: TestClient, session: Session) -> None:
    email = "p62-suite@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    raw = run_collector_intelligence_pipeline(session, owner_user_id=owner_id)
    assert "buy_queue" in raw["steps"]
    headers = {"Authorization": f"Bearer {token}"}
    cert = client.get("/api/v1/recommendation-intelligence/platform/certification", headers=headers)
    assert cert.status_code == 200
    data = cert.json()["data"]
    assert "foc" in data
    assert "pull_forecast" in data
    assert "auto_watchlists" in data
