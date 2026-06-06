from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p81_discovery import P81DiscoveryWatchlist
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_auto_and_manual_watchlists(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-wl@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-wl@example.com")).one().id or 0)
    client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={"publishers": [{"interest_type": "PUBLISHER", "label": "Image", "priority_rank": 1}]},
    )
    seed_release_number_one(session, owner_user_id=owner_id)
    client.get("/api/v1/discovery/dashboard?refresh=true", headers=auth_headers(token))

    listed = client.get("/api/v1/discovery/watchlists", headers=auth_headers(token))
    assert listed.status_code == 200
    auto_items = listed.json()["data"]["items"]
    assert any(i["label"] == "Image" and i["auto_managed"] for i in auto_items)

    created = client.post(
        "/api/v1/discovery/watchlists",
        headers=auth_headers(token),
        json={"watchlist_type": "SERIES", "label": "Absolute Batman"},
    )
    assert created.status_code == 201
    wl_id = created.json()["data"]["id"]
    updated = client.put(
        f"/api/v1/discovery/watchlists/{wl_id}",
        headers=auth_headers(token),
        json={"active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["active"] is False

    rows = session.exec(select(P81DiscoveryWatchlist).where(P81DiscoveryWatchlist.owner_user_id == owner_id)).all()
    assert len(rows) >= 2
