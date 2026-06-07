"""P89-05 Sell Command Center tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.sell_command_center_service import build_sell_command_center
from test_inventory import auth_headers, create_order, register_and_login


def test_sell_command_center_api(client: TestClient) -> None:
    token = register_and_login(client, "p89-scc@example.com")
    with patch("app.services.sell_candidate_service.recalculate_sell_candidates") as gen:
        with patch("app.services.p89_market_pricing_service.generate_market_price_snapshots") as pricing:
            resp = client.get("/api/v1/sell-command-center", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "kpis" in data
    assert "daily_actions" in data
    assert "sell_now" in data
    assert "profit_summary" in data
    assert "quick_actions" in data
    gen.assert_not_called()
    pricing.assert_not_called()


def test_sell_command_center_empty_state(client: TestClient) -> None:
    token = register_and_login(client, "p89-scc-empty@example.com")
    resp = client.get("/api/v1/sell-command-center", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "OK"
    assert resp.json()["data"]["kpis"]["sell_now_count"] == 0


def test_action_feed_ranking(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "p89-scc-rank@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "p89-scc-rank@example.com")).one()
    dash = build_sell_command_center(session, owner_user_id=int(user.id))
    if dash.daily_actions:
        ranks = [a.rank for a in dash.daily_actions]
        assert ranks == sorted(ranks)
        scores = [a.urgency_score for a in dash.daily_actions]
        assert scores == sorted(scores, reverse=True)


def test_kpis_and_profit_summary(client: TestClient, session: Session) -> None:
    from app.models.p89_sell_candidate import P89SellCandidate, utc_now

    token = register_and_login(client, "p89-scc-kpi@example.com")
    create_order(client, token)
    from app.models import User
    from app.models.asset_ledger import InventoryCopy
    from sqlmodel import select

    user = session.exec(select(User).where(User.email == "p89-scc-kpi@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    now = utc_now()
    session.add(
        P89SellCandidate(
            owner_user_id=int(user.id),
            inventory_copy_id=int(copy.id),
            recommendation="SELL_NOW",
            sell_score=90,
            hold_score=10,
            grade_first_score=5,
            monitor_score=5,
            confidence="HIGH",
            estimated_sale_value=50,
            estimated_profit=25,
            reason_summary="Test",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    dash = build_sell_command_center(session, owner_user_id=int(user.id))
    assert dash.kpis.sell_now_count >= 1
    assert dash.profit_summary.sold_count >= 0
