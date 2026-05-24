"""Deterministic collection analytics API tests."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy


def _register(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    r = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _hdr(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _order(client: TestClient, token: str, order_date: str, items: list[dict]) -> None:
    assert (
        client.post(
            "/orders",
            headers=_hdr(token),
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


def _simple_item(title: str, publisher: str, **extra: object) -> dict:
    row: dict = {
        "title": title,
        "publisher": publisher,
        "issue_number": "1",
        "cover_name": None,
        "printing": None,
        "ratio": None,
        "variant_type": None,
        "cover_artist": None,
        "quantity": 1,
        "raw_item_price": 3.0,
    }
    row.update(extra)
    return row


def test_publishers_stable_alphabetical_order(client: TestClient) -> None:
    tok = _register(client, "ca-pub@example.com")
    _order(client, tok, "2026-06-01", [_simple_item("A", "Zebra Pub")])
    _order(client, tok, "2026-06-02", [_simple_item("B", "Acme Pub")])
    resp = client.get("/collection-analytics/publishers", headers=_hdr(tok))
    assert resp.status_code == 200
    names = [p["publisher_name"] for p in resp.json()["publishers"]]
    assert names == ["Acme Pub", "Zebra Pub"]


def test_timeline_orders_purchase_year_buckets(client: TestClient) -> None:
    tok = _register(client, "ca-time@example.com")
    _order(client, tok, "2021-03-04", [_simple_item("Old", "P1")])
    _order(client, tok, "2024-07-09", [_simple_item("New", "P2")])
    r = client.get("/collection-analytics/timeline", headers=_hdr(tok))
    assert r.status_code == 200
    years = {b["year_key"]: b["copies"] for b in r.json()["timeline"]["by_purchase_year"]}
    assert years.get("2021") == 1
    assert years.get("2024") == 1


def test_preorder_upcoming_respects_fixed_as_of(client: TestClient) -> None:
    tok = _register(client, "ca-pre@example.com")
    _order(
        client,
        tok,
        "2026-01-01",
        [
            _simple_item(
                "Future Hit",
                "P",
                release_status="not_released_yet",
                order_status="preordered",
                release_date="2030-04-15",
            )
        ],
    )
    r = client.get(
        "/collection-analytics/timeline?as_of=2029-12-31",
        headers=_hdr(tok),
    )
    assert r.status_code == 200
    upcoming = r.json()["timeline"]["upcoming_preorder_calendar"]
    assert len(upcoming) >= 1
    assert upcoming[0]["first_release_bucket"] == "2030-04"


def test_composition_raw_vs_graded(client: TestClient, session: Session) -> None:
    tok = _register(client, "ca-grade@example.com")
    _order(client, tok, "2026-06-02", [_simple_item("G", "P")])
    copy_id = session.exec(select(InventoryCopy.id)).one()
    p = client.patch(
        f"/inventory/{copy_id}",
        headers=_hdr(tok),
        json={"grade_status": "submitted"},
    )
    assert p.status_code == 200
    c = client.get("/collection-analytics/composition", headers=_hdr(tok))
    assert c.status_code == 200
    body = c.json()["composition"]
    assert body["graded_copies"] == 1
    assert body["raw_copies"] == 0
    assert body["graded_vs_raw"]["numerator"] == 1


def test_quality_rollups_bounded(client: TestClient) -> None:
    tok = _register(client, "ca-q@example.com")
    _order(client, tok, "2026-06-03", [_simple_item("Q", "P")])
    r = client.get("/collection-analytics/quality", headers=_hdr(tok))
    assert r.status_code == 200
    q = r.json()["inventory_quality"]
    assert q["scope_active_copies_ex_cancelled"] >= 1
    for metric in (
        q["ocr_complete"],
        q["canonical_linked"],
        q["unresolved_open_conflict_copies"],
        q["duplicate_ownership_exposure_copies"],
        q["missing_primary_scan"],
        q["primary_cover_failed_processing"],
        q["primary_cover_failed_ocr"],
    ):
        assert metric["numerator"] <= metric["denominator"]


def test_duplicate_gets_identical_twice_deterministic(client: TestClient) -> None:
    tok = _register(client, "ca-idem@example.com")
    _order(client, tok, "2026-06-03", [_simple_item("X", "P")])
    a = client.get("/collection-analytics/publishers?as_of=2026-06-03", headers=_hdr(tok)).json()
    b = client.get("/collection-analytics/publishers?as_of=2026-06-03", headers=_hdr(tok)).json()
    assert a == b


def test_get_endpoints_do_not_mutate_inventory(client: TestClient, session: Session) -> None:
    tok = _register(client, "ca-ro@example.com")
    _order(client, tok, "2026-06-03", [_simple_item("R", "P")])
    before = session.exec(select(InventoryCopy.id)).all()
    endpoints = (
        "/collection-analytics/summary",
        "/collection-analytics/publishers",
        "/collection-analytics/timeline",
        "/collection-analytics/quality",
        "/collection-analytics/composition",
    )
    for ep in endpoints:
        assert client.get(ep, headers=_hdr(tok)).status_code == 200
    after = session.exec(select(InventoryCopy.id)).all()
    assert sorted(after) == sorted(before)


def test_ops_collection_analytics_requires_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-ca@example.com")
    get_settings.cache_clear()
    tok = _register(client, "ops-ca@example.com")
    resp = client.get("/ops/collection-analytics/summary", headers=_hdr(tok))
    assert resp.status_code == 200
    other = _register(client, "notops@example.com")
    forbidden = client.get("/ops/collection-analytics/summary", headers=_hdr(other))
    assert forbidden.status_code == 403

