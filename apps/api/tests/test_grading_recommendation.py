"""P37-06 deterministic grading recommendation tests."""

from __future__ import annotations

from datetime import date, timezone, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_grading_submission_batches import inventory_id_from_latest_order, make_ready_candidate
from test_inventory import auth_headers, register_and_login

from app.core.config import get_settings
from app.models import (
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingRecommendation,
    GradingRecommendationHistory,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    InventoryCopy,
    InventoryFmvSnapshot,
    InventoryLiquiditySnapshot,
    Listing,
    ListingIntelligenceSnapshot,
    Variant,
)
from app.services.grading_recommendation import deterministic_checksum


def _seed_recommendation_inputs(
    session: Session,
    *,
    inventory_id: int,
    candidate_id: int,
    grader: str = "PSA",
    target_grade: str = "9.8",
    roi_status: str = "STRONG",
    spread_status: str = "STRONG",
    liquidity_status: str = "HIGH",
    listing_status: str = "STRONG",
    stale_risk_flag: bool = False,
    estimated_roi: str = "1.25",
    liquidity_adjusted_roi: str = "0.95",
    estimated_net_profit: str = "85.00",
    estimated_total_cost: str = "45.00",
    average_roi_delta: str = "0.18000000",
    below_expectation_count: int = 1,
    above_expectation_count: int = 3,
) -> int:
    inventory = session.get(InventoryCopy, inventory_id)
    candidate = session.get(GradingCandidate, candidate_id)
    assert inventory is not None
    assert candidate is not None
    owner_user_id = int(candidate.owner_user_id)
    issue_id = int(session.exec(select(Variant.comic_issue_id).where(Variant.id == inventory.variant_id)).one())
    created_at = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    snapshot_date = date(2026, 5, 26)

    listing = Listing(
        owner_user_id=owner_user_id,
        canonical_comic_issue_id=issue_id,
        inventory_copy_id=inventory_id,
        source_type="manual",
        status="ACTIVE",
        title="Recommendation listing",
        description="Deterministic listing used for recommendation evidence.",
        condition_summary="Sharp corners and clean staples.",
        asking_price_amount="225.00",
        asking_price_currency="USD",
        quantity=1,
    )
    session.add(listing)
    session.flush()

    session.add(
        GradingRoiSnapshot(
            owner_user_id=owner_user_id,
            grading_candidate_id=candidate_id,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=issue_id,
            target_grader=grader,
            target_grade=target_grade,
            raw_fmv_amount=Decimal("100.00"),
            graded_fmv_amount=Decimal("230.00"),
            grading_fee_amount=Decimal("25.00"),
            shipping_cost_amount=Decimal("12.00"),
            insurance_cost_amount=Decimal("8.00"),
            estimated_turnaround_days=45,
            estimated_total_cost=Decimal(estimated_total_cost),
            estimated_spread_amount=Decimal("130.00"),
            estimated_net_profit=Decimal(estimated_net_profit),
            estimated_roi_pct=Decimal(estimated_roi),
            liquidity_adjusted_roi=Decimal(liquidity_adjusted_roi),
            break_even_grade="9.4",
            roi_status=roi_status,
            confidence_level="HIGH" if roi_status != "NEGATIVE" else "LOW",
            evidence_count=3,
            checksum=f"roi-{candidate_id}-{grader}-{target_grade}-{estimated_roi}",
            snapshot_date=snapshot_date,
            replay_key=None,
            generation_params_json={},
            created_at=created_at,
        )
    )
    session.add(
        GradingSpreadSnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=issue_id,
            target_grader=grader,
            target_grade=target_grade,
            raw_fmv_amount=Decimal("100.00"),
            graded_fmv_amount=Decimal("230.00"),
            grading_cost_amount=Decimal("45.00"),
            estimated_spread_amount=Decimal("130.00"),
            estimated_spread_pct=Decimal("1.30000000"),
            estimated_net_upside=Decimal("85.00"),
            liquidity_adjusted_upside=Decimal("77.00"),
            spread_status=spread_status,
            liquidity_modifier="POSITIVE" if liquidity_status == "HIGH" else "NEGATIVE",
            confidence_level="HIGH" if spread_status != "NEGATIVE" else "LOW",
            evidence_count=2,
            checksum=f"spread-{candidate_id}-{grader}-{target_grade}-{spread_status}",
            snapshot_date=snapshot_date,
            replay_key=None,
            generation_params_json={},
            created_at=created_at,
        )
    )
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=issue_id,
            channel="all",
            liquidity_status=liquidity_status,
            days_on_market_median=Decimal("18.00"),
            days_to_sale_median=Decimal("20.00"),
            sell_through_rate_pct=Decimal("72.00"),
            stale_listing_rate_pct=Decimal("8.00"),
            relist_rate_pct=Decimal("5.00"),
            successful_sale_count=12,
            failed_listing_count=2,
            active_listing_count=3,
            liquidity_confidence="HIGH" if liquidity_status == "HIGH" else "LOW",
            evaluation_window_days=365,
            snapshot_date=snapshot_date,
            checksum=f"liq-{candidate_id}-{liquidity_status}",
            evidence_count=4,
            created_at=created_at,
        )
    )
    session.add(
        ListingIntelligenceSnapshot(
            owner_user_id=owner_user_id,
            listing_id=int(listing.id or 0),
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=issue_id,
            channel="ebay",
            replay_key=None,
            intelligence_status=listing_status,
            completeness_score=Decimal("92.00"),
            image_score=Decimal("20.00"),
            title_score=Decimal("20.00"),
            description_score=Decimal("20.00"),
            pricing_score=Decimal("15.00"),
            export_readiness_score=Decimal("95.00"),
            sale_outcome_score=Decimal("70.00"),
            stale_risk_flag=stale_risk_flag,
            missing_required_fields_json=[],
            warning_flags_json=[],
            evidence_count=5,
            checksum=f"listing-{candidate_id}-{listing_status}-{stale_risk_flag}",
            snapshot_date=snapshot_date,
            created_at=created_at,
        )
    )
    session.add(
        GraderPerformanceSnapshot(
            owner_user_id=owner_user_id,
            grader=grader,
            submission_count=5,
            above_expectation_count=above_expectation_count,
            met_expectation_count=1,
            below_expectation_count=below_expectation_count,
            average_roi_delta=Decimal(average_roi_delta),
            average_turnaround_days=Decimal("42.00"),
            checksum=f"perf-{candidate_id}-{grader}-{below_expectation_count}",
            snapshot_date=snapshot_date,
            created_at=created_at,
        )
    )
    session.commit()
    return owner_user_id


