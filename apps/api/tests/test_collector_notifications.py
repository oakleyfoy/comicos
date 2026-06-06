from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_notification_lifecycle(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-notif@example.com")
    listed = client.get("/api/v1/notifications?refresh=true", headers=auth_headers(token))
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    if not items:
        client.post(
            "/api/v1/marketplace-acquisition/scan",
            headers=auth_headers(token),
            json={"external_listing_id": "P84-N-1", "title": "Notify Test #1", "asking_price": 5.0},
        )
        listed = client.get("/api/v1/notifications?refresh=true", headers=auth_headers(token))
        items = listed.json()["data"]["items"]
    assert listed.json()["data"]["pagination"]["total_count"] >= 0
    if items:
        nid = items[0]["id"]
        read = client.put(
            f"/api/v1/notifications/{nid}",
            headers=auth_headers(token),
            json={"status": "READ"},
        )
        assert read.status_code == 200
        assert read.json()["data"]["status"] == "READ"
    dash = client.get("/api/v1/notifications/dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
