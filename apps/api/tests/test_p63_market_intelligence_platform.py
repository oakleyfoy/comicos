from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.services.market_intelligence_certification import certify_portfolio_performance
from test_p63_market_helpers import owner_id, seed_p63_owner
from test_inventory import register_and_login


def test_empty_owner_portfolio_not_ready(client: TestClient, session: Session) -> None:
    email = "p63-empty@example.com"
    register_and_login(client, email)
    oid = owner_id(session, email)
    cert = certify_portfolio_performance(session, owner_user_id=oid)
    assert cert["status"] == "NOT_READY"
    assert cert["certified"] is False


def test_owner_isolation(client: TestClient, session: Session) -> None:
    email_a = "p63-iso-a@example.com"
    email_b = "p63-iso-b@example.com"
    register_and_login(client, email_a)
    register_and_login(client, email_b)
    seed_p63_owner(client, session, email_a)
    token_b = register_and_login(client, email_b)
    headers = {"Authorization": f"Bearer {token_b}"}
    resp = client.get("/api/v1/market-intelligence/portfolio/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] == 0


def test_platform_cert_and_no_p62_mutation(client: TestClient, session: Session) -> None:
    email = "p63-platform@example.com"
    token = register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    before = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    headers = {"Authorization": f"Bearer {token}"}
    build = client.post("/api/v1/market-intelligence/platform/build", headers=headers)
    assert build.status_code == 200
    after = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    assert after == before
    cert = client.get("/api/v1/market-intelligence/platform/certification", headers=headers)
    assert cert.status_code == 200
    data = cert.json()["data"]
    assert "portfolio" in data
    assert data["portfolio"]["certified"] is True