def test_checksum_is_deterministic() -> None:
    payload = {"candidate": 1, "grader": "PSA", "score": "88.00"}
    assert deterministic_checksum(payload) == deterministic_checksum(payload)


def test_generate_grade_recommendation_and_evidence(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "recommend-grade@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="PSA")
    _seed_recommendation_inputs(session, inventory_id=inventory_id, candidate_id=candidate_id, grader="PSA")

    rsp = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id, "replay_key": "rec-grade-001"},
    )
    assert rsp.status_code == 201, rsp.text
    payload = rsp.json()
    rec = payload["recommendation"]
    assert rec["recommended_action"] == "GRADE"
    assert rec["recommended_grader"] == "PSA"
    assert rec["risk_level"] == "LOW"
    assert Decimal(rec["confidence_score"]) >= Decimal("80.00")
    evidence_types = {row["evidence_type"] for row in payload["evidence"]}
    assert {"ROI_ENGINE", "SPREAD_ENGINE", "LIQUIDITY", "GRADER_PERFORMANCE", "LISTING_INTELLIGENCE"} <= evidence_types
    assert [row["scenario_name"] for row in payload["scenarios"]] == ["pessimistic", "baseline", "optimistic"]


def test_negative_roi_becomes_not_recommended_high_risk(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "recommend-negative@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="CBCS")
    _seed_recommendation_inputs(
        session,
        inventory_id=inventory_id,
        candidate_id=candidate_id,
        grader="CBCS",
        roi_status="NEGATIVE",
        spread_status="NEGATIVE",
        liquidity_status="LOW",
        listing_status="WEAK",
        stale_risk_flag=True,
        estimated_roi="-0.35",
        liquidity_adjusted_roi="-0.40",
        estimated_net_profit="-18.00",
        average_roi_delta="-0.22000000",
        below_expectation_count=4,
        above_expectation_count=0,
    )

    rsp = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id},
    )
    assert rsp.status_code == 201, rsp.text
    rec = rsp.json()["recommendation"]
    assert rec["recommended_action"] == "NOT_RECOMMENDED"
    assert rec["risk_level"] == "HIGH"
    assert "poor_grader_performance" in rec["warning_flags_json"]


