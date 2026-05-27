from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    MarketAcquisitionScore,
    MarketAcquisitionScoreEvidence,
    MarketAcquisitionScoreSnapshot,
    MarketAcquisitionSignal,
    MarketAcquisitionSignalEvidence,
    MarketAcquisitionSignalHistory,
    MarketAcquisitionSignalSnapshot,
    User,
)
from app.services import market_signal as signal_svc
from test_inventory import auth_headers, register_and_login
from test_market_scoring import _run_ingestion_and_normalization, _seed_issue_and_context


def test_market_signal_strength_bands() -> None:
    assert signal_svc._signal_strength(Decimal("85.00")) == "ELITE"
    assert signal_svc._signal_strength(Decimal("70.00")) == "HIGH"
    assert signal_svc._signal_strength(Decimal("50.00")) == "MEDIUM"
    assert signal_svc._signal_strength(Decimal("49.99")) == "LOW"


def test_market_signal_select_rule_prefers_explicit_high_risk() -> None:
    score_snapshot = MarketAcquisitionScoreSnapshot(
        id=1,
        owner_user_id=1,
        total_candidates_scored=1,
        avg_score=Decimal("32.00"),
        checksum="score-snap",
        snapshot_date=date(2026, 5, 26),
        created_at=datetime.now(timezone.utc),
    )
    score = MarketAcquisitionScore(
        id=7,
        market_acquisition_score_snapshot_id=1,
        normalized_candidate_id=3,
        owner_user_id=1,
        liquidity_score=Decimal("20.00"),
        portfolio_fit_score=Decimal("45.00"),
        grading_upside_score=Decimal("62.00"),
        concentration_reduction_score=Decimal("30.00"),
        diversification_score=Decimal("28.00"),
        risk_penalty_score=Decimal("78.00"),
        final_rank_score=Decimal("42.00"),
        score_breakdown_json={},
        recommendation_label="IGNORE",
        confidence_level="LOW",
        risk_level="HIGH",
        checksum="score-checksum",
        snapshot_date=date(2026, 5, 26),
        created_at=datetime.now(timezone.utc),
    )
    ctx = signal_svc._SignalContext(
        score=score,
        score_snapshot=score_snapshot,
        evidence_map={
            "NORMALIZATION_LAYER": {
                "normalized_price": "18.00",
                "normalized_fmv_estimate": "19.00",
                "condition_band": "GOOD",
            },
            "DUPLICATE_INTELLIGENCE": {"existing_issue_count": 0, "duplicate_overlap_penalty": "0.00"},
            "CONCENTRATION_RISK": {"publisher_status": "WATCH", "title_status": "WATCH"},
            "LIQUIDITY_ENGINE": {"portfolio_balance_status": "LOW"},
            "PORTFOLIO_STATE": {"existing_issue_count": 0},
        },
    )
    signal_type, reason, factors = signal_svc._select_signal(ctx)
    assert signal_type == "HIGH_RISK_ASSET"
    assert reason["rule"] == "risk_penalty_or_low_liquidity"
    assert factors["risk_level"] == "HIGH"


def test_market_signal_generation_is_deterministic_replay_safe_and_non_mutating(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ma-signal-deterministic@example.com")
    owner_user_id = int(session.exec(select(User.id).where(User.email == "ma-signal-deterministic@example.com")).one())
    _run_ingestion_and_normalization(client, token)
    _seed_issue_and_context(session, owner_user_id=owner_user_id)
    score_run = client.post("/market-scoring/run", headers=auth_headers(token), json={})
    assert score_run.status_code == 200, score_run.text

    score_count_before = len(session.exec(select(MarketAcquisitionScore)).all())
    score_evidence_count_before = len(session.exec(select(MarketAcquisitionScoreEvidence)).all())

    first = client.post("/market-signals/generate", headers=auth_headers(token), json={})
    assert first.status_code == 200, first.text
    payload_1 = first.json()
    assert payload_1["replayed"] is False
    assert payload_1["total_signals"] == score_count_before

    second = client.post("/market-signals/generate", headers=auth_headers(token), json={})
    assert second.status_code == 200, second.text
    payload_2 = second.json()
    assert payload_2["replayed"] is True
    assert payload_1["snapshot"]["id"] == payload_2["snapshot"]["id"]
    assert payload_1["snapshot"]["checksum"] == payload_2["snapshot"]["checksum"]

    signals = session.exec(select(MarketAcquisitionSignal)).all()
    evidence = session.exec(select(MarketAcquisitionSignalEvidence)).all()
    history = session.exec(select(MarketAcquisitionSignalHistory)).all()
    snapshots = session.exec(select(MarketAcquisitionSignalSnapshot)).all()
    assert len(signals) == score_count_before
    assert len(evidence) == score_count_before * 3
    assert len(history) == score_count_before
    assert len(snapshots) == 1
    assert len(session.exec(select(MarketAcquisitionScore)).all()) == score_count_before
    assert len(session.exec(select(MarketAcquisitionScoreEvidence)).all()) == score_evidence_count_before


def test_market_signal_owner_ops_visibility_and_detail(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "ma-signal-owner-a@example.com")
    token_b = register_and_login(client, "ma-signal-owner-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "ma-signal-owner-a@example.com")).one())
    _run_ingestion_and_normalization(client, token_a)
    _seed_issue_and_context(session, owner_user_id=owner_a)
    score_run = client.post("/market-scoring/run", headers=auth_headers(token_a), json={})
    assert score_run.status_code == 200, score_run.text
    signal_run = client.post("/market-signals/generate", headers=auth_headers(token_a), json={})
    assert signal_run.status_code == 200, signal_run.text

    signals = client.get("/market-signals", headers=auth_headers(token_a))
    assert signals.status_code == 200, signals.text
    signal_id = int(signals.json()["items"][0]["id"])

    owner_detail = client.get(f"/market-signals/{signal_id}", headers=auth_headers(token_a))
    assert owner_detail.status_code == 200, owner_detail.text
    assert len(owner_detail.json()["evidence"]) == 3

    other_owner_detail = client.get(f"/market-signals/{signal_id}", headers=auth_headers(token_b))
    assert other_owner_detail.status_code == 404, other_owner_detail.text

    ops_signals = client.get(f"/ops/market-signals?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_signals.status_code == 200, ops_signals.text
    assert any(int(row["id"]) == signal_id for row in ops_signals.json()["items"])

    ops_evidence = client.get(f"/ops/market-signal-evidence?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_evidence.status_code == 200, ops_evidence.text
    assert len(ops_evidence.json()["items"]) >= 3

    ops_detail = client.get(f"/ops/market-signals/{signal_id}", headers=auth_headers(token_a))
    assert ops_detail.status_code == 200, ops_detail.text
    assert ops_detail.json()["signal"]["owner_user_id"] == owner_a
