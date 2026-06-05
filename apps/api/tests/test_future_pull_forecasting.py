from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.pull_list import PullList
from app.services.future_pull_forecast_service import generate_future_pull_forecast, list_forecast_items
from tests.test_buy_queue_intelligence import _owner_id, _seed_catalog, register_and_login


def test_pull_forecast_confidence_and_explanation(client: TestClient, session: Session) -> None:
    email = "forecast@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    session.add(
        PullList(
            owner_user_id=owner_id,
            publisher="Marvel",
            series_name="Buy Queue Series",
            status="ACTIVE",
        )
    )
    session.commit()
    fc = generate_future_pull_forecast(session, owner_user_id=owner_id)
    items, total = list_forecast_items(session, forecast_id=int(fc.id or 0))
    assert total >= 1
    assert items[0].confidence in ("HIGH", "MEDIUM", "LOW")
    assert items[0].explanation


def test_pull_forecast_api(client: TestClient, session: Session) -> None:
    email = "forecast-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/recommendation-intelligence/pull-forecast/build", headers=headers)
    resp = client.get("/api/v1/recommendation-intelligence/pull-forecast/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] >= 1