def test_replay_safe_generation_history_and_no_inventory_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "recommend-history@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="CGC")
    inventory = session.get(InventoryCopy, inventory_id)
    assert inventory is not None
    before_fmv = inventory.current_fmv
    before_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    _seed_recommendation_inputs(session, inventory_id=inventory_id, candidate_id=candidate_id, grader="CGC")

    first = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id, "replay_key": "rec-history-001"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id, "replay_key": "rec-history-001"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["recommendation"]["id"] == first.json()["recommendation"]["id"]

    session.add(
        GradingRoiSnapshot(
            owner_user_id=first.json()["recommendation"]["owner_user_id"],
            grading_candidate_id=candidate_id,
            inventory_item_id=inventory_id,
            canonical_comic_issue_id=first.json()["recommendation"]["canonical_comic_issue_id"],
            target_grader="CGC",
            target_grade="9.8",
            raw_fmv_amount=Decimal("100.00"),
            graded_fmv_amount=Decimal("120.00"),
            grading_fee_amount=Decimal("25.00"),
            shipping_cost_amount=Decimal("12.00"),
            insurance_cost_amount=Decimal("8.00"),
            estimated_turnaround_days=45,
            estimated_total_cost=Decimal("45.00"),
            estimated_spread_amount=Decimal("20.00"),
            estimated_net_profit=Decimal("-5.00"),
            estimated_roi_pct=Decimal("-0.10000000"),
            liquidity_adjusted_roi=Decimal("-0.15000000"),
            break_even_grade="10.0",
            roi_status="NEGATIVE",
            confidence_level="HIGH",
            evidence_count=3,
            checksum="roi-history-newer",
            snapshot_date=date(2026, 5, 27),
            replay_key=None,
            generation_params_json={"reason": "shift"},
        )
    )
    session.commit()

    third = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id, "replay_key": "rec-history-002", "snapshot_date": "2026-05-27"},
    )
    assert third.status_code == 201, third.text
    assert third.json()["recommendation"]["id"] != first.json()["recommendation"]["id"]

    session.expire_all()
    inventory_after = session.get(InventoryCopy, inventory_id)
    assert inventory_after is not None
    assert inventory_after.current_fmv == before_fmv
    after_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    assert len(after_fmv_snapshots) == len(before_fmv_snapshots)

    histories = session.exec(
        select(GradingRecommendationHistory).where(GradingRecommendationHistory.inventory_item_id == inventory_id)
    ).all()
    assert len(histories) == 2
    rows = session.exec(
        select(GradingRecommendation).where(GradingRecommendation.inventory_item_id == inventory_id)
    ).all()
    assert any(row.recommendation_status == "SUPERSEDED" for row in rows)
    assert any(row.recommendation_status == "ACTIVE" for row in rows)


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "recommend-scope-owner@example.com")
    other = register_and_login(client, "recommend-scope-other@example.com")
    admin = register_and_login(client, "recommend-scope-admin@example.com")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "recommend-scope-admin@example.com")
    get_settings.cache_clear()

    owner_inventory = inventory_id_from_latest_order(client, owner)
    other_inventory = inventory_id_from_latest_order(client, other)
    owner_candidate = make_ready_candidate(client, owner, owner_inventory, target_grader="PSA")
    other_candidate = make_ready_candidate(client, other, other_inventory, target_grader="CGC")
    owner_user_id = _seed_recommendation_inputs(session, inventory_id=owner_inventory, candidate_id=owner_candidate, grader="PSA")
    _seed_recommendation_inputs(session, inventory_id=other_inventory, candidate_id=other_candidate, grader="CGC")

    owner_rec = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(owner),
        json={"grading_candidate_id": owner_candidate},
    )
    assert owner_rec.status_code == 201, owner_rec.text
    other_rec = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(other),
        json={"grading_candidate_id": other_candidate},
    )
    assert other_rec.status_code == 201, other_rec.text

    miss = client.get(
        f"/grading-recommendations/{owner_rec.json()['recommendation']['id']}",
        headers=auth_headers(other),
    )
    assert miss.status_code == 404

    ops_list = client.get(
        "/ops/grading-recommendations",
        params={"owner_user_id": owner_user_id},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    assert ops_list.json()["total_items"] >= 1

    ops_history = client.get(
        "/ops/grading-recommendation-history",
        params={"owner_user_id": owner_user_id},
        headers=auth_headers(admin),
    )
    assert ops_history.status_code == 200, ops_history.text
    assert ops_history.json()["total_items"] >= 1
