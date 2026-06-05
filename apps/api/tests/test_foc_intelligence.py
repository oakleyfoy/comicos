from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.collector_intelligence import FOCAlertItem
from app.services.demand_refresh_service import run_demand_refresh
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.foc_intelligence_service import generate_foc_alerts, list_foc_items
from tests.test_buy_queue_intelligence import _owner_id, _seed_catalog, register_and_login


def test_foc_alerts_ordered(client: TestClient, session: Session) -> None:
    email = "foc-ord@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    snap = generate_foc_alerts(session, owner_user_id=owner_id)
    items, _ = list_foc_items(session, snapshot_id=int(snap.id or 0))
    assert len(items) >= 1
    assert all(i.foc_date is not None for i in items)
    if len(items) > 1:
        assert items[0].urgency_score >= items[1].urgency_score


def test_foc_api_build(client: TestClient, session: Session) -> None:
    email = "foc-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/recommendation-intelligence/foc/build", headers=headers)
    assert resp.status_code == 200
    row = session.exec(select(FOCAlertItem).where(FOCAlertItem.owner_user_id == owner_id)).first()
    assert row is not None
