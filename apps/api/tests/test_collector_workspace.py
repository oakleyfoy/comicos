from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.models.collector_experience import CollectorTaskItem, CollectorTaskSnapshot
from test_inventory import register_and_login
from test_p64_collector_assistant import seed_p64_upstream


def test_build_and_latest_tasks(client: TestClient, session: Session) -> None:
    email = "p65-ws@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    bq_before = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    build = client.post("/api/v1/collector-workspace/tasks/build", headers=headers)
    assert build.status_code == 200
    bq_after = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    assert bq_after == bq_before
    latest = client.get("/api/v1/collector-workspace/tasks/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["readiness_status"] == "SUCCESS"
    assert data["total_items"] >= 1


def test_task_status_update(client: TestClient, session: Session) -> None:
    email = "p65-ws-status@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/collector-workspace/tasks/build", headers=headers)
    item = session.exec(select(CollectorTaskItem).order_by(CollectorTaskItem.id.desc())).first()
    assert item is not None
    patch = client.patch(
        f"/api/v1/collector-workspace/tasks/{int(item.id or 0)}",
        headers=headers,
        json={"status": "IN_PROGRESS"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "IN_PROGRESS"


def test_task_history(client: TestClient, session: Session) -> None:
    email = "p65-ws-hist@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/collector-workspace/tasks/build", headers=headers)
    client.post("/api/v1/collector-workspace/tasks/build", headers=headers)
    hist = client.get("/api/v1/collector-workspace/tasks/history", headers=headers)
    assert hist.status_code == 200
    assert len(hist.json()["data"]["entries"]) >= 2
    snaps = session.exec(select(func.count()).select_from(CollectorTaskSnapshot)).one()
    assert snaps >= 2
