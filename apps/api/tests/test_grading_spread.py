"""P37-02 deterministic raw-vs-graded spread tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_inventory import auth_headers, create_order, register_and_login

from app.models import (
    GradingSpreadEvidence,
    GradingSpreadHistory,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryFmvSnapshot,
    InventoryLiquiditySnapshot,
    MarketFmvSnapshot,
    Variant,
)
from app.services.grading_spread import _liquidity_modifier, _money, _spread_status, deterministic_checksum


def inventory_id_from_latest_order(client: TestClient, token: str) -> int:
    rsp = create_order(client, token)
    order_id = rsp["order_id"]
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    return detail.json()["items"][0]["inventory_copy_ids"][0]


def seed_spread_inputs(
    session: Session,
    *,
    inventory_id: int,
    raw_fmv: Decimal,
    graded_fmv: Decimal,
    target_grader: str,
    target_grade: str,
    liquidity_status: str,
) -> int:
    inventory = session.get(InventoryCopy, inventory_id)
    assert inventory is not None
    issue_id = int(session.exec(select(Variant.comic_issue_id).where(Variant.id == inventory.variant_id)).one())
    session.add(
        InventoryFmvSnapshot(
            inventory_copy_id=inventory_id,
            new_fmv=raw_fmv,
            changed_at=datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc),
            source="manual",
        )
    )
    session.add(
        MarketFmvSnapshot(
            canonical_issue_id=issue_id,
            metadata_identity_key=f"inv-{inventory_id}",
            snapshot_scope="graded",
            grading_company=target_grader,
            normalized_grade=target_grade,
            currency_code="USD",
            snapshot_date=date(2026, 5, 25),
            comp_count=5,
            valuation_method="weighted_recent_sales",
            estimated_fmv=graded_fmv,
            confidence_bucket="high",
            liquidity_bucket="high",
            volatility_bucket="stable",
            stale_data=False,
            evidence_json={"seed": inventory_id},
        )
    )
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=int(inventory.user_id),
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=issue_id,
            channel=None,
            liquidity_status=liquidity_status,
            days_on_market_median=Decimal("9.00"),
            days_to_sale_median=Decimal("5.00"),
            sell_through_rate_pct=Decimal("75.00"),
            stale_listing_rate_pct=Decimal("5.00"),
            relist_rate_pct=Decimal("0.00"),
            successful_sale_count=6,
            failed_listing_count=1,
            active_listing_count=0,
            liquidity_confidence="HIGH" if liquidity_status == "HIGH" else "LOW",
            evaluation_window_days=365,
            snapshot_date=date(2026, 5, 25),
            checksum=f"liq-{inventory_id}",
            evidence_count=3,
        )
    )
    session.commit()
    return issue_id


def test_pure_calculations_and_classification() -> None:
    assert _money(Decimal("12.345")) == Decimal("12.35")
    assert deterministic_checksum({"a": 1, "b": Decimal("2.50")}) == deterministic_checksum({"b": Decimal("2.50"), "a": 1})
    assert _liquidity_modifier("HIGH") == ("HIGH", Decimal("1.00"))
    assert _liquidity_modifier("MODERATE") == ("MEDIUM", Decimal("0.85"))
    assert _liquidity_modifier("ILLIQUID") == ("LOW", Decimal("0.65"))
    assert (
        _spread_status(
            estimated_spread_amount=Decimal("80.00"),
            estimated_net_upside=Decimal("65.00"),
            estimated_spread_pct=Decimal("40.00"),
            liquidity_modifier="HIGH",
            confidence_level="HIGH",
            has_raw=True,
            has_graded=True,
            has_liquidity=True,
        )
        == "STRONG"
    )
    assert (
        _spread_status(
            estimated_spread_amount=Decimal("-5.00"),
            estimated_net_upside=Decimal("-10.00"),
            estimated_spread_pct=Decimal("-5.00"),
            liquidity_modifier="LOW",
            confidence_level="LOW",
            has_raw=True,
            has_graded=True,
            has_liquidity=True,
        )
        == "NEGATIVE"
    )


def test_generate_spread_replay_history_and_evidence(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "spread-owner@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    issue_id = seed_spread_inputs(
        session,
        inventory_id=inventory_id,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="CGC",
        target_grade="9.8",
        liquidity_status="HIGH",
    )

    body = {
        "inventory_item_id": inventory_id,
        "canonical_comic_issue_id": issue_id,
        "target_grader": "CGC",
        "target_grade": "9.8",
        "replay_key": "spread-rk-001",
    }
    first = client.post("/grading-spreads/generate", json=body, headers=auth_headers(token))
    assert first.status_code == 201, first.text
    first_json = first.json()
    assert first_json["snapshot"]["spread_status"] == "STRONG"
    assert first_json["snapshot"]["estimated_spread_amount"] == "120.00"
    assert first_json["snapshot"]["estimated_net_upside"] == "90.00"
    assert len(first_json["evidence"]) >= 3
    evidence_types = {row["evidence_type"] for row in first_json["evidence"]}
    assert {"RAW_FMV", "GRADED_FMV", "LIQUIDITY"}.issubset(evidence_types)
    assert len(first_json["history"]) == 1

    second = client.post("/grading-spreads/generate", json=body, headers=auth_headers(token))
    assert second.status_code == 200, second.text
    second_json = second.json()
    assert second_json["snapshot"]["id"] == first_json["snapshot"]["id"]
    assert second_json["snapshot"]["checksum"] == first_json["snapshot"]["checksum"]
    assert second_json["snapshot"]["liquidity_adjusted_upside"] == "90.00"

    db_row = session.get(GradingSpreadSnapshot, first_json["snapshot"]["id"])
    assert db_row is not None
    assert db_row.checksum == first_json["snapshot"]["checksum"]

    histories = session.exec(select(GradingSpreadHistory)).all()
    assert len(histories) == 1
    evidence_rows = session.exec(select(GradingSpreadEvidence)).all()
    assert len(evidence_rows) >= 3


def test_liquidity_weighting_changes_adjusted_upside(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "spread-liquidity@example.com")
    high_inventory = inventory_id_from_latest_order(client, token)
    low_inventory = inventory_id_from_latest_order(client, token)

    high_issue = seed_spread_inputs(
        session,
        inventory_id=high_inventory,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="PSA",
        target_grade="9.8",
        liquidity_status="HIGH",
    )
    low_issue = seed_spread_inputs(
        session,
        inventory_id=low_inventory,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="PSA",
        target_grade="9.8",
        liquidity_status="LOW",
    )

    high = client.post(
        "/grading-spreads/generate",
        json={
            "inventory_item_id": high_inventory,
            "canonical_comic_issue_id": high_issue,
            "target_grader": "PSA",
            "target_grade": "9.8",
            "replay_key": "spread-high",
        },
        headers=auth_headers(token),
    )
    low = client.post(
        "/grading-spreads/generate",
        json={
            "inventory_item_id": low_inventory,
            "canonical_comic_issue_id": low_issue,
            "target_grader": "PSA",
            "target_grade": "9.8",
            "replay_key": "spread-low",
        },
        headers=auth_headers(token),
    )
    assert high.status_code == 201
    assert low.status_code == 201
    assert Decimal(high.json()["snapshot"]["liquidity_adjusted_upside"]) > Decimal(low.json()["snapshot"]["liquidity_adjusted_upside"])


def test_owner_scoping_ops_visibility_and_no_inventory_mutation(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "spread-owner-2@example.com")
    other = register_and_login(client, "spread-other@example.com")
    inventory_id = inventory_id_from_latest_order(client, owner)
    issue_id = seed_spread_inputs(
        session,
        inventory_id=inventory_id,
        raw_fmv=Decimal("110.00"),
        graded_fmv=Decimal("200.00"),
        target_grader="CBCS",
        target_grade="9.8",
        liquidity_status="HIGH",
    )
    before = session.get(InventoryCopy, inventory_id)
    assert before is not None
    before_fmv = before.current_fmv

    create_rsp = client.post(
        "/grading-spreads/generate",
        json={
            "inventory_item_id": inventory_id,
            "canonical_comic_issue_id": issue_id,
            "target_grader": "CBCS",
            "target_grade": "9.8",
            "replay_key": "spread-scope",
        },
        headers=auth_headers(owner),
    )
    assert create_rsp.status_code == 201, create_rsp.text
    spread_id = create_rsp.json()["snapshot"]["id"]

    miss = client.get(f"/grading-spreads/{spread_id}", headers=auth_headers(other))
    assert miss.status_code == 404
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "spread-admin@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert client.get("/ops/grading-spreads", headers=auth_headers(other)).status_code == 403
    admin = register_and_login(client, "spread-admin@example.com")
    ops_rsp = client.get("/ops/grading-spreads", headers=auth_headers(admin))
    assert ops_rsp.status_code == 200, ops_rsp.text

    session.expire_all()
    after = session.get(InventoryCopy, inventory_id)
    assert after is not None
    assert after.current_fmv == before_fmv
