from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_discovery_feed_and_dashboard(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-dash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-dash@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)

    client.get("/api/v1/discovery/opportunities?refresh=true", headers=auth_headers(token))
    feed = client.get("/api/v1/discovery/feed", headers=auth_headers(token))
    assert feed.status_code == 200, feed.text
    f = feed.json()["data"]
    assert f["snapshot_id"] is not None
    assert len(f["top_opportunities"]) >= 1

    dash = client.post("/api/v1/discovery/dashboard/refresh", headers=auth_headers(token))
    assert dash.status_code == 200
    d = dash.json()["data"]
    assert d["counts"].get("future_pull", 0) >= 0
    assert isinstance(d["watchlists"], list)

    opp_id = f["top_opportunities"][0]["id"]
    detail = client.get(f"/api/v1/discovery/opportunities/{opp_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["data"]["title"]

    assert f["snapshot_id"] is not None
