from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from test_inventory import auth_headers, register_and_login


def test_market_user_intelligence_api(client: TestClient) -> None:
    email = "market-user-api@example.com"
    token = register_and_login(client, email)

    refresh = client.post("/api/v1/market-user-intelligence/refresh", headers=auth_headers(token))
    dashboard = client.get("/api/v1/market-user-intelligence/dashboard", headers=auth_headers(token))
    market = client.get("/api/v1/market-user-intelligence/market-demand", headers=auth_headers(token))
    prefs = client.get("/api/v1/market-user-intelligence/user-preferences", headers=auth_headers(token))

    assert refresh.status_code == 200, refresh.text
    assert dashboard.status_code == 200, dashboard.text
    assert market.status_code == 200
    assert prefs.status_code == 200
    assert dashboard.json()["data"]["total_market_profiles"] >= 1

    create = client.post(
        "/api/v1/market-user-intelligence/user-preferences",
        headers=auth_headers(token),
        json={"preference_type": "FRANCHISE", "preference_label": "TMNT", "preference_score": 82},
    )
    assert create.status_code == 200, create.text
    profile_id = create.json()["data"]["preference"]["id"]

    disable = client.patch(
        f"/api/v1/market-user-intelligence/user-preferences/{profile_id}/disable",
        headers=auth_headers(token),
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["data"]["preference"]["status"] == "DISABLED"

    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        assert owner_id > 0
