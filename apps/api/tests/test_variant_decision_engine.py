from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from test_p66_helpers import seed_p66_owner


def test_variant_decision_ranking(client: TestClient, session: Session) -> None:
    email = "p66-dec@example.com"
    _, token = seed_p66_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    bq_before = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    build = client.post("/api/v1/variant-decision/platform/build", headers=headers)
    assert build.status_code == 200
    bq_after = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    assert bq_after == bq_before
    latest = client.get("/api/v1/variant-decision/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["total_issues"] >= 1
    item = data["items"][0]
    assert len(item["cover_ranking_json"]) >= 2
    assert item["buy_plan_json"]
