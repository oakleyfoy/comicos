from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import test_inventory as inv
from app.models import InventoryCopy
from app.services.order_arrival_intelligence import (
    OrderArrivalProjectionRow,
    derive_order_arrival_classifications,
)


def _proj(**kwargs: object) -> OrderArrivalProjectionRow:
    base = {
        "inventory_copy_id": 1,
        "owner_user_id": 1,
        "retailer": "Shop",
        "source_type": None,
        "publisher": "Pub",
        "title": "T",
        "issue_number": "1",
        "order_item_quantity": 1,
        "purchase_date": None,
        "release_date": None,
        "release_status": "unknown",
        "order_status": "ordered",
        "expected_ship_date": None,
        "received_at": None,
        "asset_state": "ordered_not_received",
    }
    base.update(kwargs)
    return OrderArrivalProjectionRow(**base)  # type: ignore[arg-type]


def test_derive_cancelled_returns_only_cancelled_order() -> None:
    row = _proj(order_status="cancelled", release_date=date(2026, 5, 1), expected_ship_date=date(2026, 4, 1))
    today = date(2026, 5, 24)
    assert derive_order_arrival_classifications(row, today=today) == ["cancelled_order"]


def test_derive_active_not_cancelled_includes_ship_and_release_buckets() -> None:
    today = date(2026, 5, 24)
    row = _proj(
        order_status="preordered",
        release_status="not_released_yet",
        release_date=date(2026, 6, 1),
        expected_ship_date=date(2026, 5, 30),
        received_at=None,
        asset_state="preorder_not_released_yet",
    )
    out = derive_order_arrival_classifications(row, today=today)
    assert "upcoming_preorder" in out
    assert "releases_this_week" not in out
    assert "expected_to_ship_soon" in out


def test_derive_releases_this_week_iso_bounds() -> None:
    today = date(2026, 5, 24)  # Sunday; ISO week spans May 18–May 24
    row = _proj(
        order_status="ordered",
        release_status="released",
        release_date=date(2026, 5, 22),
        expected_ship_date=None,
        received_at=None,
        asset_state="ordered_not_received",
    )
    out = derive_order_arrival_classifications(row, today=today)
    assert "releases_this_week" in out


def test_derive_released_not_received_excludes_received() -> None:
    today = date(2026, 5, 24)
    row_received = _proj(
        order_status="received",
        release_status="released",
        release_date=date(2026, 5, 1),
        received_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        asset_state="in_hand",
    )
    out_in_hand = derive_order_arrival_classifications(row_received, today=today)
    assert "released_not_received" not in out_in_hand
    assert "received_recently" in out_in_hand

    row_waiting = replace(
        row_received,
        received_at=None,
        order_status="ordered",
        asset_state="ordered_not_received",
    )
    out_wait = derive_order_arrival_classifications(row_waiting, today=today)
    assert "released_not_received" in out_wait


def test_expected_to_ship_fourteen_day_inclusive_boundary() -> None:
    today = date(2026, 5, 24)
    inclusive = _proj(
        order_status="ordered",
        release_status="released",
        release_date=date(2026, 5, 1),
        expected_ship_date=today + timedelta(days=14),
        received_at=None,
        asset_state="ordered_not_received",
    )
    assert "expected_to_ship_soon" in derive_order_arrival_classifications(inclusive, today=today)

    excluded = replace(
        inclusive,
        inventory_copy_id=2,
        expected_ship_date=today + timedelta(days=15),
    )
    assert "expected_to_ship_soon" not in derive_order_arrival_classifications(excluded, today=today)


def test_overdue_when_expected_ship_past_without_receive() -> None:
    today = date(2026, 5, 24)
    row = _proj(
        order_status="ordered",
        release_status="released",
        release_date=date(2026, 5, 1),
        expected_ship_date=date(2026, 5, 10),
        received_at=None,
        asset_state="ordered_not_received",
    )
    out = derive_order_arrival_classifications(row, today=today)
    assert "overdue_expected_ship" in out


def test_missing_release_date_for_preordered_without_calendar() -> None:
    row = _proj(order_status="preordered", release_status="unknown", release_date=None)
    today = date(2026, 5, 24)
    assert "missing_release_date" in derive_order_arrival_classifications(row, today=today)


