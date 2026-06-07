"""Tests for marketplace alerts API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p88_marketplace_monitoring import MarketplaceAlert, utc_now
from test_inventory import auth_headers, register_and_login


def test_alert_acknowledge(client: TestClient, session: Session) -> None:
    email = "p88-alert@example.com"
    token = register_and_login(client, email)
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None
    user_id = int(user.id or 0)
    row = MarketplaceAlert(
        owner_user_id=user_id,
        alert_type="NEW_LISTING",
        title="Test alert",
        message="New listing",
        severity="MEDIUM",
        status="NEW",
        dedupe_key="k1",
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    listed = client.get("/api/v1/marketplace-monitoring/alerts", headers=auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()["data"]["items"]) >= 1

    resp = client.patch(
        f"/api/v1/marketplace-monitoring/alerts/{row.id}",
        headers=auth_headers(token),
        json={"status": "ACKNOWLEDGED"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACKNOWLEDGED"
