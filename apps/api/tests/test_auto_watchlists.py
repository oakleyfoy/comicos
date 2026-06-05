from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.auto_watchlist_service import build_auto_watchlists, get_latest_watchlists, list_watchlist_items
from tests.test_buy_queue_intelligence import _owner_id, _seed_catalog, register_and_login


def test_auto_watchlists_build_with_explanations(client: TestClient, session: Session) -> None:
    email = "autowl@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    built = build_auto_watchlists(session, owner_user_id=owner_id)
    assert len(built) >= 1
    latest = get_latest_watchlists(session, owner_user_id=owner_id)
    assert latest
    for wl in latest:
        for item in list_watchlist_items(session, watchlist_id=int(wl.id or 0)):
            assert item.inclusion_reason


def test_auto_watchlist_refresh_api(client: TestClient, session: Session) -> None:
    email = "autowl-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/recommendation-intelligence/watchlists/auto/refresh", headers=headers)
    assert resp.status_code == 200
    listed = client.get("/api/v1/recommendation-intelligence/watchlists/auto", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]["watchlists"]) >= 1
