"""P38-07 portfolio strategy dashboard deterministic behavior."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryLiquiditySnapshot, PortfolioStrategyDashboardAlert, PortfolioStrategyDashboardFeedEvent, User
from test_inventory import auth_headers, create_order, register_and_login


def _ck(label: str = "p38-07-test") -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _seed_liquidity_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    issue_id: int,
    liquidity_status: str,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
    snapshot_date: date,
) -> None:
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_item_id,
            canonical_comic_issue_id=issue_id,
            channel=None,
            liquidity_status=liquidity_status,
            days_on_market_median=None,
            days_to_sale_median=None,
            sell_through_rate_pct=sell_through_rate_pct,
            stale_listing_rate_pct=stale_listing_rate_pct,
            relist_rate_pct=Decimal("0"),
            successful_sale_count=0,
            failed_listing_count=0,
            active_listing_count=0,
            liquidity_confidence="CONFIDENT",
            evaluation_window_days=365,
            snapshot_date=snapshot_date,
            checksum=_ck(f"{owner_user_id}:{inventory_item_id}:{snapshot_date.isoformat()}"),
            evidence_count=0,
        )
    )
    session.commit()


def _seed_strategy_inputs(client: TestClient, session: Session, token: str, owner_id: int, *, snapshot_date: date) -> list[int]:
    create_order(
        client,
        token,
        items=[
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": "Regular",
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 12.5,
            }
        ],
    )
    inventory_rows = client.get("/inventory", headers=auth_headers(token)).json()["items"]
    inventory_ids = [int(row["inventory_copy_id"]) for row in inventory_rows]
    for idx, inventory_item_id in enumerate(inventory_ids, start=1):
        inv = session.get(InventoryCopy, inventory_item_id)
        assert inv is not None
        inv.current_fmv = Decimal("150.00") + Decimal(str(idx * 25))
        session.add(inv)
        _seed_liquidity_snapshot(
            session,
            owner_user_id=owner_id,
            inventory_item_id=inventory_item_id,
            issue_id=inventory_item_id,
            liquidity_status="LOW" if idx == 1 else "ILLIQUID",
            sell_through_rate_pct=Decimal("10.00"),
            stale_listing_rate_pct=Decimal("85.00"),
            snapshot_date=snapshot_date,
        )
    session.commit()

    portfolio_rsp = client.post(
        "/portfolios",
        headers=auth_headers(token),
        json={"name": "Strategy", "portfolio_type": "personal_collection", "replay_key": f"pf-{owner_id}"},
    )
    assert portfolio_rsp.status_code in (200, 201), portfolio_rsp.text
    portfolio_id = int(portfolio_rsp.json()["id"])
    for inventory_item_id in inventory_ids:
        add_rsp = client.post(
            f"/portfolios/{portfolio_id}/items",
            headers=auth_headers(token),
            json={"inventory_item_id": inventory_item_id, "allocation_role": "core_holding"},
        )
        assert add_rsp.status_code == 201, add_rsp.text

    date_str = str(snapshot_date)
    assert client.post(
        "/portfolio-allocations/generate",
        headers=auth_headers(token),
        json={"replay_key": f"alloc-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    assert client.post(
        "/portfolio-liquidity/generate",
        headers=auth_headers(token),
        json={"replay_key": f"liq-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    assert client.post(
        "/duplicate-clusters/generate",
        headers=auth_headers(token),
        json={"replay_key": f"dup-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    assert client.post(
        "/portfolio-recommendations/generate",
        headers=auth_headers(token),
        json={"replay_key": f"rec-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    assert client.post(
        "/concentration-risk/generate",
        headers=auth_headers(token),
        json={"replay_key": f"conc-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    assert client.post(
        "/acquisition-priorities/generate",
        headers=auth_headers(token),
        json={"replay_key": f"acq-{owner_id}", "snapshot_date": date_str},
    ).status_code in (200, 201)
    return inventory_ids


def test_portfolio_strategy_dashboard_replay_stable_checksum_no_fmv_mutation(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "strategy-replay@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "strategy-replay@example.com")).one())
    inventory_ids = _seed_strategy_inputs(client, session, token, owner_id, snapshot_date=date(2026, 5, 29))
    before_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]

    body = {"replay_key": "strategy-rk-1", "snapshot_date": str(date(2026, 5, 29))}
    first = client.post("/portfolio-strategy-dashboard/generate", headers=auth_headers(token), json=body)
    assert first.status_code == 201, first.text
    second = client.post("/portfolio-strategy-dashboard/generate", headers=auth_headers(token), json=body)
    assert second.status_code == 200, second.text
    assert first.json()["snapshot"]["checksum"] == second.json()["snapshot"]["checksum"]

    get_rsp = client.get("/portfolio-strategy-dashboard", headers=auth_headers(token))
    assert get_rsp.status_code == 200, get_rsp.text
    assert get_rsp.json()["snapshot"]["portfolio_count"] == 1

    after_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]
    assert after_fmv == before_fmv


def test_portfolio_strategy_dashboard_alerts_feed_metrics_are_stable(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "strategy-alerts@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "strategy-alerts@example.com")).one())
    _seed_strategy_inputs(client, session, token, owner_id, snapshot_date=date(2026, 5, 30))

    gen = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token),
        json={"replay_key": "strategy-alerts", "snapshot_date": str(date(2026, 5, 30))},
    )
    assert gen.status_code == 201, gen.text

    alerts = client.get("/portfolio-strategy-dashboard/alerts", headers=auth_headers(token))
    assert alerts.status_code == 200, alerts.text
    alert_rows = alerts.json()["items"]
    alert_types = {row["alert_type"] for row in alert_rows}
    assert {"DEAD_CAPITAL", "DUPLICATE_RISK", "OVEREXPOSURE"} & alert_types
    assert [row["created_at"] for row in alert_rows] == sorted([row["created_at"] for row in alert_rows], reverse=True)

    feed = client.get("/portfolio-strategy-dashboard/feed", headers=auth_headers(token))
    assert feed.status_code == 200, feed.text
    feed_rows = feed.json()["items"]
    feed_types = {row["event_type"] for row in feed_rows}
    assert {"PORTFOLIO_CREATED", "DUPLICATE_CLUSTER_CREATED", "LIQUIDITY_WARNING"} & feed_types
    assert [row["created_at"] for row in feed_rows] == sorted([row["created_at"] for row in feed_rows], reverse=True)

    metrics = client.get("/portfolio-strategy-dashboard/metrics", headers=auth_headers(token))
    assert metrics.status_code == 200, metrics.text
    metric_keys = {row["metric_key"] for row in metrics.json()["items"]}
    assert {"portfolio_count", "duplicate_cluster_count", "capital_release_estimate"} <= metric_keys

    alert_count_before = len(session.exec(select(PortfolioStrategyDashboardAlert).where(PortfolioStrategyDashboardAlert.owner_user_id == owner_id)).all())
    feed_count_before = len(session.exec(select(PortfolioStrategyDashboardFeedEvent).where(PortfolioStrategyDashboardFeedEvent.owner_user_id == owner_id)).all())
    replay = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token),
        json={"replay_key": "strategy-alerts", "snapshot_date": str(date(2026, 5, 30))},
    )
    assert replay.status_code == 200, replay.text
    alert_count_after = len(session.exec(select(PortfolioStrategyDashboardAlert).where(PortfolioStrategyDashboardAlert.owner_user_id == owner_id)).all())
    feed_count_after = len(session.exec(select(PortfolioStrategyDashboardFeedEvent).where(PortfolioStrategyDashboardFeedEvent.owner_user_id == owner_id)).all())
    assert alert_count_after == alert_count_before
    assert feed_count_after == feed_count_before


def test_portfolio_strategy_dashboard_owner_scoping_and_ops_visibility(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "strategy-scope-a@example.com")
    token_b = register_and_login(client, "strategy-scope-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "strategy-scope-a@example.com")).one())
    _seed_strategy_inputs(client, session, token_a, owner_a, snapshot_date=date(2026, 5, 31))

    gen = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "strategy-scope", "snapshot_date": str(date(2026, 5, 31))},
    )
    assert gen.status_code == 201, gen.text

    owner_b_get = client.get("/portfolio-strategy-dashboard", headers=auth_headers(token_b))
    assert owner_b_get.status_code == 200, owner_b_get.text
    assert owner_b_get.json()["snapshot"] is None

    ops_dash = client.get(f"/ops/portfolio-strategy-dashboard?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_dash.status_code == 200, ops_dash.text
    assert ops_dash.json()["snapshot"]["owner_user_id"] == owner_a

    ops_metrics = client.get(f"/ops/portfolio-strategy-dashboard/metrics?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_metrics.status_code == 200, ops_metrics.text
    assert all(isinstance(row["dashboard_snapshot_id"], int) for row in ops_metrics.json()["items"])

    ops_alerts = client.get(f"/ops/portfolio-strategy-dashboard/alerts?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_alerts.status_code == 200, ops_alerts.text
    assert all(row["owner_user_id"] == owner_a for row in ops_alerts.json()["items"])

    ops_feed = client.get(f"/ops/portfolio-strategy-dashboard/feed?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_feed.status_code == 200, ops_feed.text
    assert all(row["owner_user_id"] == owner_a for row in ops_feed.json()["items"])


def test_portfolio_strategy_dashboard_metrics_default_to_latest_snapshot_and_include_dependencies(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "strategy-metrics@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "strategy-metrics@example.com")).one())
    _seed_strategy_inputs(client, session, token, owner_id, snapshot_date=date(2026, 6, 1))

    first = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token),
        json={"replay_key": "strategy-metrics-1", "snapshot_date": str(date(2026, 6, 1))},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token),
        json={"replay_key": "strategy-metrics-2", "snapshot_date": str(date(2026, 6, 2))},
    )
    assert second.status_code == 201, second.text
    latest_snapshot_id = int(second.json()["snapshot"]["id"])

    owner_metrics = client.get("/portfolio-strategy-dashboard/metrics", headers=auth_headers(token))
    assert owner_metrics.status_code == 200, owner_metrics.text
    owner_metric_rows = owner_metrics.json()["items"]
    assert owner_metric_rows
    assert {row["dashboard_snapshot_id"] for row in owner_metric_rows} == {latest_snapshot_id}
    metric_map = {row["metric_key"]: row for row in owner_metric_rows}
    assert metric_map["source_engine_versions"]["metric_metadata_json"]["portfolio_strategy_dashboard"] == "p38-07:v1"
    dependency_graph = metric_map["source_dependency_graph"]["metric_metadata_json"]
    assert dependency_graph["allocation_snapshot_id"] is not None
    assert dependency_graph["liquidity_snapshot_id"] is not None
    assert dependency_graph["duplicate_cluster_ids"]
    assert dependency_graph["recommendation_snapshot_ids"]
    assert dependency_graph["concentration_snapshot_ids"]
    assert dependency_graph["acquisition_snapshot_ids"]

    ops_metrics = client.get(
        f"/ops/portfolio-strategy-dashboard/metrics?owner_user_id={owner_id}",
        headers=auth_headers(token),
    )
    assert ops_metrics.status_code == 200, ops_metrics.text
    assert {row["dashboard_snapshot_id"] for row in ops_metrics.json()["items"]} == {latest_snapshot_id}


def test_portfolio_strategy_dashboard_owner_and_ops_contracts_match_when_scoped(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "strategy-contracts@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "strategy-contracts@example.com")).one())
    _seed_strategy_inputs(client, session, token, owner_id, snapshot_date=date(2026, 6, 3))

    gen = client.post(
        "/portfolio-strategy-dashboard/generate",
        headers=auth_headers(token),
        json={"replay_key": "strategy-contracts", "snapshot_date": str(date(2026, 6, 3))},
    )
    assert gen.status_code == 201, gen.text

    owner_dash = client.get("/portfolio-strategy-dashboard", headers=auth_headers(token))
    ops_dash = client.get(f"/ops/portfolio-strategy-dashboard?owner_user_id={owner_id}", headers=auth_headers(token))
    assert owner_dash.status_code == 200, owner_dash.text
    assert ops_dash.status_code == 200, ops_dash.text
    assert owner_dash.json()["snapshot"].keys() == ops_dash.json()["snapshot"].keys()

    owner_metrics = client.get("/portfolio-strategy-dashboard/metrics", headers=auth_headers(token))
    ops_metrics = client.get(f"/ops/portfolio-strategy-dashboard/metrics?owner_user_id={owner_id}", headers=auth_headers(token))
    assert owner_metrics.status_code == 200, owner_metrics.text
    assert ops_metrics.status_code == 200, ops_metrics.text
    assert owner_metrics.json()["total_items"] == ops_metrics.json()["total_items"]
    assert owner_metrics.json()["items"][0].keys() == ops_metrics.json()["items"][0].keys()

    owner_alerts = client.get("/portfolio-strategy-dashboard/alerts", headers=auth_headers(token))
    ops_alerts = client.get(f"/ops/portfolio-strategy-dashboard/alerts?owner_user_id={owner_id}", headers=auth_headers(token))
    assert owner_alerts.status_code == 200, owner_alerts.text
    assert ops_alerts.status_code == 200, ops_alerts.text
    assert owner_alerts.json()["total_items"] == ops_alerts.json()["total_items"]
    assert owner_alerts.json()["items"][0].keys() == ops_alerts.json()["items"][0].keys()

    owner_feed = client.get("/portfolio-strategy-dashboard/feed", headers=auth_headers(token))
    ops_feed = client.get(f"/ops/portfolio-strategy-dashboard/feed?owner_user_id={owner_id}", headers=auth_headers(token))
    assert owner_feed.status_code == 200, owner_feed.text
    assert ops_feed.status_code == 200, ops_feed.text
    assert owner_feed.json()["total_items"] == ops_feed.json()["total_items"]
    assert owner_feed.json()["items"][0].keys() == ops_feed.json()["items"][0].keys()
