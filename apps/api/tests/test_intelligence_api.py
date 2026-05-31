from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import auth_headers, register_and_login


def test_intelligence_api_seed_dashboard_and_lists(client: TestClient) -> None:
    email = "intelligence-api@example.com"
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_id)

    seed = client.post("/api/v1/intelligence/seed", headers=auth_headers(token))
    characters = client.get("/api/v1/intelligence/characters?limit=5", headers=auth_headers(token))
    franchises = client.get("/api/v1/intelligence/franchises?limit=5", headers=auth_headers(token))
    creators = client.get("/api/v1/intelligence/creators?limit=5", headers=auth_headers(token))
    dashboard = client.get("/api/v1/intelligence/dashboard", headers=auth_headers(token))

    assert seed.status_code == 200, seed.text
    assert seed.json()["data"]["character_count"] >= 100
    assert characters.status_code == 200
    assert franchises.status_code == 200
    assert creators.status_code == 200
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["top_characters"]
    assert dashboard.json()["data"]["top_franchises"]
    assert dashboard.json()["data"]["top_creators"]
