from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.schemas.release_watchlist import ReleaseWatchlistCreateRequest, ReleaseWatchlistItemCreateRequest
from app.services.release_import import import_release_feed
from app.services.release_watchlists import add_watchlist_item, create_watchlist
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_watchlist_monitoring_endpoint(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-wl@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-wl@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    wl = create_watchlist(
        session,
        owner_user_id=owner_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="Marvel watch", watchlist_type="PUBLISHER"),
    )
    add_watchlist_item(
        session,
        owner_user_id=owner_id,
        watchlist_id=wl.watchlist.id,
        payload=ReleaseWatchlistItemCreateRequest(publisher="Marvel", series_name="Amazing Future"),
    )

    resp = client.get(
        "/api/v1/release-monitoring/watchlist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["total_watchlists"] >= 1
