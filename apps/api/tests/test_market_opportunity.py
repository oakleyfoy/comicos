from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.models import (
    MarketAcquisitionOpportunityEvidence,
    MarketAcquisitionOpportunityHistory,
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionOpportunitySnapshot,
    MarketAcquisitionScore,
    MarketAcquisitionSignal,
    User,
)
from app.services import market_opportunity as opp_svc
from test_inventory import auth_headers, register_and_login
from test_market_scoring import _run_ingestion_and_normalization, _seed_issue_and_context


def test_opportunity_classification_branches_deterministic() -> None:
    cls = opp_svc.classify_opportunity_portfolio_view(
        total_signals=10,
        value_dislocation_count=4,
        grading_upside_count=2,
        liquidity_opportunity_count=2,
        portfolio_gap_fill_count=2,
        concentration_reduction_count=2,
        redundant_asset_count=0,
        high_risk_asset_count=0,
        avg_acquisition_score=Decimal("75.00"),
    )
    assert cls == "ELITE_OPPORTUNITY"

    stressed = opp_svc.classify_opportunity_portfolio_view(
        total_signals=10,
        value_dislocation_count=1,
        grading_upside_count=0,
        liquidity_opportunity_count=0,
        portfolio_gap_fill_count=0,
        concentration_reduction_count=0,
        redundant_asset_count=4,
        high_risk_asset_count=4,
        avg_acquisition_score=Decimal("30.00"),
    )
    assert stressed == "LOW_OPPORTUNITY"


def test_market_opportunity_aggregate_is_deterministic_replay_safe_and_non_mutating(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ma-opp-deterministic@example.com")
    owner_user_id = int(session.exec(select(User.id).where(User.email == "ma-opp-deterministic@example.com")).one())
    _run_ingestion_and_normalization(client, token)
    _seed_issue_and_context(session, owner_user_id=owner_user_id)
    score_run = client.post("/market-scoring/run", headers=auth_headers(token), json={})
    assert score_run.status_code == 200, score_run.text
    signal_run = client.post("/market-signals/generate", headers=auth_headers(token), json={})
    assert signal_run.status_code == 200, signal_run.text

    score_count_before = len(session.exec(select(MarketAcquisitionScore)).all())
    signals_before_count = len(session.exec(select(MarketAcquisitionSignal)).all())

    first = client.post("/market-opportunities/generate", headers=auth_headers(token), json={})
    assert first.status_code == 200, first.text
    p1 = first.json()
    assert p1["replayed"] is False
    opp_snapshot_id = int(p1["snapshot"]["id"])

    detail = client.get(f"/market-opportunities/{opp_snapshot_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    items = body["items"]
    assert items == sorted(items, key=lambda row: row["id"])

    repeat = client.post("/market-opportunities/generate", headers=auth_headers(token), json={})
    assert repeat.status_code == 200, repeat.text
    p2 = repeat.json()
    assert p2["replayed"] is True
    assert p1["snapshot"]["id"] == p2["snapshot"]["id"]
    assert p1["snapshot"]["snapshot_checksum"] == p2["snapshot"]["snapshot_checksum"]

    histories = session.exec(
        select(MarketAcquisitionOpportunityHistory).where(MarketAcquisitionOpportunityHistory.owner_user_id == owner_user_id),
    ).all()
    assert len(histories) == 1

    evidences = session.exec(
        select(MarketAcquisitionOpportunityEvidence).where(
            MarketAcquisitionOpportunityEvidence.market_acquisition_opportunity_snapshot_id == opp_snapshot_id,
        ),
    ).all()
    assert len(evidences) == 5

    opp_items_db = session.exec(
        select(MarketAcquisitionOpportunityItem).where(
            MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id == opp_snapshot_id,
        ).order_by(col(MarketAcquisitionOpportunityItem.id).asc()),
    ).all()
    assert len(opp_items_db) == p1["total_items"] == signals_before_count == score_count_before
    weights = [_row.contribution_weight for _row in opp_items_db]
    assert sum(weights) == Decimal("1.000000")

    assert len(session.exec(select(MarketAcquisitionSignal)).all()) == signals_before_count
    assert len(session.exec(select(MarketAcquisitionScore)).all()) == score_count_before

    dup_detail = client.get(f"/market-opportunities/{opp_snapshot_id}", headers=auth_headers(token))
    assert dup_detail.status_code == 200, dup_detail.text
    assert [row["market_acquisition_signal_id"] for row in dup_detail.json()["items"]] == [
        row["market_acquisition_signal_id"] for row in items
    ]


def test_market_opportunity_owner_ops_visibility(
    monkeypatch,
    client: TestClient,
    session: Session,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ma-opp-ops@example.com")
    tok_owner = register_and_login(client, "ma-opp-owner@example.com")
    tok_other = register_and_login(client, "ma-opp-peer@example.com")
    ops_tok = register_and_login(client, "ma-opp-ops@example.com")

    owner_id = int(session.exec(select(User.id).where(User.email == "ma-opp-owner@example.com")).one())
    _run_ingestion_and_normalization(client, tok_owner)
    _seed_issue_and_context(session, owner_user_id=owner_id)
    assert client.post("/market-scoring/run", headers=auth_headers(tok_owner), json={}).status_code == 200
    assert client.post("/market-signals/generate", headers=auth_headers(tok_owner), json={}).status_code == 200
    assert client.post("/market-opportunities/generate", headers=auth_headers(tok_owner), json={}).status_code == 200

    detail_list = client.get("/market-opportunities/snapshots", headers=auth_headers(tok_owner))
    opp_id = int(detail_list.json()["items"][0]["id"])

    peer = client.get(f"/market-opportunities/{opp_id}", headers=auth_headers(tok_other))
    assert peer.status_code == 404, peer.text

    ops_rows = client.get(f"/ops/market-opportunities/snapshots?owner_user_id={owner_id}", headers=auth_headers(ops_tok))
    assert ops_rows.status_code == 200, ops_rows.text
    assert any(int(row["id"]) == opp_id for row in ops_rows.json()["items"])

    ops_detail = client.get(f"/ops/market-opportunities/{opp_id}", headers=auth_headers(ops_tok))
    assert ops_detail.status_code == 200, ops_detail.text
    assert ops_detail.json()["snapshot"]["owner_user_id"] == owner_id
