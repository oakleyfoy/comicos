from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    InventoryCopy,
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionBatch,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionScore,
    MarketAcquisitionSignal,
    MarketDeterminismValidationRun,
    MarketIntelligenceFeedEvent,
    MarketIntelligenceFeedHistory,
    MarketIntelligenceFeedSnapshot,
    PortfolioMarketCouplingEdge,
    User,
)
from test_inventory import auth_headers, register_and_login
from test_market_scoring import _run_ingestion_and_normalization, _seed_issue_and_context
from test_portfolio_market_coupling import _seed_active_portfolio_for_copy


def _seed_full_pipeline(client: TestClient, session: Session, *, token: str, owner_user_id: int) -> int:
    _run_ingestion_and_normalization(client, token)
    _seed_issue_and_context(session, owner_user_id=owner_user_id)

    copy_row = session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == owner_user_id)).first()
    assert copy_row is not None
    inventory_copy_id = int(copy_row[0] if isinstance(copy_row, tuple) else copy_row)
    _seed_active_portfolio_for_copy(session, owner_user_id=owner_user_id, inventory_copy_id=inventory_copy_id)

    score = client.post("/market-scoring/run", headers=auth_headers(token), json={})
    assert score.status_code == 200, score.text
    signal = client.post("/market-signals/generate", headers=auth_headers(token), json={})
    assert signal.status_code == 200, signal.text
    opportunity = client.post("/market-opportunities/generate", headers=auth_headers(token), json={})
    assert opportunity.status_code == 200, opportunity.text
    coupling = client.post("/market-portfolio-coupling/generate", headers=auth_headers(token), json={})
    assert coupling.status_code == 200, coupling.text
    feed = client.post("/api/v1/market/market-feed/replay", headers=auth_headers(token), json={"cursor_key": "pipeline"})
    assert feed.status_code == 200, feed.text
    determinism = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(token), json={})
    assert determinism.status_code in {200, 201}, determinism.text
    return int(determinism.json()["data"]["run"]["id"])


def test_market_intelligence_pipeline_is_stable_and_replay_safe(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-pipeline-stable@example.com")
    owner_user_id = int(session.exec(select(User.id).where(User.email == "market-pipeline-stable@example.com")).one())

    run_id = _seed_full_pipeline(client, session, token=token, owner_user_id=owner_user_id)

    initial_counts = {
        "ingestion": len(session.exec(select(MarketAcquisitionIngestionBatch)).all()),
        "candidates": len(session.exec(select(MarketAcquisitionCandidate)).all()),
        "normalized": len(session.exec(select(MarketAcquisitionNormalizedCandidate)).all()),
        "scores": len(session.exec(select(MarketAcquisitionScore)).all()),
        "signals": len(session.exec(select(MarketAcquisitionSignal)).all()),
        "opportunities": len(session.exec(select(MarketAcquisitionOpportunityItem)).all()),
        "coupling_edges": len(session.exec(select(PortfolioMarketCouplingEdge)).all()),
        "feed_events": len(session.exec(select(MarketIntelligenceFeedEvent)).all()),
        "feed_snapshots": len(session.exec(select(MarketIntelligenceFeedSnapshot)).all()),
        "feed_histories": len(session.exec(select(MarketIntelligenceFeedHistory)).all()),
    }

    first_run = client.get(
        f"/api/v1/market/market-determinism/validation-runs/{run_id}",
        headers=auth_headers(token),
    )
    assert first_run.status_code == 200, first_run.text
    first_body = first_run.json()["data"]
    assert first_body["run"]["validation_status"] in {"PASS", "WARNING"}
    assert first_body["run"]["validation_checksum"]
    assert first_body["run"]["pipeline_checksum"]
    assert first_body["checksum_audits"]
    assert first_body["invariants"]
    assert first_body["replay_audits"]

    second = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(token), json={})
    assert second.status_code == 200, second.text
    second_body = second.json()["data"]
    assert second_body["replayed"] is True
    assert second_body["run"]["id"] == first_body["run"]["id"]
    assert second_body["run"]["validation_checksum"] == first_body["run"]["validation_checksum"]

    feed_list_a = client.get("/api/v1/market/market-feed/events?limit=10&offset=0", headers=auth_headers(token))
    feed_list_b = client.get("/api/v1/market/market-feed/events?limit=10&offset=0", headers=auth_headers(token))
    assert feed_list_a.status_code == 200 and feed_list_b.status_code == 200
    assert feed_list_a.json()["data"]["items"] == feed_list_b.json()["data"]["items"]

    feed_snapshots = client.get("/api/v1/market/market-feed/snapshots?limit=10&offset=0", headers=auth_headers(token))
    assert feed_snapshots.status_code == 200, feed_snapshots.text
    assert feed_snapshots.json()["data"]["pagination"]["total_count"] >= 1

    det_runs = client.get("/api/v1/market/market-determinism/validation-runs?limit=10&offset=0", headers=auth_headers(token))
    assert det_runs.status_code == 200, det_runs.text
    assert det_runs.json()["data"]["pagination"]["total_count"] == 1
    assert det_runs.json()["data"]["items"][0]["validation_checksum"] == first_body["run"]["validation_checksum"]

    assert initial_counts["ingestion"] == len(session.exec(select(MarketAcquisitionIngestionBatch)).all())
    assert initial_counts["candidates"] == len(session.exec(select(MarketAcquisitionCandidate)).all())
    assert initial_counts["normalized"] == len(session.exec(select(MarketAcquisitionNormalizedCandidate)).all())
    assert initial_counts["scores"] == len(session.exec(select(MarketAcquisitionScore)).all())
    assert initial_counts["signals"] == len(session.exec(select(MarketAcquisitionSignal)).all())
    assert initial_counts["opportunities"] == len(session.exec(select(MarketAcquisitionOpportunityItem)).all())
    assert initial_counts["coupling_edges"] == len(session.exec(select(PortfolioMarketCouplingEdge)).all())
    assert initial_counts["feed_events"] == len(session.exec(select(MarketIntelligenceFeedEvent)).all())
    assert initial_counts["feed_snapshots"] == len(session.exec(select(MarketIntelligenceFeedSnapshot)).all())
    assert initial_counts["feed_histories"] == len(session.exec(select(MarketIntelligenceFeedHistory)).all())


