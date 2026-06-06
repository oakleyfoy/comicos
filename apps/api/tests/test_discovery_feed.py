"""P81 spec alias — discovery feed API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_discovery_feed_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-feed@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-feed@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    response = client.get("/api/v1/discovery/feed?refresh=true", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert "top_opportunities" in data
