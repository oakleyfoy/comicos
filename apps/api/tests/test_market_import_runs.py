from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.services.market_sales as market_sales_module
from app.core.config import get_settings
from app.models import MarketSource, MarketSourceImportRunEvent
from app.services.market_sales import SYSTEM_MARKET_SOURCE_PRESETS, ensure_system_market_sources

from test_inventory import auth_headers, register_and_login


def _ops_headers(client: TestClient, email: str) -> dict[str, str]:
    token = register_and_login(client, email)
    return auth_headers(token)


def _source_id(session: Session, source_name: str) -> int:
    ensure_system_market_sources(session)
    row = session.exec(select(MarketSource).where(MarketSource.source_name == source_name)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _create_run(client: TestClient, headers: dict[str, str], *, market_source_id: int, notes: str | None = None):
    payload = {"market_source_id": market_source_id}
    if notes is not None:
        payload["notes"] = notes
    rsp = client.post("/ops/market-import-runs", headers=headers, json=payload)
    assert rsp.status_code == 201
    return rsp.json()


def test_market_sources_list_is_deterministically_ordered(client: TestClient) -> None:
    hdr = auth_headers(register_and_login(client, "market-source-list@example.com"))
    rsp = client.get("/market-sources", headers=hdr)
    assert rsp.status_code == 200
    rows = rsp.json()
    assert [row["source_name"] for row in rows] == [seed.source_name for seed in SYSTEM_MARKET_SOURCE_PRESETS]
    assert [row["import_priority"] for row in rows] == [seed.import_priority for seed in SYSTEM_MARKET_SOURCE_PRESETS]


def test_market_import_run_lifecycle_and_history(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "market-import-ops@example.com")
    get_settings.cache_clear()
    hdr = _ops_headers(client, "market-import-ops@example.com")
    source_id = _source_id(session, "eBay")

    created = _create_run(client, hdr, market_source_id=source_id, notes="  initial pass  ")
    run_id = created["id"]
    assert created["status"] == "pending"
    assert created["notes"] == "initial pass"
    assert [event["event_type"] for event in created["events"]] == ["created"]

    detail = client.get(f"/market-import-runs/{run_id}", headers=hdr)
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id

    started = client.post(f"/ops/market-import-runs/{run_id}/start", headers=hdr)
    assert started.status_code == 200
    started_payload = started.json()
    assert started_payload["status"] == "running"
    assert started_payload["started_at"] is not None
    assert [event["event_type"] for event in started_payload["events"]] == ["created", "started"]

    second_start = client.post(f"/ops/market-import-runs/{run_id}/start", headers=hdr)
    assert second_start.status_code == 400

    completed = client.post(f"/ops/market-import-runs/{run_id}/complete", headers=hdr)
    assert completed.status_code == 200
    completed_payload = completed.json()
    assert completed_payload["status"] == "completed"
    assert completed_payload["completed_at"] is not None
    assert [event["event_type"] for event in completed_payload["events"]] == ["created", "started", "completed"]

    events = session.exec(
        select(MarketSourceImportRunEvent)
        .where(MarketSourceImportRunEvent.import_run_id == run_id)
        .order_by(MarketSourceImportRunEvent.created_at.asc(), MarketSourceImportRunEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == ["created", "started", "completed"]

    terminal_cancel = client.post(f"/ops/market-import-runs/{run_id}/cancel", headers=hdr)
    assert terminal_cancel.status_code == 400

    cancel_run = _create_run(client, hdr, market_source_id=_source_id(session, "Heritage Auctions"))
    cancel_rsp = client.post(f"/ops/market-import-runs/{cancel_run['id']}/cancel", headers=hdr)
    assert cancel_rsp.status_code == 200
    cancel_payload = cancel_rsp.json()
    assert cancel_payload["status"] == "cancelled"
    assert [event["event_type"] for event in cancel_payload["events"]] == ["created", "cancelled"]


def test_market_import_run_scope_and_ordering(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "market-import-scope-ops@example.com")
    get_settings.cache_clear()
    ops_hdr = _ops_headers(client, "market-import-scope-ops@example.com")
    other_hdr = auth_headers(register_and_login(client, "market-import-scope-owner@example.com"))

    base = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)
    tick = {"value": 0}

    def fake_now() -> datetime:
        tick["value"] += 1
        return base + timedelta(minutes=tick["value"])

    monkeypatch.setattr(market_sales_module, "utc_now", fake_now)

    first = _create_run(client, ops_hdr, market_source_id=_source_id(session, "MyComicShop"))
    second = _create_run(client, ops_hdr, market_source_id=_source_id(session, "ComicLink"))

    ops_list = client.get("/ops/market-import-runs", headers=ops_hdr)
    assert ops_list.status_code == 200
    ops_items = ops_list.json()["items"]
    assert [row["id"] for row in ops_items[:2]] == [second["id"], first["id"]]

    owner_list = client.get("/market-import-runs", headers=other_hdr)
    assert owner_list.status_code == 200
    assert owner_list.json()["items"] == []

    owner_detail = client.get(f"/market-import-runs/{first['id']}", headers=other_hdr)
    assert owner_detail.status_code == 404

    ops_forbidden = client.get("/ops/market-import-runs", headers=other_hdr)
    assert ops_forbidden.status_code == 403
