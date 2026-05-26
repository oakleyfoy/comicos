"""P37-07 deterministic grading risk tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_grading_recommendation import _seed_recommendation_inputs
from test_grading_submission_batches import inventory_id_from_latest_order, make_ready_candidate
from test_inventory import auth_headers, register_and_login

from app.core.config import get_settings
from app.models import ConfidenceFactorSnapshot, GradingRecommendation, GradingRiskSnapshot, InventoryCopy, InventoryFmvSnapshot
from app.services.grading_risk import deterministic_checksum


def _generate_recommendation(client: TestClient, token: str, candidate_id: int, replay_key: str = "risk-rec-001") -> dict:
    rsp = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={"grading_candidate_id": candidate_id, "replay_key": replay_key},
    )
    assert rsp.status_code == 201, rsp.text
    return rsp.json()


def test_grading_risk_checksum_is_deterministic() -> None:
    payload = {"candidate": 7, "risk": "HIGH", "weight": "0.55000000"}
    assert deterministic_checksum(payload) == deterministic_checksum(payload)


def test_generate_risk_snapshot_and_recommendation_integration(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "risk-owner@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="PSA")
    _seed_recommendation_inputs(session, inventory_id=inventory_id, candidate_id=candidate_id, grader="PSA")
    recommendation = _generate_recommendation(client, token, candidate_id)

    rsp = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={"recommendation_id": recommendation["recommendation"]["id"], "replay_key": "risk-rk-001"},
    )
    assert rsp.status_code == 201, rsp.text
    payload = rsp.json()
    snapshot = payload["snapshot"]
    assert snapshot["overall_risk_level"] in {"LOW", "MEDIUM"}
    assert snapshot["overall_confidence_level"] in {"MEDIUM", "HIGH"}
    assert snapshot["risk_adjusted_roi"] is not None
    assert snapshot["confidence_weight"] is not None
    factor_keys = {row["factor_key"] for row in payload["confidence_factors"]}
    assert factor_keys == {
        "liquidity_stability",
        "spread_stability",
        "roi_stability",
        "grader_consistency",
        "market_depth",
        "evidence_volume",
        "reconciliation_history",
    }
    rec_detail = client.get(
        f"/grading-recommendations/{recommendation['recommendation']['id']}",
        headers=auth_headers(token),
    )
    assert rec_detail.status_code == 200, rec_detail.text
    rec_payload = rec_detail.json()["recommendation"]
    assert rec_payload["grading_risk_snapshot_id"] == snapshot["id"]
    assert rec_payload["risk_adjusted_roi"] == snapshot["risk_adjusted_roi"]
    assert rec_payload["overall_confidence_level"] in {"MEDIUM", "HIGH"}


def test_extreme_risk_classification_and_factor_weighting(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "risk-extreme@example.com")
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
        estimated_roi="-0.40",
        liquidity_adjusted_roi="-0.45",
        estimated_net_profit="-22.00",
        average_roi_delta="-0.25000000",
        below_expectation_count=4,
        above_expectation_count=0,
    )
    recommendation = _generate_recommendation(client, token, candidate_id, replay_key="risk-rec-extreme")

    rsp = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={"recommendation_id": recommendation["recommendation"]["id"]},
    )
    assert rsp.status_code == 201, rsp.text
    snapshot = rsp.json()["snapshot"]
    assert snapshot["overall_risk_level"] in {"HIGH", "EXTREME"}
    assert snapshot["overall_confidence_level"] in {"LOW", "MEDIUM"}
    assert "poor_grader_consistency" in snapshot["warning_flags_json"]
    factors = rsp.json()["confidence_factors"]
    weighting_sum = sum(Decimal(row["weighting"]) for row in factors)
    assert weighting_sum == Decimal("1.00000000")


def test_replay_safe_generation_history_and_no_inventory_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "risk-history@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="CGC")
    inventory = session.get(InventoryCopy, inventory_id)
    assert inventory is not None
    before_fmv = inventory.current_fmv
    before_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    _seed_recommendation_inputs(session, inventory_id=inventory_id, candidate_id=candidate_id, grader="CGC")
    recommendation = _generate_recommendation(client, token, candidate_id, replay_key="risk-history-rec")

    first = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={"recommendation_id": recommendation["recommendation"]["id"], "replay_key": "risk-history-001"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={"recommendation_id": recommendation["recommendation"]["id"], "replay_key": "risk-history-001"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["snapshot"]["id"] == first.json()["snapshot"]["id"]

    third = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={
            "recommendation_id": recommendation["recommendation"]["id"],
            "replay_key": "risk-history-002",
            "snapshot_date": "2026-05-27",
        },
    )
    assert third.status_code == 201, third.text
    assert third.json()["snapshot"]["id"] != first.json()["snapshot"]["id"]

    session.expire_all()
    inventory_after = session.get(InventoryCopy, inventory_id)
    assert inventory_after is not None
    assert inventory_after.current_fmv == before_fmv
    after_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    assert len(after_fmv_snapshots) == len(before_fmv_snapshots)


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "risk-scope-owner@example.com")
    other = register_and_login(client, "risk-scope-other@example.com")
    admin = register_and_login(client, "risk-scope-admin@example.com")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "risk-scope-admin@example.com")
    get_settings.cache_clear()

    owner_inventory = inventory_id_from_latest_order(client, owner)
    other_inventory = inventory_id_from_latest_order(client, other)
    owner_candidate = make_ready_candidate(client, owner, owner_inventory, target_grader="PSA")
    other_candidate = make_ready_candidate(client, other, other_inventory, target_grader="CGC")
    _seed_recommendation_inputs(session, inventory_id=owner_inventory, candidate_id=owner_candidate, grader="PSA")
    _seed_recommendation_inputs(session, inventory_id=other_inventory, candidate_id=other_candidate, grader="CGC")
    owner_rec = _generate_recommendation(client, owner, owner_candidate, replay_key="risk-scope-owner-rec")
    other_rec = _generate_recommendation(client, other, other_candidate, replay_key="risk-scope-other-rec")

    owner_risk = client.post(
        "/grading-risk/generate",
        headers=auth_headers(owner),
        json={"recommendation_id": owner_rec["recommendation"]["id"]},
    )
    assert owner_risk.status_code == 201, owner_risk.text
    other_risk = client.post(
        "/grading-risk/generate",
        headers=auth_headers(other),
        json={"recommendation_id": other_rec["recommendation"]["id"]},
    )
    assert other_risk.status_code == 201, other_risk.text

    miss = client.get(f"/grading-risk/{owner_risk.json()['snapshot']['id']}", headers=auth_headers(other))
    assert miss.status_code == 404

    ops_list = client.get(
        "/ops/grading-risk",
        params={"owner_user_id": owner_rec["recommendation"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    assert ops_list.json()["total_items"] >= 1

    ops_factors = client.get(
        "/ops/grading-confidence-factors",
        params={"owner_user_id": owner_rec["recommendation"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_factors.status_code == 200, ops_factors.text
    assert ops_factors.json()["total_items"] >= 1

    snapshots = session.exec(select(GradingRiskSnapshot)).all()
    assert len(snapshots) >= 2
    factors = session.exec(select(ConfidenceFactorSnapshot)).all()
    assert len(factors) >= 7
