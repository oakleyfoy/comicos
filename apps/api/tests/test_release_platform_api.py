from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import InventoryCopy, Order, User
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import auth_headers, register_and_login


def test_release_platform_api(client: TestClient) -> None:
    owner_email = "release-platform@example.com"
    outsider_email = "release-platform-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_user_id)
        inventory_before = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
        order_before = len(session.exec(select(Order).where(Order.user_id == owner_user_id)).all())

    horizons = client.get("/api/v1/release-platform/horizons", headers=auth_headers(owner_token))
    opportunities = client.get("/api/v1/release-platform/opportunities", headers=auth_headers(owner_token))
    queue = client.get("/api/v1/release-platform/future-buy-queue", headers=auth_headers(owner_token))
    run_planning = client.get("/api/v1/release-platform/run-planning", headers=auth_headers(owner_token))
    budget = client.get("/api/v1/release-platform/budget", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/release-platform/dashboard", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/release-platform/horizons", headers=auth_headers(outsider_token))

    assert horizons.status_code == 200, horizons.text
    assert opportunities.status_code == 200, opportunities.text
    assert queue.status_code == 200, queue.text
    assert run_planning.status_code == 200, run_planning.text
    assert budget.status_code == 200, budget.text
    assert dashboard.status_code == 200, dashboard.text
    assert horizons.json()["data"]["announced"]
    assert outsider.json()["data"]["announced"] == []
    dashboard_body = dashboard.json()["data"]
    assert "start_following_alerts" in dashboard_body
    assert "new_opportunity_alerts" in dashboard_body

    with Session(get_engine()) as session:
        inventory_after = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
        order_after = len(session.exec(select(Order).where(Order.user_id == owner_user_id)).all())
    assert inventory_before == inventory_after
    assert order_before == order_after
