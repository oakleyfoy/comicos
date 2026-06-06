from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.p77_personalization_engine import load_personalization_context, personalize_score
from sqlmodel import Session
from test_inventory import auth_headers, register_and_login


def test_personalize_score_publisher_and_budget(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p77-pers@example.com")
    from sqlmodel import select

    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p77-pers@example.com")).one().id or 0)

    client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={
            "publishers": [{"interest_type": "PUBLISHER", "label": "DC", "priority_rank": 1}],
            "characters": [{"interest_type": "CHARACTER", "label": "Batman", "priority_rank": 1}],
        },
    )
    client.put(
        "/api/v1/collector-profile/budget",
        headers=auth_headers(token),
        json={"monthly_budget": 100, "budget_period": "MONTHLY"},
    )

    ctx = load_personalization_context(session, owner_user_id=owner_id)
    personalized, adj, _, _, _, reasons = personalize_score(
        ctx,
        global_score=92.0,
        publisher="DC",
        series_name="Batman",
        title="Batman #1",
        owned_copies=4,
        estimated_price=20.0,
    )
    assert adj != 0.0
    assert personalized != 92.0
    assert any("Batman" in r or "DC" in r for r in reasons)


def test_personalized_recommendations_api(client: TestClient) -> None:
    token = register_and_login(client, "p77-recs@example.com")
    client.put(
        "/api/v1/collector-profile/budget",
        headers=auth_headers(token),
        json={"monthly_budget": 500, "budget_period": "MONTHLY"},
    )
    response = client.get("/api/v1/collector-profile/recommendations", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "items" in data
    if data["items"]:
        row = data["items"][0]
        assert "global_score" in row
        assert "personalized_score" in row
        assert "collector_adjustment" in row


def test_budget_status_and_quantities(client: TestClient) -> None:
    token = register_and_login(client, "p77-qty@example.com")
    status = client.get("/api/v1/collector-profile/budget-status", headers=auth_headers(token))
    assert status.status_code == 200
    assert status.json()["data"]["budget_state"] in {"GREEN", "YELLOW", "RED"}

    qty = client.get("/api/v1/collector-profile/quantities", headers=auth_headers(token))
    assert qty.status_code == 200

    dash = client.get("/api/v1/collector-profile/personalized-dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    assert "budget_status" in dash.json()["data"]

