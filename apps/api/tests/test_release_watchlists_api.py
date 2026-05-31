from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from test_inventory import auth_headers, create_order, register_and_login


def _seed_watchlist_data(client: TestClient, email: str) -> tuple[str, int]:
    token = register_and_login(client, email)
    create_order(client, token)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        today = date.today()
        payload = ReleaseImportFeedRequest.model_validate(
            {
                "series": [
                    {
                        "publisher": "Image",
                        "series_name": "Invincible",
                        "series_type": "ONGOING",
                        "status": "ACTIVE",
                        "issues": [
                            {
                                "release_uuid": "inv-watch-2",
                                "issue_number": "2",
                                "title": "Invincible #2",
                                "foc_date": str(today),
                                "release_date": str(today + timedelta(days=1)),
                                "release_status": "SCHEDULED",
                            },
                            {
                                "release_uuid": "inv-watch-4",
                                "issue_number": "4",
                                "title": "Invincible #4 Anniversary",
                                "foc_date": str(today + timedelta(days=2)),
                                "release_date": str(today + timedelta(days=3)),
                                "release_status": "SCHEDULED",
                            },
                        ],
                    }
                ]
            }
        )
        import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    return token, owner_user_id


def test_release_watchlists_api_routes_functional_and_owner_scoped(client: TestClient) -> None:
    owner_token, _owner_user_id = _seed_watchlist_data(client, "watchlist-api@example.com")
    outsider_token = register_and_login(client, "watchlist-outsider@example.com")

    created = client.post(
        "/api/v1/release-watchlists/watchlists",
        headers=auth_headers(owner_token),
        json={"watchlist_name": "Manual Invincible", "watchlist_type": "MANUAL"},
    )
    assert created.status_code == 200, created.text
    watchlist_id = created.json()["data"]["watchlist"]["id"]

    added = client.post(
        f"/api/v1/release-watchlists/watchlists/{watchlist_id}/items",
        headers=auth_headers(owner_token),
        json={"publisher": "Image", "series_name": "Invincible"},
    )
    assert added.status_code == 200, added.text
    item_id = added.json()["data"]["items"][0]["id"]

    continuity = client.post("/api/v1/release-watchlists/run/continuity", headers=auth_headers(owner_token))
    foc = client.post("/api/v1/release-watchlists/run/foc-reminders", headers=auth_headers(owner_token))
    release = client.post("/api/v1/release-watchlists/run/release-reminders", headers=auth_headers(owner_token))
    auto = client.post("/api/v1/release-watchlists/run/auto-watchlists", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/release-watchlists/dashboard", headers=auth_headers(owner_token))
    runs = client.get("/api/v1/release-watchlists/runs", headers=auth_headers(owner_token))
    alerts = client.get("/api/v1/release-watchlists/alerts", headers=auth_headers(owner_token))
    reminders = client.get("/api/v1/release-watchlists/reminders", headers=auth_headers(owner_token))
    watchlists = client.get("/api/v1/release-watchlists/watchlists", headers=auth_headers(owner_token))
    outsider_watchlists = client.get("/api/v1/release-watchlists/watchlists", headers=auth_headers(outsider_token))

    assert continuity.status_code == 200, continuity.text
    assert foc.status_code == 200, foc.text
    assert release.status_code == 200, release.text
    assert auto.status_code == 200, auto.text
    assert dashboard.status_code == 200, dashboard.text
    assert runs.status_code == 200, runs.text
    assert alerts.status_code == 200, alerts.text
    assert reminders.status_code == 200, reminders.text
    assert watchlists.status_code == 200, watchlists.text
    assert outsider_watchlists.json()["data"]["items"] == []
    assert len(dashboard.json()["data"]["watchlists"]) >= 1
    assert len(dashboard.json()["data"]["agent_activity"]) >= 1

    removed = client.delete(
        f"/api/v1/release-watchlists/watchlists/{watchlist_id}/items/{item_id}",
        headers=auth_headers(owner_token),
    )
    assert removed.status_code == 200, removed.text