def test_market_intelligence_pipeline_owner_ops_scoping_and_contracts(
    monkeypatch,
    client: TestClient,
    session: Session,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "market-pipeline-ops@example.com")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "market-pipeline-owner@example.com")
    peer_token = register_and_login(client, "market-pipeline-peer@example.com")
    ops_token = register_and_login(client, "market-pipeline-ops@example.com")
    owner_user_id = int(session.exec(select(User.id).where(User.email == "market-pipeline-owner@example.com")).one())

    run_id = _seed_full_pipeline(client, session, token=owner_token, owner_user_id=owner_user_id)

    owner_envelope = client.get("/api/v1/market/market-ingestion/batches?limit=1&offset=0", headers=auth_headers(owner_token))
    assert owner_envelope.status_code == 200, owner_envelope.text
    body = owner_envelope.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert "engine_versions" in body["meta"]

    peer_detail = client.get(
        f"/api/v1/market/market-determinism/validation-runs/{run_id}",
        headers=auth_headers(peer_token),
    )
    assert peer_detail.status_code == 404, peer_detail.text

    denied = client.get(
        f"/api/v1/market/ops/market-determinism/validation-runs?owner_user_id={owner_user_id}",
        headers=auth_headers(peer_token),
    )
    assert denied.status_code == 403, denied.text

    allowed = client.get(
        f"/api/v1/market/ops/market-determinism/validation-runs?owner_user_id={owner_user_id}",
        headers=auth_headers(ops_token),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["pagination"]["total_count"] == 1

    ops_feed = client.get(
        f"/api/v1/market/ops/market-feed/events?owner_user_id={owner_user_id}&limit=5&offset=0",
        headers=auth_headers(ops_token),
    )
    assert ops_feed.status_code == 200, ops_feed.text
    assert ops_feed.json()["data"]["pagination"]["total_count"] >= 1

    ops_generation_attempts = (
        "/api/v1/market/ops/market-ingestion/batch",
        "/api/v1/market/ops/market-normalization/run",
        "/api/v1/market/ops/market-scoring/run",
        "/api/v1/market/ops/market-signals/generate",
        "/api/v1/market/ops/market-opportunities/generate",
        "/api/v1/market/ops/market-portfolio-coupling/generate",
        "/api/v1/market/ops/market-determinism/run",
    )
    for path in ops_generation_attempts:
        response = client.post(path, headers=auth_headers(ops_token), json={})
        assert response.status_code in (404, 405), path
