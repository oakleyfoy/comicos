from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from test_inventory import auth_headers, register_and_login
from test_p78_sell_workflow import _seed_sell_copy
from test_sales_tracking import _publish_and_sync


def test_selling_analytics_and_dashboard(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-analytics@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-analytics@example.com")).one().id or 0)
    copy_id = _seed_sell_copy(session, owner_user_id=owner_id, copies=1)
    _publish_and_sync(client, token, copy_id)

    analytics = client.get("/api/v1/selling-analytics", headers=auth_headers(token))
    assert analytics.status_code == 200, analytics.text
    a = analytics.json()["data"]
    assert a["listings_created"] >= 1
    assert a["listings_sold"] >= 1
    assert a["revenue"] >= 0
    assert a["snapshot_id"] is not None

    dash = client.get("/api/v1/selling-dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    d = dash.json()["data"]
    assert d["analytics"]["listings_sold"] >= 1
    assert isinstance(d["recent_sales"], list)
