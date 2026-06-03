"""Physical intake / receiving workflow (explicit mutations, deterministic classifications)."""

from datetime import date, datetime, timedelta, timezone

import pytest
import test_inventory as inv
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy, ScanSession
from app.services.order_arrival_intelligence import OrderArrivalProjectionRow
from app.services.physical_intake import derive_physical_intake_state


def test_derived_intake_states_for_common_rows() -> None:
    today = date(2026, 5, 24)
    preorder = OrderArrivalProjectionRow(
        inventory_copy_id=1,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="1",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today + timedelta(days=30),
        release_status="not_released_yet",
        order_status="preordered",
        expected_ship_date=None,
        received_at=None,
        asset_state="preorder_not_released_yet",
    )
    assert derive_physical_intake_state(
        preorder,
        today=today,
        has_cover_scan=False,
        ocr_complete_on_primary_cover=False,
    ) == "awaiting_release"

    released_waiting = OrderArrivalProjectionRow(
        inventory_copy_id=2,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="2",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today - timedelta(days=10),
        release_status="released",
        order_status="ordered",
        expected_ship_date=None,
        received_at=None,
        asset_state="ordered_not_received",
    )
    assert derive_physical_intake_state(
        released_waiting,
        today=today,
        has_cover_scan=False,
        ocr_complete_on_primary_cover=False,
    ) == "released_awaiting_receipt"

    blocked = OrderArrivalProjectionRow(
        inventory_copy_id=3,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="3",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today - timedelta(days=10),
        release_status="released",
        order_status="ordered",
        expected_ship_date=today - timedelta(days=3),
        received_at=None,
        asset_state="ordered_not_received",
    )
    assert derive_physical_intake_state(blocked, today=today, has_cover_scan=False, ocr_complete_on_primary_cover=False) == "intake_blocked"

    recv_no_scan = OrderArrivalProjectionRow(
        inventory_copy_id=4,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="4",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today - timedelta(days=10),
        release_status="released",
        order_status="received",
        expected_ship_date=None,
        received_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        asset_state="in_hand",
    )
    assert derive_physical_intake_state(
        recv_no_scan,
        today=today,
        has_cover_scan=False,
        ocr_complete_on_primary_cover=False,
    ) == "received_pending_scan"

    recv_scanned_pending_ocr = OrderArrivalProjectionRow(
        inventory_copy_id=recv_no_scan.inventory_copy_id,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="4",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today - timedelta(days=10),
        release_status="released",
        order_status="received",
        expected_ship_date=None,
        received_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        asset_state="in_hand",
    )
    assert derive_physical_intake_state(
        recv_scanned_pending_ocr,
        today=today,
        has_cover_scan=True,
        ocr_complete_on_primary_cover=False,
    ) == "received_scanned"

    recv_done = OrderArrivalProjectionRow(
        inventory_copy_id=recv_no_scan.inventory_copy_id,
        owner_user_id=1,
        retailer="Shop",
        source_type=None,
        publisher="P",
        title="T",
        issue_number="4",
        order_item_quantity=1,
        purchase_date=today,
        release_date=today - timedelta(days=10),
        release_status="released",
        order_status="received",
        expected_ship_date=None,
        received_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        asset_state="in_hand",
    )
    assert derive_physical_intake_state(
        recv_done,
        today=today,
        has_cover_scan=True,
        ocr_complete_on_primary_cover=True,
    ) == "completed"


def test_mark_received_requires_explicit_endpoint(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "pi-received@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "X",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 4.0,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    canon_before = copy.canonical_series_id
    meta_before = copy.metadata_identity_key

    sessions_before = session.exec(select(func.count()).select_from(ScanSession)).one()

    explicit_ts = "2026-05-20T15:00:00+00:00"
    response = client.post(
        f"/inventory/{copy.id}/mark-received",
        json={"received_at": explicit_ts},
        headers=hdr,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["order_status"] == "received"
    assert body["asset_state"] == "in_hand"
    assert body["received_at"] is not None

    session.expire_all()
    refreshed = session.get(InventoryCopy, copy.id)
    assert refreshed is not None
    assert refreshed.order_status == "received"
    assert refreshed.received_at is not None
    assert refreshed.canonical_series_id == canon_before
    assert refreshed.metadata_identity_key == meta_before

    sessions_after = session.exec(select(func.count()).select_from(ScanSession)).one()
    assert sessions_after == sessions_before

    dup = client.post(f"/inventory/{copy.id}/mark-received", json={}, headers=hdr)
    assert dup.status_code == 200


def test_mark_received_owner_scoped(client: TestClient, session: Session) -> None:
    a = inv.register_and_login(client, "pi-a@example.com")
    b = inv.register_and_login(client, "pi-b@example.com")
    inv.create_order(
        client,
        a,
        items=[
            {
                "title": "Solo",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    copy_id = session.exec(select(InventoryCopy.id)).first()
    assert copy_id is not None
    response = client.post(f"/inventory/{copy_id}/mark-received", json={}, headers=inv.auth_headers(b))
    assert response.status_code == 404


def test_physical_intake_released_not_received_bucket(client: TestClient) -> None:
    token = inv.register_and_login(client, "pi-bucket@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Bucket",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    summary = client.get("/physical-intake/summary", headers=hdr).json()
    assert summary["counts"]["released_not_received"] >= 1
    lst = client.get("/physical-intake", headers=hdr).json()
    assert any("released_not_received" in row["order_arrival_classifications"] for row in lst["items"])

    filt = client.get("/physical-intake?intake_state=released_awaiting_receipt", headers=hdr).json()
    assert filt["items"]


def test_create_intake_scan_session_from_received_only(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "pi-session@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Ses",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    copy_id = session.exec(select(InventoryCopy.id)).one()

    deny = client.post(
        "/physical-intake/create-scan-session",
        json={"inventory_copy_ids": [copy_id]},
        headers=hdr,
    )
    assert deny.status_code == 400

    client.post(f"/inventory/{copy_id}/mark-received", json={}, headers=hdr)

    ok = client.post(
        "/physical-intake/create-scan-session",
        json={"inventory_copy_ids": [copy_id]},
        headers=hdr,
    )
    assert ok.status_code == 200
    detail = ok.json()
    assert detail["session_type"] == "intake_receiving"
    assert detail["statistics"]["total_scans"] == 1
    assert detail["items"][0]["inventory_copy_id"] == copy_id
    assert detail["items"][0]["ingest_status"] == "pending"


def test_cannot_queue_cancelled_line(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "pi-cancel-q@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Cx",
                "publisher": "Image",
                "issue_number": "1",
                "order_status": "cancelled",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    copy_id = session.exec(select(InventoryCopy.id)).one()
    deny = client.post("/physical-intake/create-scan-session", json={"inventory_copy_ids": [copy_id]}, headers=hdr)
    assert deny.status_code == 400


def test_ops_physical_intake_requires_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "pi-ops@example.com")
    get_settings.cache_clear()
    normal = inv.register_and_login(client, "pi-normal@example.com")
    ops = inv.register_and_login(client, "pi-ops@example.com")

    denied = client.get("/ops/physical-intake/summary", headers=inv.auth_headers(normal))
    assert denied.status_code == 403

    allowed = client.get("/ops/physical-intake/summary", headers=inv.auth_headers(ops))
    assert allowed.status_code == 200
