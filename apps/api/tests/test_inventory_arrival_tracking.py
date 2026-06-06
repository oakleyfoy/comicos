from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import test_inventory as inv
from app.services.inventory_arrival_tracking import classify_inventory_arrival_lane
from app.services.order_arrival_intelligence import OrderArrivalProjectionRow


def _proj(**kwargs: object) -> OrderArrivalProjectionRow:
    base = {
        "inventory_copy_id": 1,
        "owner_user_id": 1,
        "retailer": "Shop",
        "source_type": "import",
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


def test_classify_not_released_yet_preorder() -> None:
    today = date(2026, 6, 1)
    row = _proj(
        order_status="preordered",
        release_status="not_released_yet",
        release_date=date(2026, 7, 1),
    )
    assert classify_inventory_arrival_lane(row, today=today) == "not_released_yet"


def test_classify_on_the_way_shipped() -> None:
    today = date(2026, 6, 1)
    row = _proj(
        order_status="shipped",
        release_status="released",
        release_date=date(2026, 5, 1),
    )
    assert classify_inventory_arrival_lane(row, today=today) == "on_the_way"


def test_classify_released_not_received() -> None:
    today = date(2026, 6, 1)
    row = _proj(
        order_status="ordered",
        release_status="released",
        release_date=date(2026, 5, 1),
        expected_ship_date=None,
    )
    assert classify_inventory_arrival_lane(row, today=today) == "released_not_received"


def test_classify_skips_in_hand_and_cancelled() -> None:
    today = date(2026, 6, 1)
    assert classify_inventory_arrival_lane(_proj(order_status="received"), today=today) is None
    assert classify_inventory_arrival_lane(_proj(order_status="cancelled"), today=today) is None


def test_inventory_arrival_tracking_endpoint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.inventory_arrival_tracking._utc_today",
        lambda: date(2026, 5, 24),
    )
    monkeypatch.setattr(
        "app.services.order_arrival_intelligence._utc_today",
        lambda: date(2026, 5, 24),
    )

    token = inv.register_and_login(client, "arrival-track@example.com")
    hdr = inv.auth_headers(token)

    inv.create_order(
        client,
        token,
        retailer="FutureShop",
        items=[
            {
                "title": "Future Book",
                "publisher": "Marvel",
                "issue_number": "9",
                "cover_name": "A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
                "release_status": "not_released_yet",
                "release_date": "2026-07-15",
                "order_status": "preordered",
            }
        ],
    )

    inv.create_order(
        client,
        token,
        retailer="PastShop",
        items=[
            {
                "title": "Past Release",
                "publisher": "DC",
                "issue_number": "2",
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
            }
        ],
    )

    rsp = client.get("/inventory-arrival-tracking", headers=hdr)
    assert rsp.status_code == 200
    body = rsp.json()
    assert body["summary"]["not_released_yet_count"] >= 1
    assert body["summary"]["released_not_received_count"] >= 1
    assert body["summary"]["not_in_hand_total"] >= 2
    titles = {row["title"] for row in body["not_released_yet_items"]}
    assert "Future Book" in titles
    future = next(row for row in body["not_released_yet_items"] if row["title"] == "Future Book")
    assert future["release_date"] == "2026-07-15"
    assert future["lane"] == "not_released_yet"
