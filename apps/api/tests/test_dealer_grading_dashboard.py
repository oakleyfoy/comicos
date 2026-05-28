"""P37-08 deterministic dealer grading dashboard tests."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_grading_reconciliation import complete_submission_batch
from test_grading_recommendation import _seed_recommendation_inputs
from test_grading_submission_batches import create_submission_batch, inventory_id_from_latest_order, make_ready_candidate
from test_inventory import auth_headers, register_and_login

from app.core.config import get_settings
from app.models import (
    DealerGradingDashboardAlert,
    DealerGradingDashboardFeedEvent,
    DealerGradingDashboardMetric,
    DealerGradingDashboardSnapshot,
    GradingRecommendation,
    GradingRiskSnapshot,
    GradingSubmissionBatch,
    GradingSubmissionItem,
    GradingReconciliationRecord,
)

# Dashboard tests aggregate rows with snapshot_date <= this date; seeded rec/risk must match.
DASHBOARD_SNAPSHOT_DATE = "2026-05-26"


def _generate_recommendation(
    client: TestClient,
    token: str,
    candidate_id: int,
    replay_key: str,
) -> dict:
    rsp = client.post(
        "/grading-recommendations/generate",
        headers=auth_headers(token),
        json={
            "grading_candidate_id": candidate_id,
            "replay_key": replay_key,
            "snapshot_date": DASHBOARD_SNAPSHOT_DATE,
        },
    )
    assert rsp.status_code == 201, rsp.text
    return rsp.json()


def _generate_risk(client: TestClient, token: str, recommendation_id: int, replay_key: str) -> dict:
    rsp = client.post(
        "/grading-risk/generate",
        headers=auth_headers(token),
        json={
            "recommendation_id": recommendation_id,
            "replay_key": replay_key,
            "snapshot_date": DASHBOARD_SNAPSHOT_DATE,
        },
    )
    assert rsp.status_code == 201, rsp.text
    return rsp.json()


def _seed_dashboard_fixture(client: TestClient, session: Session, token: str) -> dict[str, int]:
    elite_inventory = inventory_id_from_latest_order(client, token)
    elite_candidate = make_ready_candidate(client, token, elite_inventory, target_grader="PSA")
    _seed_recommendation_inputs(session, inventory_id=elite_inventory, candidate_id=elite_candidate, grader="PSA")
    elite_rec_payload = _generate_recommendation(client, token, elite_candidate, replay_key="dashboard-elite-rec")
    elite_rec_id = int(elite_rec_payload["recommendation"]["id"])
    elite_risk_payload = _generate_risk(client, token, elite_rec_id, replay_key="dashboard-elite-risk")
    _ = elite_risk_payload
    elite_rec = session.get(GradingRecommendation, elite_rec_id)
    assert elite_rec is not None
    elite_rec.recommendation_strength = "ELITE"
    session.add(elite_rec)
    session.commit()

    risk_inventory = inventory_id_from_latest_order(client, token)
    risk_candidate = make_ready_candidate(client, token, risk_inventory, target_grader="CBCS")
    _seed_recommendation_inputs(
        session,
        inventory_id=risk_inventory,
        candidate_id=risk_candidate,
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
    risk_rec_payload = _generate_recommendation(client, token, risk_candidate, replay_key="dashboard-risk-rec")
    risk_rec_id = int(risk_rec_payload["recommendation"]["id"])
    risk_payload = _generate_risk(client, token, risk_rec_id, replay_key="dashboard-risk-risk")
    risk_snapshot_id = int(risk_payload["snapshot"]["id"])
    risk_rec = session.get(GradingRecommendation, risk_rec_id)
    risk_snapshot = session.get(GradingRiskSnapshot, risk_snapshot_id)
    assert risk_rec is not None
    assert risk_snapshot is not None
    risk_rec.evidence_count = 1
    risk_snapshot.overall_risk_level = "HIGH"
    risk_snapshot.overall_confidence_level = "LOW"
    risk_snapshot.evidence_count = 1
    session.add(risk_rec)
    session.add(risk_snapshot)
    session.commit()

    delayed_batch = create_submission_batch(client, token, [risk_candidate], replay_key="dashboard-delayed-batch")
    delayed_batch_id = int(delayed_batch["batch"]["id"])
    assert client.post(f"/grading-submission-batches/{delayed_batch_id}/ready", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{delayed_batch_id}/ship", headers=auth_headers(token)).status_code == 200
    delayed_row = session.get(GradingSubmissionBatch, delayed_batch_id)
    assert delayed_row is not None
    delayed_row.submission_date = date(2026, 5, 1)
    delayed_row.estimated_turnaround_days = 1
    session.add(delayed_row)
    session.commit()

    recon_inventory = inventory_id_from_latest_order(client, token)
    recon_candidate = make_ready_candidate(client, token, recon_inventory, target_grader="CGC")
    completed_batch = create_submission_batch(client, token, [recon_candidate], replay_key="dashboard-recon-batch")
    completed_batch_id = int(completed_batch["batch"]["id"])
    complete_submission_batch(client, token, completed_batch_id)
    item_id = int(
        session.exec(
            select(GradingSubmissionItem.id).where(GradingSubmissionItem.grading_submission_batch_id == completed_batch_id),
        ).one(),
    )
    reconcile = client.post(
        "/grading-reconciliation/reconcile",
        headers=auth_headers(token),
        json={
            "grading_submission_item_id": item_id,
            "final_grade": "9.4",
            "realized_graded_value": "210.00",
            "reconciled_at": "2026-05-30T12:00:00Z",
        },
    )
    assert reconcile.status_code == 201, reconcile.text

    return {
        "elite_rec_id": elite_rec_id,
        "risk_rec_id": risk_rec_id,
        "risk_snapshot_id": risk_snapshot_id,
        "delayed_batch_id": delayed_batch_id,
        "completed_batch_id": completed_batch_id,
    }


def test_generate_dealer_grading_dashboard_snapshot_alerts_and_feed(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "grading-dashboard-owner@example.com")
    fixture = _seed_dashboard_fixture(client, session, token)
    before_counts = {
        "recommendations": len(session.exec(select(GradingRecommendation)).all()),
        "risk": len(session.exec(select(GradingRiskSnapshot)).all()),
        "batches": len(session.exec(select(GradingSubmissionBatch)).all()),
        "reconciliation": len(session.exec(select(GradingReconciliationRecord)).all()),
    }

    rsp = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-001"},
    )
    assert rsp.status_code == 201, rsp.text
    snapshot = rsp.json()["snapshot"]
    assert snapshot["active_candidate_count"] == 2
    assert snapshot["ready_for_submission_count"] == 1
    assert snapshot["submitted_candidate_count"] == 1
    assert snapshot["graded_candidate_count"] == 1
    assert snapshot["elite_recommendation_count"] == 1
    assert snapshot["high_risk_candidate_count"] >= 1
    assert snapshot["low_confidence_candidate_count"] >= 1
    assert snapshot["active_submission_batch_count"] == 1
    assert snapshot["grading_pipeline_value"] is not None
    assert snapshot["estimated_total_submission_cost"] is not None
    assert snapshot["expected_total_profit"] is not None
    assert snapshot["checksum"]

    metrics = client.get("/dealer-grading-dashboard/metrics", headers=auth_headers(token))
    assert metrics.status_code == 200, metrics.text
    metric_keys = {row["metric_key"] for row in metrics.json()["items"]}
    assert {
        "aggregation_label",
        "grade_recommendation_count",
        "elite_opportunity_count",
        "delayed_batch_count",
        "average_roi_delta",
        "grader_performance_rollup",
    } <= metric_keys

    alerts = client.get("/dealer-grading-dashboard/alerts", headers=auth_headers(token))
    assert alerts.status_code == 200, alerts.text
    alert_types = {row["alert_type"] for row in alerts.json()["items"]}
    assert {
        "NEGATIVE_ROI",
        "HIGH_RISK",
        "LOW_CONFIDENCE",
        "SUBMISSION_DELAY",
        "RECONCILIATION_FAILURE",
        "WEAK_LIQUIDITY",
        "MISSING_EVIDENCE",
    } <= alert_types

    feed = client.get("/dealer-grading-dashboard/feed", headers=auth_headers(token))
    assert feed.status_code == 200, feed.text
    feed_json = feed.json()
    assert feed_json["total_items"] >= len(feed_json["items"])
    event_types = [row["event_type"] for row in feed_json["items"]]
    assert {
        "CANDIDATE_CREATED",
        "RECOMMENDATION_GENERATED",
        "SUBMISSION_BATCH_CREATED",
        "SUBMISSION_SHIPPED",
        "GRADES_RETURNED",
        "RECONCILIATION_COMPLETED",
        "HIGH_RISK_DETECTED",
        "ELITE_OPPORTUNITY_DETECTED",
    } <= set(event_types)

    created_times = [row["created_at"] for row in feed_json["items"]]
    assert created_times == sorted(created_times, reverse=True)

    session.expire_all()
    after_counts = {
        "recommendations": len(session.exec(select(GradingRecommendation)).all()),
        "risk": len(session.exec(select(GradingRiskSnapshot)).all()),
        "batches": len(session.exec(select(GradingSubmissionBatch)).all()),
        "reconciliation": len(session.exec(select(GradingReconciliationRecord)).all()),
    }
    assert after_counts == before_counts
    assert session.exec(select(DealerGradingDashboardSnapshot)).all()
    assert session.exec(select(DealerGradingDashboardMetric)).all()
    assert session.exec(select(DealerGradingDashboardAlert)).all()
    assert session.exec(select(DealerGradingDashboardFeedEvent)).all()
    assert fixture["risk_snapshot_id"] > 0


def test_checksum_stability_and_replay_safety(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "grading-dashboard-replay@example.com")
    _seed_dashboard_fixture(client, session, token)

    first = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-replay-001"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-replay-001"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["snapshot"]["id"] == first.json()["snapshot"]["id"]
    assert second.json()["snapshot"]["checksum"] == first.json()["snapshot"]["checksum"]

    third = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-replay-002"},
    )
    assert third.status_code == 201, third.text
    assert third.json()["snapshot"]["id"] == first.json()["snapshot"]["id"]
    assert len(session.exec(select(DealerGradingDashboardSnapshot)).all()) == 1


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "grading-dashboard-scope-owner@example.com")
    other = register_and_login(client, "grading-dashboard-scope-other@example.com")
    admin = register_and_login(client, "grading-dashboard-scope-admin@example.com")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "grading-dashboard-scope-admin@example.com")
    get_settings.cache_clear()

    _seed_dashboard_fixture(client, session, owner)
    _seed_dashboard_fixture(client, session, other)

    owner_gen = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(owner),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-scope-owner"},
    )
    assert owner_gen.status_code == 201, owner_gen.text
    other_gen = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(other),
        json={"snapshot_date": DASHBOARD_SNAPSHOT_DATE, "replay_key": "grading-dashboard-scope-other"},
    )
    assert other_gen.status_code == 201, other_gen.text

    owner_snapshot = client.get("/dealer-grading-dashboard", headers=auth_headers(owner))
    assert owner_snapshot.status_code == 200, owner_snapshot.text
    assert owner_snapshot.json()["snapshot"]["owner_user_id"] == owner_gen.json()["snapshot"]["owner_user_id"]

    other_alerts = client.get("/dealer-grading-dashboard/alerts", headers=auth_headers(other))
    assert other_alerts.status_code == 200, other_alerts.text
    assert all(row["owner_user_id"] == other_gen.json()["snapshot"]["owner_user_id"] for row in other_alerts.json()["items"])

    ops_snapshot = client.get(
        "/ops/dealer-grading-dashboard",
        params={"owner_user_id": owner_gen.json()["snapshot"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_snapshot.status_code == 200, ops_snapshot.text
    assert ops_snapshot.json()["snapshot"]["owner_user_id"] == owner_gen.json()["snapshot"]["owner_user_id"]

    ops_alerts = client.get(
        "/ops/dealer-grading-dashboard/alerts",
        params={"owner_user_id": owner_gen.json()["snapshot"]["owner_user_id"], "alert_type": "HIGH_RISK"},
        headers=auth_headers(admin),
    )
    assert ops_alerts.status_code == 200, ops_alerts.text
    assert all(row["owner_user_id"] == owner_gen.json()["snapshot"]["owner_user_id"] for row in ops_alerts.json()["items"])

    ops_feed = client.get(
        "/ops/dealer-grading-dashboard/feed",
        params={"owner_user_id": owner_gen.json()["snapshot"]["owner_user_id"], "event_type": "HIGH_RISK_DETECTED"},
        headers=auth_headers(admin),
    )
    assert ops_feed.status_code == 200, ops_feed.text
    assert ops_feed.json()["total_items"] >= 1
