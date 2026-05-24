"""Tests for deterministic collection event timeline (read-only)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import DuplicateCandidateReview, InventoryCopy


def _hdr(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _register(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _order(client: TestClient, tok: str, order_date: str, items: list[dict]) -> None:
    assert (
        client.post(
            "/orders",
            headers=_hdr(tok),
            json={
                "retailer": "Fixture",
                "order_date": order_date,
                "source_type": "manual",
                "shipping_amount": 0,
                "tax_amount": 0,
                "items": items,
            },
        ).status_code
        == 201
    )


def _simple_item(**extra: object) -> dict:
    row = {
        "title": "T",
        "publisher": "P",
        "issue_number": "1",
        "cover_name": None,
        "printing": None,
        "ratio": None,
        "variant_type": None,
        "cover_artist": None,
        "quantity": 1,
        "raw_item_price": 3,
    }
    row.update(extra)
    return row


def test_collection_timeline_preorder_created_and_sort_desc(client: TestClient) -> None:
    tok = _register(client, "ct-pre@example.com")
    _order(
        client,
        tok,
        "2028-06-01",
        [
            _simple_item(
                order_status="preordered",
                release_status="not_released_yet",
                release_date="2028-06-01",
            ),
        ],
    )
    resp = client.get("/collection-timeline?sort=desc&limit=500", headers=_hdr(tok))
    assert resp.status_code == 200
    body = resp.json()
    types = [e["event_type"] for e in body["events"]]
    assert "preorder_created" in types
    assert "inventory_added" in types
    times = [datetime.fromisoformat(e["occurred_at"]) for e in body["events"]]
    assert times == sorted(times, reverse=True)


def test_collection_timeline_received_event_and_filter(client: TestClient) -> None:
    tok = _register(client, "ct-recv@example.com")
    _order(client, tok, "2026-01-01", [_simple_item()])
    copy = client.get("/inventory?page=1&page_size=10", headers=_hdr(tok)).json()["items"][0]
    cid = copy["inventory_copy_id"]
    recv = "2026-02-15T12:00:00+00:00"
    assert (
        client.patch(
            f"/inventory/{cid}",
            headers=_hdr(tok),
            json={"received_at": recv, "order_status": "received"},
        ).status_code
        == 200
    )
    detail = client.get("/collection-timeline?event_type=inventory_received", headers=_hdr(tok))
    assert detail.status_code == 200
    evs = detail.json()["events"]
    assert len(evs) >= 1
    assert all(e["event_type"] == "inventory_received" for e in evs)


def test_inventory_detail_timeline_404_for_other_user(client: TestClient, session: Session) -> None:
    a = _register(client, "ct-a@example.com")
    b = _register(client, "ct-b@example.com")
    _order(client, a, "2026-04-01", [_simple_item()])
    copy_id = session.exec(select(InventoryCopy.id)).first()
    assert copy_id is not None
    r = client.get(f"/inventory/{copy_id}/timeline", headers=_hdr(b))
    assert r.status_code == 404


def test_duplicate_detected_identity_fanout(client: TestClient, session: Session) -> None:
    tok = _register(client, "ct-dup@example.com")
    _order(client, tok, "2026-05-01", [_simple_item(metadata_identity_key="dup-key-1")])
    _order(client, tok, "2026-05-02", [_simple_item(metadata_identity_key="dup-key-1")])
    session.add(
        DuplicateCandidateReview(
            metadata_identity_key="dup-key-1",
            review_status="pending",
        ),
    )
    session.commit()

    r = client.get("/collection-timeline?event_type=duplicate_detected", headers=_hdr(tok))
    assert r.status_code == 200
    assert r.json()["summary"]["total_events_present"] >= 2


def test_grouping_by_publisher(client: TestClient) -> None:
    tok = _register(client, "ct-grp@example.com")
    _order(client, tok, "2026-01-01", [_simple_item(publisher="AlphaPub")])
    _order(client, tok, "2026-01-02", [_simple_item(publisher="BetaPub", title="Other")])
    r = client.get("/collection-timeline?grouping=publisher&sort=asc&limit=500", headers=_hdr(tok))
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert len(groups) >= 2
    keys = sorted(g["group_key"] for g in groups)
    assert "AlphaPub" in keys and "BetaPub" in keys


def test_summary_matches_total_counts(client: TestClient) -> None:
    tok = _register(client, "ct-sum@example.com")
    _order(client, tok, "2026-01-01", [_simple_item()])
    full = client.get("/collection-timeline", headers=_hdr(tok)).json()
    sm = client.get("/collection-timeline/summary", headers=_hdr(tok)).json()
    assert sm["total_events_present"] == full["summary"]["total_events_present"]


def test_ops_timeline_requires_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-admin@fixture.com")
    get_settings.cache_clear()
    tok = _register(client, "ct-ops@example.com")
    r = client.get("/ops/collection-timeline", headers=_hdr(tok))
    get_settings.cache_clear()
    assert r.status_code == 403
