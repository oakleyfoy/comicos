"""P37-03 deterministic grading ROI intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_inventory import auth_headers, create_order, register_and_login

from app.core.config import get_settings
from app.models import (
    GradingRoiEvidence,
    GradingRoiHistory,
    GradingRoiSnapshot,
    InventoryCopy,
    InventoryFmvSnapshot,
    InventoryLiquiditySnapshot,
    MarketFmvSnapshot,
    Variant,
)
from app.services.grading_roi import _break_even_grade, _liquidity_modifier, _money, _roi_status, deterministic_checksum


def inventory_id_from_latest_order(client: TestClient, token: str) -> int:
    rsp = create_order(client, token)
    order_id = rsp["order_id"]
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    return detail.json()["items"][0]["inventory_copy_ids"][0]


def seed_roi_inputs(
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
            metadata_identity_key=f"roi-inv-{inventory_id}",
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


def test_pure_calculations_status_break_even_and_checksum() -> None:
    assert _money(Decimal("12.345")) == Decimal("12.35")
    assert deterministic_checksum({"a": 1, "b": Decimal("2.50")}) == deterministic_checksum(
        {"b": Decimal("2.50"), "a": 1}
    )
    assert _liquidity_modifier("HIGH") == ("HIGH", Decimal("1.00"))
    assert _liquidity_modifier("MODERATE") == ("MEDIUM", Decimal("0.85"))
    assert _liquidity_modifier("ILLIQUID") == ("LOW", Decimal("0.65"))
    assert (
        _break_even_grade(
            target_grader="PSA",
            target_grade="9.4",
            raw_fmv_amount=Decimal("100.00"),
            graded_fmv_amount=Decimal("120.00"),
            total_cost_amount=Decimal("30.00"),
        )
        == "9.8"
    )
    assert (
        _roi_status(
            estimated_net_profit=Decimal("-1.00"),
            estimated_roi_pct=Decimal("-0.01"),
            liquidity_adjusted_roi=Decimal("-0.01"),
            liquidity_weight=Decimal("1.00"),
            confidence_level="LOW",
            evidence_count=3,
            has_raw=True,
            has_graded=True,
            has_liquidity=True,
        )
        == "NEGATIVE"
    )
    assert (
        _roi_status(
            estimated_net_profit=Decimal("80.00"),
            estimated_roi_pct=Decimal("1.60"),
            liquidity_adjusted_roi=Decimal("1.60"),
            liquidity_weight=Decimal("1.00"),
            confidence_level="HIGH",
            evidence_count=5,
            has_raw=True,
            has_graded=True,
            has_liquidity=True,
        )
        == "ELITE"
    )


def test_generate_roi_replay_history_and_evidence(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "roi-owner@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    issue_id = seed_roi_inputs(
        session,
        inventory_id=inventory_id,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="CGC",
        target_grade="9.8",
        liquidity_status="HIGH",
    )

    spread_rsp = client.post(
        "/grading-spreads/generate",
        json={
            "inventory_item_id": inventory_id,
            "canonical_comic_issue_id": issue_id,
            "target_grader": "CGC",
            "target_grade": "9.8",
            "replay_key": "roi-spread-seed",
        },
        headers=auth_headers(token),
    )
    assert spread_rsp.status_code == 201, spread_rsp.text

    candidate_rsp = client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": inventory_id,
            "target_grader": "CGC",
            "target_grade": "9.8",
            "candidate_priority": "HIGH",
            "estimated_raw_value": "100.00",
            "estimated_graded_value": "220.00",
            "estimated_grading_cost": "55.00",
            "estimated_roi": "1.18",
            "rationale": "manual estimate",
            "replay_key": "roi-candidate-seed",
        },
        headers=auth_headers(token),
    )
    assert candidate_rsp.status_code in (200, 201), candidate_rsp.text
    candidate_id = candidate_rsp.json()["candidate"]["id"]

    payload = {
        "grading_candidate_id": candidate_id,
        "inventory_item_id": inventory_id,
        "canonical_comic_issue_id": issue_id,
        "target_grader": "CGC",
        "target_grade": "9.8",
        "replay_key": "roi-rk-001",
    }
    first = client.post("/grading-roi/generate", json=payload, headers=auth_headers(token))
    assert first.status_code == 201, first.text
    first_json = first.json()
    assert first_json["snapshot"]["roi_status"] == "STRONG"
    assert first_json["snapshot"]["estimated_total_cost"] == "55.00"
    assert first_json["snapshot"]["estimated_net_profit"] == "65.00"
    assert len(first_json["scenarios"]) == 3
    scenario_names = {row["scenario_name"] for row in first_json["scenarios"]}
    assert scenario_names == {"pessimistic", "baseline", "optimistic"}
    baseline = next(row for row in first_json["scenarios"] if row["scenario_name"] == "baseline")
    assert baseline["estimated_roi_pct"] == first_json["snapshot"]["estimated_roi_pct"]
    evidence_types = {row["evidence_type"] for row in first_json["evidence"]}
    assert {"FMV", "FEE_SCHEDULE", "LIQUIDITY", "MANUAL_OVERRIDE", "SPREAD_ENGINE"}.issubset(evidence_types)
    assert len(first_json["history"]) == 1

    second = client.post("/grading-roi/generate", json=payload, headers=auth_headers(token))
    assert second.status_code == 200, second.text
    second_json = second.json()
    assert second_json["snapshot"]["id"] == first_json["snapshot"]["id"]
    assert second_json["snapshot"]["checksum"] == first_json["snapshot"]["checksum"]

    db_row = session.get(GradingRoiSnapshot, first_json["snapshot"]["id"])
    assert db_row is not None
    assert db_row.checksum == first_json["snapshot"]["checksum"]
    histories = session.exec(select(GradingRoiHistory)).all()
    assert len(histories) == 1
    evidence_rows = session.exec(select(GradingRoiEvidence)).all()
    assert len(evidence_rows) >= 5

    detail_one = client.get(f"/grading-roi/{db_row.id}", headers=auth_headers(token))
    detail_two = client.get(f"/grading-roi/{db_row.id}", headers=auth_headers(token))
    assert detail_one.status_code == 200
    assert detail_two.status_code == 200
    assert detail_one.json()["snapshot"]["checksum"] == detail_two.json()["snapshot"]["checksum"]


def test_liquidity_adjustment_changes_roi_and_no_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "roi-liquidity@example.com")
    high_inventory = inventory_id_from_latest_order(client, token)
    low_inventory = inventory_id_from_latest_order(client, token)

    high_issue = seed_roi_inputs(
        session,
        inventory_id=high_inventory,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="PSA",
        target_grade="9.8",
        liquidity_status="HIGH",
    )
    low_issue = seed_roi_inputs(
        session,
        inventory_id=low_inventory,
        raw_fmv=Decimal("100.00"),
        graded_fmv=Decimal("220.00"),
        target_grader="PSA",
        target_grade="9.8",
        liquidity_status="LOW",
    )

    before_inventory = session.get(InventoryCopy, high_inventory)
    assert before_inventory is not None
    before_fmv = before_inventory.current_fmv
    before_fmv_row_count = len(session.exec(select(InventoryFmvSnapshot)).all())

    high = client.post(
        "/grading-roi/generate",
        json={
            "inventory_item_id": high_inventory,
            "canonical_comic_issue_id": high_issue,
            "target_grader": "PSA",
            "target_grade": "9.8",
            "replay_key": "roi-high",
        },
        headers=auth_headers(token),
    )
    low = client.post(
        "/grading-roi/generate",
        json={
            "inventory_item_id": low_inventory,
            "canonical_comic_issue_id": low_issue,
            "target_grader": "PSA",
            "target_grade": "9.8",
            "replay_key": "roi-low",
        },
        headers=auth_headers(token),
    )
    assert high.status_code == 201, high.text
    assert low.status_code == 201, low.text
    assert Decimal(high.json()["snapshot"]["liquidity_adjusted_roi"]) > Decimal(
        low.json()["snapshot"]["liquidity_adjusted_roi"]
    )

    session.expire_all()
    after_inventory = session.get(InventoryCopy, high_inventory)
    assert after_inventory is not None
    assert after_inventory.current_fmv == before_fmv
    assert len(session.exec(select(InventoryFmvSnapshot)).all()) == before_fmv_row_count


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "roi-owner-scope@example.com")
    other = register_and_login(client, "roi-other-scope@example.com")
    admin = register_and_login(client, "roi-admin@example.com")

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "roi-admin@example.com")
    get_settings.cache_clear()

    owner_inventory = inventory_id_from_latest_order(client, owner)
    other_inventory = inventory_id_from_latest_order(client, other)
    owner_issue = seed_roi_inputs(
        session=session,
        inventory_id=owner_inventory,
        raw_fmv=Decimal("110.00"),
        graded_fmv=Decimal("250.00"),
        target_grader="CBCS",
        target_grade="9.8",
        liquidity_status="HIGH",
    )
    _ = seed_roi_inputs(
        session=session,
        inventory_id=other_inventory,
        raw_fmv=Decimal("90.00"),
        graded_fmv=Decimal("130.00"),
        target_grader="CBCS",
        target_grade="9.8",
        liquidity_status="LOW",
    )

    owner_rsp = client.post(
        "/grading-roi/generate",
        json={
            "inventory_item_id": owner_inventory,
            "canonical_comic_issue_id": owner_issue,
            "target_grader": "CBCS",
            "target_grade": "9.8",
            "replay_key": "roi-owner-scope",
        },
        headers=auth_headers(owner),
    )
    assert owner_rsp.status_code == 201, owner_rsp.text
    roi_id = owner_rsp.json()["snapshot"]["id"]

    miss = client.get(f"/grading-roi/{roi_id}", headers=auth_headers(other))
    assert miss.status_code == 404

    owner_row = session.get(InventoryCopy, owner_inventory)
    assert owner_row is not None
    ops_list = client.get(
        "/ops/grading-roi",
        params={"owner_user_id": owner_row.user_id},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    ops_json = ops_list.json()
    assert ops_json["total_items"] >= 1

    ops_get = client.get(f"/ops/grading-roi/{roi_id}", headers=auth_headers(admin))
    assert ops_get.status_code == 200, ops_get.text
