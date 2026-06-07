"""P90 collector alerts API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.p90_collector_alert import utc_now
from app.services.automation_engine_service import run_collector_automation
from app.services.collector_alert_service import list_collector_alerts, update_collector_alert
from app.schemas.p90_automation import P90CollectorAlertUpdate
from test_inventory import auth_headers, create_order, register_and_login


def test_list_and_patch_alerts(client: TestClient, session) -> None:
    from app.models import User
    from app.models.asset_ledger import InventoryCopy
    from app.models.p89_sell_candidate import P89SellCandidate
    from sqlmodel import select

    token = register_and_login(client, "p90-alerts@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p90-alerts@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    session.add(
        P89SellCandidate(
            owner_user_id=int(user.id),
            inventory_copy_id=int(copy.id),
            recommendation="GRADE_FIRST",
            sell_score=10,
            hold_score=10,
            grade_first_score=85,
            monitor_score=0,
            confidence="HIGH",
            estimated_sale_value=200,
            estimated_profit=50,
            reason_summary="Grade ASM #300",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    session.commit()
    run_collector_automation(session, owner_user_id=int(user.id), dry_run=False)
    session.commit()

    listed = list_collector_alerts(session, owner_user_id=int(user.id))
    assert listed.total >= 1

    resp = client.get("/api/v1/automation/alerts", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]["items"]) >= 1

    alert_id = listed.items[0].id
    patch = client.patch(
        f"/api/v1/automation/alerts/{alert_id}",
        headers=auth_headers(token),
        json={"status": "ACKNOWLEDGED"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "ACKNOWLEDGED"


def test_update_alert_service(client: TestClient, session) -> None:
    from app.models import User
    from app.models.p89_sell_candidate import P89SellCandidate
    from app.models.asset_ledger import InventoryCopy
    from sqlmodel import select

    token = register_and_login(client, "p90-patch-svc@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p90-patch-svc@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    session.add(
        P89SellCandidate(
            owner_user_id=int(user.id),
            inventory_copy_id=int(copy.id),
            recommendation="SELL_NOW",
            sell_score=80,
            hold_score=10,
            grade_first_score=5,
            monitor_score=0,
            confidence="HIGH",
            estimated_sale_value=100,
            estimated_profit=30,
            reason_summary="Test",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    session.commit()
    run_collector_automation(session, owner_user_id=int(user.id), dry_run=False)
    session.commit()
    listed = list_collector_alerts(session, owner_user_id=int(user.id))
    alert_id = listed.items[0].id
    updated = update_collector_alert(
        session,
        owner_user_id=int(user.id),
        alert_id=alert_id,
        payload=P90CollectorAlertUpdate(status="DISMISSED"),
    )
    assert updated.status == "DISMISSED"


def test_automation_summary(client: TestClient) -> None:
    token = register_and_login(client, "p90-summary@example.com")
    resp = client.get("/api/v1/automation/summary", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "todays_actions" in body
    assert "briefing_summary" in body
