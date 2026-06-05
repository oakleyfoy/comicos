from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.models.collector_assistant import CollectorAssistantRun
from app.models.market_intelligence_platform import PortfolioPerformanceSnapshot
from app.services.collector_assistant_context_service import load_collector_assistant_context
from app.services.collector_assistant_orchestrator import run_collector_assistant_build
from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline
from app.services.market_intelligence_automation import run_market_intelligence_platform_build
from test_buy_queue_intelligence import _seed_catalog
from test_inventory import register_and_login
from test_p63_market_helpers import owner_id, seed_p63_owner


def seed_p64_upstream(client: TestClient, session: Session, email: str) -> int:
    oid = seed_p63_owner(client, session, email)
    _seed_catalog(session, oid)
    run_collector_intelligence_pipeline(session, owner_user_id=oid)
    run_market_intelligence_platform_build(session, owner_user_id=oid)
    return oid


def test_context_loads_when_upstream_present(client: TestClient, session: Session) -> None:
    email = "p64-ctx@example.com"
    register_and_login(client, email)
    oid = seed_p64_upstream(client, session, email)
    ctx = load_collector_assistant_context(session, owner_user_id=oid)
    assert ctx.ready is True
    assert ctx.fingerprint


def test_empty_owner_not_ready(client: TestClient, session: Session) -> None:
    email = "p64-empty@example.com"
    register_and_login(client, email)
    oid = owner_id(session, email)
    ctx = load_collector_assistant_context(session, owner_user_id=oid)
    assert ctx.ready is False
    run = run_collector_assistant_build(session, owner_user_id=oid, scope="full")
    assert run.status == "NOT_READY"


def test_lane_generation_and_api_read_only(client: TestClient, session: Session) -> None:
    email = "p64-lanes@example.com"
    token = register_and_login(client, email)
    oid = seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    bq_before = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    p63_before = session.exec(select(func.count()).select_from(PortfolioPerformanceSnapshot)).one()
    build = client.post("/api/v1/collector-assistant/platform/build", headers=headers)
    assert build.status_code == 200
    assert build.json()["data"]["status"] == "SUCCESS"
    bq_after = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    p63_after = session.exec(select(func.count()).select_from(PortfolioPerformanceSnapshot)).one()
    assert bq_after == bq_before
    assert p63_after == p63_before
    rec = client.get("/api/v1/collector-assistant/recommendations/latest", headers=headers)
    assert rec.status_code == 200
    assert rec.json()["data"]["total_items"] >= 1
    brief = client.get("/api/v1/collector-assistant/briefing/latest", headers=headers)
    assert brief.status_code == 200
    assert brief.json()["data"]["readiness_status"] == "SUCCESS"
    dash = client.get("/api/v1/collector-assistant/dashboard/latest", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["data"]["platform_ready"] is True
    runs = session.exec(select(func.count()).select_from(CollectorAssistantRun).where(CollectorAssistantRun.owner_user_id == oid)).one()
    assert runs >= 1


def test_recommendations_build_post(client: TestClient, session: Session) -> None:
    email = "p64-rec-build@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/collector-assistant/recommendations/build", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "SUCCESS"


def test_platform_certification_bundle(client: TestClient, session: Session) -> None:
    email = "p64-cert@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    cert = client.get("/api/v1/collector-assistant/platform/certification", headers=headers)
    assert cert.status_code == 200
    data = cert.json()["data"]
    assert data["non_mutation"]["certified"] is True
    assert data["platform_ready"] is True
