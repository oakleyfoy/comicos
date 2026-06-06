"""P71 production review: routes, determinism, GET safety, edge cases."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models import InventoryCopy
from app.models.sell_intelligence_platform import (
    EXIT_GRADE_THEN_SELL,
    EXIT_HOLD,
    EXIT_SELL_NOW,
    EXIT_TRIM,
    EXIT_WATCH,
    P71ExitQueueSnapshot,
    P71ExitRecommendationSnapshot,
    P71InvestorSellDashboardSnapshot,
    P71LiquiditySnapshot,
    P71ListingRecommendationSnapshot,
)
from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_exit, score_liquidity, score_listing
from test_inventory import auth_headers, register_and_login

P71_GET_PATHS = (
    "/api/v1/sell-intelligence/platform/certification",
    "/api/v1/sell-intelligence/exit-recommendations",
    "/api/v1/sell-intelligence/listing-intelligence",
    "/api/v1/sell-intelligence/liquidity",
    "/api/v1/sell-intelligence/exit-queue",
    "/api/v1/sell-intelligence/dashboard",
)


def _ctx(**overrides) -> SellIntelCopyContext:
    base = dict(
        copy_id=1,
        title="Test Book",
        publisher="Marvel",
        issue_number="1",
        quantity=1,
        cost_basis=10.0,
        estimated_fmv=20.0,
        fmv_confidence=0.5,
        liquidity_score=40.0,
        sales_count=2,
        price_trend="STABLE",
        unrealized_gain=10.0,
        unrealized_gain_pct=100.0,
        grade_status="raw",
        portfolio_share_pct=2.0,
        recommendation_hit_rate=0.0,
    )
    base.update(overrides)
    return SellIntelCopyContext(**base)


def test_p71_scoring_actions_are_deterministic() -> None:
    sell_ctx = _ctx(
        estimated_fmv=200,
        cost_basis=50,
        unrealized_gain_pct=300,
        liquidity_score=70,
        price_trend="RISING",
        fmv_confidence=0.8,
    )
    a1, s1, *_ = score_exit(sell_ctx)
    a2, s2, *_ = score_exit(sell_ctx)
    assert a1 == a2 and s1 == s2
    assert a1 == EXIT_SELL_NOW

    hold_ctx = _ctx(estimated_fmv=12, cost_basis=10, unrealized_gain_pct=20, liquidity_score=15, fmv_confidence=0.3)
    hold_action, hold_score, *_ = score_exit(hold_ctx)
    assert hold_action == EXIT_HOLD
    assert hold_score < 30

    watch_ctx = _ctx(
        unrealized_gain_pct=35,
        liquidity_score=20,
        fmv_confidence=0.55,
        price_trend="RISING",
        portfolio_share_pct=10,
        quantity=1,
    )
    watch_action, watch_score, *_ = score_exit(watch_ctx)
    assert watch_score >= 42
    assert watch_action == EXIT_WATCH

    trim_ctx = _ctx(quantity=4, portfolio_share_pct=15, unrealized_gain_pct=25, liquidity_score=50)
    trim_action, trim_score, *_ = score_exit(trim_ctx)
    assert trim_action == EXIT_TRIM
    assert trim_score >= 40

    grade_ctx = _ctx(
        estimated_fmv=90,
        cost_basis=40,
        unrealized_gain_pct=125,
        liquidity_score=42,
        fmv_confidence=0.7,
        grade_status="raw",
        price_trend="RISING",
        quantity=1,
        portfolio_share_pct=2,
    )
    grade_action, grade_score, *_ = score_exit(grade_ctx)
    assert grade_score >= 45
    assert grade_action == EXIT_GRADE_THEN_SELL


def test_p71_listing_and_liquidity_weak_pricing_safe() -> None:
    no_fmv = score_listing(_ctx(estimated_fmv=0, cost_basis=25))
    assert no_fmv[0] is None
    assert no_fmv[7] == "EITHER"

    cost_only = score_listing(_ctx(estimated_fmv=0, cost_basis=40))
    assert cost_only[4] == 0.0

    fmv_no_cost = score_listing(_ctx(estimated_fmv=30, cost_basis=0))
    assert fmv_no_cost[5] == 0.0

    zero_sales = score_liquidity(_ctx(sales_count=0, liquidity_score=0, fmv_confidence=0.2))
    assert zero_sales[0] in ("LOW", "MEDIUM", "HIGH")
    assert 5 <= zero_sales[6] <= 150


def test_p71_empty_inventory_build_and_get(client: TestClient) -> None:
    token = register_and_login(client, "p71-empty@example.com")
    headers = auth_headers(token)
    build = client.post("/api/v1/sell-intelligence/platform/build", headers=headers)
    assert build.status_code == 200
    exits = client.get("/api/v1/sell-intelligence/exit-recommendations", headers=headers)
    assert exits.status_code == 200
    assert exits.json()["data"]["items"] == []


def test_p71_get_routes_do_not_mutate_snapshots(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p71-get-safe@example.com")
    headers = auth_headers(token)
    client.post("/api/v1/sell-intelligence/platform/build", headers=headers)

    def count(model) -> int:
        return int(session.exec(select(func.count()).select_from(model)).one())

    before = {
        "exit": count(P71ExitRecommendationSnapshot),
        "listing": count(P71ListingRecommendationSnapshot),
        "liquidity": count(P71LiquiditySnapshot),
        "queue": count(P71ExitQueueSnapshot),
        "dashboard": count(P71InvestorSellDashboardSnapshot),
    }
    inventory_before = {
        int(row.id or 0): float(row.current_fmv or 0)
        for row in session.exec(select(InventoryCopy)).all()
    }

    for path in P71_GET_PATHS:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path

    after = {
        "exit": count(P71ExitRecommendationSnapshot),
        "listing": count(P71ListingRecommendationSnapshot),
        "liquidity": count(P71LiquiditySnapshot),
        "queue": count(P71ExitQueueSnapshot),
        "dashboard": count(P71InvestorSellDashboardSnapshot),
    }
    assert before == after

    for row in session.exec(select(InventoryCopy)).all():
        cid = int(row.id or 0)
        if cid:
            assert float(row.current_fmv or 0) == inventory_before.get(cid, float(row.current_fmv or 0))


def test_p71_exit_queue_priority_ordering(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p71-queue@example.com")
    headers = auth_headers(token)
    client.post("/api/v1/sell-intelligence/platform/build", headers=headers)
    res = client.get("/api/v1/sell-intelligence/exit-queue", headers=headers)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    priorities = [row["priority"] for row in items]
    assert priorities == sorted(priorities)


def test_p71_routes_require_auth(client: TestClient) -> None:
    for path in P71_GET_PATHS:
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/sell-intelligence/platform/build").status_code == 401
