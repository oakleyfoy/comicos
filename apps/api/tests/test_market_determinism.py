from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionScore,
    MarketAcquisitionSignal,
    MarketDeterminismValidationRun,
    MarketIntelligenceFeedEvent,
    PortfolioMarketCouplingEdge,
    User,
)
from test_inventory import auth_headers, register_and_login
from test_market_scoring import _run_ingestion_and_normalization, _seed_issue_and_context
from test_portfolio_market_coupling import _seed_active_portfolio_for_copy
from app.models import InventoryCopy


def _seed_market_pipeline(client: TestClient, session: Session, *, token: str, owner_user_id: int) -> None:
    _run_ingestion_and_normalization(client, token)
    _seed_issue_and_context(session, owner_user_id=owner_user_id)

    copy_row = session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == owner_user_id)).first()
    assert copy_row is not None
    inventory_copy_id = int(copy_row[0] if isinstance(copy_row, tuple) else copy_row)
    _seed_active_portfolio_for_copy(session, owner_user_id=owner_user_id, inventory_copy_id=inventory_copy_id)

    assert client.post("/market-scoring/run", headers=auth_headers(token), json={}).status_code == 200
    assert client.post("/market-signals/generate", headers=auth_headers(token), json={}).status_code == 200
    assert client.post("/market-opportunities/generate", headers=auth_headers(token), json={}).status_code == 200
    assert client.post("/market-portfolio-coupling/generate", headers=auth_headers(token), json={}).status_code == 200
    replay = client.post(
        "/api/v1/market/market-feed/replay",
        headers=auth_headers(token),
        json={"cursor_key": f"determinism-owner-{owner_user_id}"},
    )
    assert replay.status_code == 200, replay.text


def test_market_determinism_run_is_replay_safe_and_non_mutating(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-determinism-pass@example.com")
    owner_user_id = int(
        session.exec(select(User.id).where(User.email == "market-determinism-pass@example.com")).one()
    )
    _seed_market_pipeline(client, session, token=token, owner_user_id=owner_user_id)

    counts_before = {
        "scores": len(session.exec(select(MarketAcquisitionScore)).all()),
        "signals": len(session.exec(select(MarketAcquisitionSignal)).all()),
        "opportunities": len(session.exec(select(MarketAcquisitionOpportunityItem)).all()),
        "edges": len(session.exec(select(PortfolioMarketCouplingEdge)).all()),
        "events": len(session.exec(select(MarketIntelligenceFeedEvent)).all()),
    }

    first = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(token), json={})
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["meta"]["engine_versions"]["determinism"] == "P39-10"
    assert first_body["data"]["replayed"] is False
    assert first_body["data"]["run"]["validation_status"] in {"PASS", "WARNING"}
    assert len(first_body["data"]["checksum_audits"]) == 7
    assert len(first_body["data"]["invariants"]) >= 8
    assert len(first_body["data"]["replay_audits"]) >= 8

    second = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(token), json={})
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["data"]["replayed"] is True
    assert second_body["data"]["run"]["id"] == first_body["data"]["run"]["id"]
    assert second_body["data"]["run"]["validation_checksum"] == first_body["data"]["run"]["validation_checksum"]

    runs = session.exec(
        select(MarketDeterminismValidationRun).where(MarketDeterminismValidationRun.owner_user_id == owner_user_id)
    ).all()
    assert len(runs) == 1
    assert counts_before["scores"] == len(session.exec(select(MarketAcquisitionScore)).all())
    assert counts_before["signals"] == len(session.exec(select(MarketAcquisitionSignal)).all())
    assert counts_before["opportunities"] == len(session.exec(select(MarketAcquisitionOpportunityItem)).all())
    assert counts_before["edges"] == len(session.exec(select(PortfolioMarketCouplingEdge)).all())
    assert counts_before["events"] == len(session.exec(select(MarketIntelligenceFeedEvent)).all())


def test_market_determinism_routes_scope_and_detect_checksum_drift(
    monkeypatch,
    client: TestClient,
    session: Session,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "market-determinism-ops@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "market-determinism-owner@example.com")
    peer_token = register_and_login(client, "market-determinism-peer@example.com")
    ops_token = register_and_login(client, "market-determinism-ops@example.com")
    owner_user_id = int(
        session.exec(select(User.id).where(User.email == "market-determinism-owner@example.com")).one()
    )
    _seed_market_pipeline(client, session, token=owner_token, owner_user_id=owner_user_id)

    first = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(owner_token), json={})
    assert first.status_code == 201, first.text
    first_run_id = int(first.json()["data"]["run"]["id"])

    peer_detail = client.get(
        f"/api/v1/market/market-determinism/validation-runs/{first_run_id}",
        headers=auth_headers(peer_token),
    )
    assert peer_detail.status_code == 404

    denied = client.get(
        f"/api/v1/market/ops/market-determinism/validation-runs?owner_user_id={owner_user_id}",
        headers=auth_headers(peer_token),
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/api/v1/market/ops/market-determinism/validation-runs?owner_user_id={owner_user_id}",
        headers=auth_headers(ops_token),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["pagination"]["total_count"] == 1

    event_row = session.exec(
        select(MarketIntelligenceFeedEvent)
        .where(MarketIntelligenceFeedEvent.owner_user_id == owner_user_id)
        .order_by(MarketIntelligenceFeedEvent.id.asc())
    ).first()
    assert event_row is not None
    event_row.event_checksum = "0" * 64
    session.add(event_row)
    session.commit()

    rerun = client.post("/api/v1/market/market-determinism/run", headers=auth_headers(owner_token), json={})
    assert rerun.status_code == 201, rerun.text
    rerun_body = rerun.json()["data"]
    assert rerun_body["run"]["id"] != first_run_id
    assert rerun_body["run"]["validation_status"] == "FAIL"
    assert rerun_body["run"]["replay_failure_count"] >= 1 or rerun_body["run"]["checksum_mismatch_count"] >= 1
    assert any(
        row["artifact_type"] == "FEED_EVENT_STREAM" and row["replay_status"] == "FAIL"
        for row in rerun_body["replay_audits"]
    )
