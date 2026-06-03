"""Inventory receiving workflow: single and bulk mark-received."""

import test_inventory as inv
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy


def test_bulk_mark_received_multiple_ordered_copies(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "bulk-recv@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Alpha",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 2,
                "raw_item_price": 4.0,
            }
        ],
    )
    copy_ids = [int(row.id) for row in session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()]

    before = client.get("/inventory/summary", headers=hdr).json()
    response = client.post(
        "/inventory/bulk-mark-received",
        json={"inventory_copy_ids": copy_ids},
        headers=hdr,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["marked_count"] == 2
    assert body["skipped_count"] == 0
    assert len(body["results"]) == 2
    assert all(r["outcome"] == "marked" for r in body["results"])

    after = client.get("/inventory/summary", headers=hdr).json()
    assert after["in_hand_copies"] == before["in_hand_copies"] + 2
    assert after["ordered_not_received_copies"] == before["ordered_not_received_copies"] - 2


def test_bulk_mark_skips_cancelled_sold_and_already_received(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "bulk-skip@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Open",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 4.0,
            },
            {
                "title": "Dead",
                "publisher": "Image",
                "issue_number": "2",
                "release_date": "2026-01-01",
                "order_status": "cancelled",
                "quantity": 1,
                "raw_item_price": 5.0,
            },
        ],
    )
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    open_copy = next(c for c in copies if c.order_status != "cancelled")
    cancelled_copy = next(c for c in copies if c.order_status == "cancelled")

    client.post(f"/inventory/{open_copy.id}/mark-received", json={}, headers=hdr)

    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Fresh",
                "publisher": "Image",
                "issue_number": "3",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 3.0,
            },
            {
                "title": "Sold line",
                "publisher": "Image",
                "issue_number": "4",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 3.0,
            },
        ],
    )
    pending = session.exec(
        select(InventoryCopy).where(InventoryCopy.order_status == "ordered").order_by(InventoryCopy.id)
    ).all()
    fresh = pending[0]
    sold_row = pending[1]
    sold_row.hold_status = "sold"
    session.add(sold_row)
    session.commit()

    response = client.post(
        "/inventory/bulk-mark-received",
        json={
            "inventory_copy_ids": [
                int(open_copy.id),
                int(cancelled_copy.id),
                int(fresh.id),
                int(sold_row.id),
                999_999,
            ]
        },
        headers=hdr,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["marked_count"] == 2
    assert body["skipped_count"] == 3
    by_id = {r["inventory_copy_id"]: r for r in body["results"]}
    assert by_id[int(cancelled_copy.id)]["outcome"] == "skipped"
    assert by_id[int(cancelled_copy.id)]["detail"] == "cancelled"
    assert by_id[int(sold_row.id)]["outcome"] == "skipped"
    assert by_id[int(sold_row.id)]["detail"] == "sold"
    assert by_id[999_999]["outcome"] == "skipped"
    assert by_id[999_999]["detail"] == "not_found"


def test_bulk_mark_idempotent_rerun(client: TestClient, session: Session) -> None:
    token = inv.register_and_login(client, "bulk-idem@example.com")
    hdr = inv.auth_headers(token)
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Once",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2026-01-01",
                "quantity": 1,
                "raw_item_price": 4.0,
            }
        ],
    )
    copy_id = int(session.exec(select(InventoryCopy.id)).one())

    first = client.post("/inventory/bulk-mark-received", json={"inventory_copy_ids": [copy_id]}, headers=hdr)
    assert first.status_code == 200
    assert first.json()["marked_count"] == 1

    second = client.post("/inventory/bulk-mark-received", json={"inventory_copy_ids": [copy_id]}, headers=hdr)
    assert second.status_code == 200
    assert second.json()["marked_count"] == 1
    assert second.json()["skipped_count"] == 0
    assert second.json()["results"][0]["detail"] == "already_received"
