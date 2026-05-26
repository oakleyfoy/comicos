"""P38-04 portfolio recommendation engine deterministic behavior."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryLiquiditySnapshot, User
from app.models.portfolio_recommendation import PortfolioRecommendationHistory
from app.services.portfolio_recommendation import (
    _classify_confidence,
    _classify_risk,
    _classify_strength,
    _select_action,
)
from test_inventory import auth_headers, create_order, register_and_login


def _ck(label: str = "p38-04-test") -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _seed_liquidity_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    liquidity_status: str,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
    snapshot_date: date,
) -> None:
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_item_id,
            canonical_comic_issue_id=None,
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


def test_portfolio_recommendation_replay_stable_checksum_no_fmv_mutation(
    client: TestClient, session: Session
) -> None:
    token = register_and_login(client, "preco-replay@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "preco-replay@example.com")).one())

    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "18",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 14.25,
            },
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200, inv_rsp.text
    inventory_item_id = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_before = session.get(InventoryCopy, inventory_item_id)
    assert inv_before is not None
    inv_before.current_fmv = Decimal("120.00")
    session.add(inv_before)
    session.commit()
    before_fmv = inv_before.current_fmv

    _seed_liquidity_snapshot(
        session,
        owner_user_id=owner_id,
        inventory_item_id=inventory_item_id,
        liquidity_status="HIGH",
        sell_through_rate_pct=Decimal("45.00"),
        stale_listing_rate_pct=Decimal("8.00"),
        snapshot_date=date(2026, 5, 26),
    )

    body = {"replay_key": "preco-rk-1", "snapshot_date": str(date(2026, 5, 26))}
    r1 = client.post("/portfolio-recommendations/generate", headers=auth_headers(token), json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/portfolio-recommendations/generate", headers=auth_headers(token), json=body)
    assert r2.status_code == 200, r2.text

    js1 = r1.json()
    js2 = r2.json()
    assert js1["total"] == 1
    assert js2["total"] == 1
    assert js1["items"][0]["checksum"] == js2["items"][0]["checksum"]

    inv_after = session.get(InventoryCopy, inventory_item_id)
    assert inv_after is not None
    assert inv_after.current_fmv == before_fmv


def test_portfolio_recommendation_history_scenarios_and_scoping(
    client: TestClient, session: Session
) -> None:
    token_a = register_and_login(client, "preco-scope-a@example.com")
    token_b = register_and_login(client, "preco-scope-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "preco-scope-a@example.com")).one())

    create_order(
        client,
        token_a,
        items=[
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "5",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 9.0,
            },
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token_a))
    assert inv_rsp.status_code == 200, inv_rsp.text
    inventory_item_id = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_row = session.get(InventoryCopy, inventory_item_id)
    assert inv_row is not None
    inv_row.current_fmv = Decimal("100.00")
    session.add(inv_row)
    session.commit()

    _seed_liquidity_snapshot(
        session,
        owner_user_id=owner_a,
        inventory_item_id=inventory_item_id,
        liquidity_status="ILLIQUID",
        sell_through_rate_pct=Decimal("5.00"),
        stale_listing_rate_pct=Decimal("88.00"),
        snapshot_date=date(2026, 5, 27),
    )

    body = {"replay_key": "preco-rk-scope", "snapshot_date": str(date(2026, 5, 27))}
    gen = client.post("/portfolio-recommendations/generate", headers=auth_headers(token_a), json=body)
    assert gen.status_code == 201, gen.text
    recommendation_id = int(gen.json()["items"][0]["id"])

    detail = client.get(f"/portfolio-recommendations/{recommendation_id}", headers=auth_headers(token_a))
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert sorted(item["scenario_name"] for item in detail_body["scenarios"]) == [
        "baseline",
        "optimistic",
        "pessimistic",
    ]
    assert len(detail_body["evidence"]) >= 4

    history_before = session.exec(
        select(PortfolioRecommendationHistory).where(PortfolioRecommendationHistory.owner_user_id == owner_a)
    ).all()
    replay = client.post("/portfolio-recommendations/generate", headers=auth_headers(token_a), json=body)
    assert replay.status_code == 200, replay.text
    history_after = session.exec(
        select(PortfolioRecommendationHistory).where(PortfolioRecommendationHistory.owner_user_id == owner_a)
    ).all()
    assert len(history_after) == len(history_before)

    peer_detail = client.get(f"/portfolio-recommendations/{recommendation_id}", headers=auth_headers(token_b))
    assert peer_detail.status_code == 404

    ops_list = client.get("/ops/portfolio-recommendations", headers=auth_headers(token_a))
    assert ops_list.status_code == 200, ops_list.text
    ops_evidence = client.get(
        f"/ops/portfolio-recommendation-evidence?recommendation_id={recommendation_id}",
        headers=auth_headers(token_a),
    )
    assert ops_evidence.status_code == 200, ops_evidence.text
    ops_history = client.get("/ops/portfolio-recommendation-history", headers=auth_headers(token_a))
    assert ops_history.status_code == 200, ops_history.text


def test_portfolio_recommendation_classification_helpers() -> None:
    assert _classify_confidence(Decimal("76")) == "HIGH"
    assert _classify_confidence(Decimal("50")) == "MEDIUM"
    assert _classify_confidence(Decimal("49.99")) == "LOW"

    assert _classify_risk(6) == "HIGH"
    assert _classify_risk(3) == "MEDIUM"
    assert _classify_risk(2) == "LOW"

    assert _classify_strength(Decimal("78")) == "ELITE"
    assert _classify_strength(Decimal("58")) == "STRONG"
    assert _classify_strength(Decimal("35")) == "MODERATE"
    assert _classify_strength(Decimal("34.99")) == "WEAK"

    grade = SimpleNamespace(
        recommended_action="GRADE",
        expected_roi=Decimal("0.60"),
        liquidity_adjusted_roi=Decimal("0.55"),
    )
    assert (
        _select_action(
            fact=SimpleNamespace(),
            liquidity_bucket="HIGH",
            duplicate_status="HEALTHY",
            duplicate_action=None,
            strongest_copy=True,
            grading=grade,
            exposure_status="BALANCED",
            confidence_score=Decimal("70"),
            risk_level="LOW",
            sell_pressure_score=Decimal("0.10"),
        )
        == "GRADE_THEN_SELL"
    )
    assert (
        _select_action(
            fact=SimpleNamespace(),
            liquidity_bucket="ILLIQUID",
            duplicate_status="REDUNDANT",
            duplicate_action="SELL_DUPLICATES",
            strongest_copy=False,
            grading=None,
            exposure_status="OVEREXPOSED",
            confidence_score=Decimal("20"),
            risk_level="HIGH",
            sell_pressure_score=Decimal("-0.20"),
        )
        == "SELL"
    )
