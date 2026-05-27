from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MarketIntelligenceFeedEvent, MarketIntelligenceFeedHistory, MarketIntelligenceFeedSnapshot, User
from app.schemas.market_feed import MarketIntelligenceFeedReplayPayload
from app.services.market_feed import append_market_feed_event, build_market_feed_snapshot, replay_market_feed
from test_inventory import auth_headers, register_and_login


def test_market_feed_append_replay_and_snapshot_are_deterministic(client: TestClient, session: Session) -> None:
    _token = register_and_login(client, "market-feed-deterministic@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "market-feed-deterministic@example.com")).one())

    snap_date = date(2026, 5, 26)
    created = append_market_feed_event(
        session,
        owner_user_id=owner_id,
        event_type="INGESTION_BATCH_CREATED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={"batch_id": 101, "stage": "created"},
        ingestion_batch_id=101,
    )
    duplicate = append_market_feed_event(
        session,
        owner_user_id=owner_id,
        event_type="INGESTION_BATCH_CREATED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={"batch_id": 101, "stage": "created"},
        ingestion_batch_id=101,
    )
    append_market_feed_event(
        session,
        owner_user_id=owner_id,
        event_type="INGESTION_BATCH_COMPLETED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={"batch_id": 101, "stage": "completed"},
        ingestion_batch_id=101,
    )
    session.commit()

    assert created.id == duplicate.id
    events = list(session.exec(select(MarketIntelligenceFeedEvent).where(MarketIntelligenceFeedEvent.owner_user_id == owner_id)).all())
    assert len(events) == 2
    assert [row.event_sequence_id for row in events] == [1, 2]

    snapshot = build_market_feed_snapshot(session, owner_user_id=owner_id, snapshot_date=snap_date)
    session.commit()
    assert snapshot.total_events == 2
    assert snapshot.latest_event_sequence_id == 2
    assert snapshot.event_type_counts_json["INGESTION_BATCH_CREATED"] == 1
    assert snapshot.event_type_counts_json["INGESTION_BATCH_COMPLETED"] == 1

    replay_payload = MarketIntelligenceFeedReplayPayload(
        owner_user_id=owner_id,
        snapshot_date=snap_date,
        cursor_key="feed-owner",
    )
    replay_a = replay_market_feed(session, payload=replay_payload)
    session.commit()
    replay_b = replay_market_feed(session, payload=replay_payload)
    session.commit()

    assert replay_a.checksum_consistent is True
    assert replay_b.checksum_consistent is True
    assert replay_a.snapshot.snapshot_checksum == replay_b.snapshot.snapshot_checksum
    assert replay_a.snapshot.id == replay_b.snapshot.id

    snapshots = list(
        session.exec(
            select(MarketIntelligenceFeedSnapshot).where(MarketIntelligenceFeedSnapshot.owner_user_id == owner_id)
        ).all()
    )
    histories = list(
        session.exec(select(MarketIntelligenceFeedHistory).where(MarketIntelligenceFeedHistory.owner_user_id == owner_id)).all()
    )
    assert len(snapshots) == 1
    assert len(histories) == 1


def test_market_feed_owner_and_ops_routes_scoped(client: TestClient, monkeypatch, session: Session) -> None:
    owner_token = register_and_login(client, "market-feed-owner@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "market-feed-owner@example.com")).one())
    snap_date = date(2026, 5, 26)
    append_market_feed_event(
        session,
        owner_user_id=owner_id,
        event_type="SNAPSHOT_CREATED",
        severity="INFO",
        snapshot_date=snap_date,
        event_payload_json={"layer": "scoring", "score_snapshot_id": 5001},
        scoring_run_id=5001,
    )
    session.commit()

    owner_feed = client.get("/api/v1/market/market-feed/events", headers=auth_headers(owner_token))
    assert owner_feed.status_code == 200, owner_feed.text
    assert owner_feed.json()["data"]["pagination"]["total_count"] == 1

    ops_token = register_and_login(client, "market-feed-ops@example.com")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "")
    get_settings.cache_clear()
    denied = client.get("/api/v1/market/ops/market-feed/events?owner_user_id=1", headers=auth_headers(ops_token))
    assert denied.status_code == 403

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "market-feed-ops@example.com")
    get_settings.cache_clear()
    allowed = client.get(
        f"/api/v1/market/ops/market-feed/events?owner_user_id={owner_id}",
        headers=auth_headers(ops_token),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["pagination"]["total_count"] == 1