def test_missing_expected_ship_for_ordered_when_no_ship_metadata() -> None:
    row = _proj(order_status="ordered", release_status="released", release_date=date(2026, 5, 1), expected_ship_date=None)
    today = date(2026, 5, 24)
    assert "missing_expected_ship_date" in derive_order_arrival_classifications(row, today=today)


def test_order_arrival_intel_endpoints_integration(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.order_arrival_intelligence._utc_today",
        lambda: date(2026, 5, 24),
    )

    token = inv.register_and_login(client, "arrival-user@example.com")
    hdr = inv.auth_headers(token)

    inv.create_order(
        client,
        token,
        retailer="SoonShop",
        items=[
            {
                "title": "Soon Ship",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
                "release_status": "released",
                "release_date": "2026-05-01",
                "order_status": "ordered",
                "expected_ship_date": "2026-05-29",
            }
        ],
    )

    lst = client.get("/inventory?page=1&page_size=50", headers=hdr).json()
    soon_inv = next(it for it in lst["items"] if it["title"] == "Soon Ship")

    inv.create_order(
        client,
        token,
        retailer="CancelHouse",
        items=[
            {
                "title": "Cancelled Book",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
                "release_status": "released",
                "release_date": "2026-05-01",
                "order_status": "ordered",
                "expected_ship_date": "2026-05-10",
            }
        ],
    )
    lst2 = client.get("/inventory?page=1&page_size=50", headers=hdr).json()
    cancelled_inv = next(it for it in lst2["items"] if it["title"] == "Cancelled Book")

    canceled_copy = session.get(InventoryCopy, cancelled_inv["inventory_copy_id"])
    assert canceled_copy is not None
    canceled_copy.order_status = "cancelled"
    session.commit()

    intel_resp = client.get("/order-arrival-intelligence", headers=hdr)
    assert intel_resp.status_code == 200
    payload = intel_resp.json()

    classifications = [row["classification"] for row in payload["items"]]
    assert "expected_to_ship_soon" in classifications
    canceled_rows = [
        row
        for row in payload["items"]
        if row["classification"] != "cancelled_order" and row["inventory_copy_id"] == canceled_copy.id
    ]
    assert not canceled_rows
    canceled_only = [
        row
        for row in payload["items"]
        if row["inventory_copy_id"] == canceled_copy.id and row["classification"] == "cancelled_order"
    ]
    assert len(canceled_only) == 1

    filtered_all = client.get("/order-arrival-intelligence", headers=hdr).json()
    filtered_one = client.get(
        "/order-arrival-intelligence?classification=released_not_received",
        headers=hdr,
    ).json()
    assert filtered_one["total_count"] <= filtered_all["total_count"]

    calendar = client.get(
        "/order-arrival-intelligence/calendar",
        headers=hdr,
        params={"calendar_start": "2026-05-24", "calendar_end": "2026-06-06"},
    )
    assert calendar.status_code == 200

    filt_inv = client.get(
        "/inventory?page=1&page_size=50&arrival_classification=expected_to_ship_soon",
        headers=hdr,
    ).json()
    assert filt_inv["total"] >= 1
    assert all("expected_to_ship_soon" in row.get("order_arrival_classifications", []) for row in filt_inv["items"])

    before = session.get(InventoryCopy, soon_inv["inventory_copy_id"])
    assert before is not None

    frozen_rdate = before.release_date
    frozen_ord = before.order_status

    assert client.get("/order-arrival-intelligence/summary", headers=hdr).status_code == 200
    after = session.get(InventoryCopy, soon_inv["inventory_copy_id"])
    assert after is not None
    assert after.release_date == frozen_rdate
    assert after.order_status == frozen_ord


def test_ops_order_arrival_endpoints_require_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "oarrival-ops@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    normal = inv.register_and_login(client, "oarrival-user@example.com")
    ops = inv.register_and_login(client, "oarrival-ops@example.com")

    denied = client.get("/ops/order-arrival-intelligence", headers=inv.auth_headers(normal))
    assert denied.status_code == 403

    allowed = client.get("/ops/order-arrival-intelligence", headers=inv.auth_headers(ops))
    assert allowed.status_code == 200
    assert allowed.json()["summary"]["scope"] == "ops"
