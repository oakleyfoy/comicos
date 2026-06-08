"""P90-03 Collector Advisor tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.advisor_priority_service import rank_advisor_actions
from app.services.collector_advisor_service import generate_collector_advisor_snapshot
from app.services.portfolio_impact_service import compute_portfolio_impact
from test_inventory import auth_headers, register_and_login


def test_advisor_priority_orders_by_score() -> None:
    actions = [
        {"category": "BUY", "alert_type": "BUY_OPPORTUNITY", "confidence": "LOW", "severity": "LOW", "profit_signal": 1.0},
        {"category": "SELL", "alert_type": "SELL_OPPORTUNITY", "confidence": "HIGH", "severity": "HIGH", "profit_signal": 30.0},
    ]
    ranked = rank_advisor_actions(actions, limit=2)
    assert ranked[0]["priority_score"] >= ranked[1]["priority_score"]


def test_portfolio_impact_sums() -> None:
    impact = compute_portfolio_impact(
        buy_actions=[{"potential_upside": 10.0}],
        sell_actions=[{"profit_potential": 25.0}],
        grade_actions=[{"value_increase": 5.0}],
    )
    assert impact["portfolio_impact_total"] == 40.0
    assert impact["estimated_profit"] == 25.0
    assert impact["estimated_savings"] == 10.0


def test_collector_advisor_dry_run(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    register_and_login(client, "advisor-dry@example.com")
    user = session.exec(select(User).where(User.email == "advisor-dry@example.com")).one()
    summary = generate_collector_advisor_snapshot(session, owner_user_id=int(user.id), dry_run=True)
    assert "buy_actions" in summary
    assert summary["dry_run"] is True


def test_collector_advisor_generate_endpoint(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "advisor-generate@example.com")
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "OK"
    assert data["plan"] is not None


def test_collector_advisor_persist_and_api(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "advisor-api@example.com")
    user = session.exec(select(User).where(User.email == "advisor-api@example.com")).one()
    generate_collector_advisor_snapshot(session, owner_user_id=int(user.id), dry_run=False)
    session.commit()
    resp = client.get("/api/v1/collector-advisor", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] in {"OK", "EMPTY"}
    if data["plan"]:
        assert "buy_actions" in data["plan"]
        assert "portfolio_impact" in data["plan"]
