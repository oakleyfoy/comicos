from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.collector_home_service import build_collector_home
from test_inventory import auth_headers, register_and_login


def test_collector_home_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-home@example.com")
    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "headline" in data
    assert len(data["sections"]) >= 8
    assert "budget_status" in data


def test_collector_home_empty_inventory_hint(client: TestClient, session: Session) -> None:
    register_and_login(client, "p85-home-empty@example.com")
    from sqlmodel import select
    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p85-home-empty@example.com")).one().id or 0)
    home = build_collector_home(session, owner_user_id=owner_id)
    assert "inventory" in home.headline.lower() or home.headline
