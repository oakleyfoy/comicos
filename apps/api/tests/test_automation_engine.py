"""P90 automation engine tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.automation_engine_service import run_collector_automation
from test_inventory import auth_headers, create_order, register_and_login


def test_automation_dry_run_no_writes(client, session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "p90-engine@example.com")
    user = session.exec(select(User).where(User.email == "p90-engine@example.com")).one()
    with patch("app.services.sell_candidate_service.recalculate_sell_candidates") as sell_gen:
        with patch("app.services.marketplace.marketplace_monitoring_service.search_comics") as search:
            summary = run_collector_automation(session, owner_user_id=int(user.id), dry_run=True)
    assert summary["dry_run"] is True
    assert summary["status"] == "SUCCESS"
    sell_gen.assert_not_called()
    search.assert_not_called()

    resp = client.get("/api/v1/automation/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200


def test_automation_sync_creates_alerts(client, session) -> None:
    from app.models import User
    from app.models.p89_sell_candidate import P89SellCandidate, utc_now
    from app.models.asset_ledger import InventoryCopy
    from sqlmodel import select

    token = register_and_login(client, "p90-sync@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p90-sync@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    session.add(
        P89SellCandidate(
            owner_user_id=int(user.id),
            inventory_copy_id=int(copy.id),
            recommendation="SELL_NOW",
            sell_score=88,
            hold_score=10,
            grade_first_score=5,
            monitor_score=0,
            confidence="HIGH",
            estimated_sale_value=100,
            estimated_profit=40,
            reason_summary="Absolute Batman #1",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    session.commit()
    summary = run_collector_automation(session, owner_user_id=int(user.id), dry_run=False)
    session.commit()
    assert summary["alerts_created"] >= 1 or summary["alerts_updated"] >= 1
