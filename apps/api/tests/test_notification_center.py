from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.collector_experience import NotificationItem
from test_inventory import register_and_login
from test_p64_collector_assistant import seed_p64_upstream


def test_notifications_build_and_status(client: TestClient, session: Session) -> None:
    email = "p65-notif@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    build = client.post("/api/v1/notifications/build", headers=headers)
    assert build.status_code == 200
    latest = client.get("/api/v1/notifications/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["readiness_status"] == "SUCCESS"
    item = session.exec(select(NotificationItem).order_by(NotificationItem.id.desc())).first()
    assert item is not None
    patch = client.patch(
        f"/api/v1/notifications/items/{int(item.id or 0)}",
        headers=headers,
        json={"status": "READ"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "READ"
