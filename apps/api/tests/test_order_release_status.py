from decimal import Decimal

import test_inventory as inv
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy


def test_future_release_date_defaults_to_preorder_states(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "future-preorder@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Transformers",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2099-06-01",
                "quantity": 1,
                "raw_item_price": 4.99,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    assert copy.release_status == "not_released_yet"
    assert copy.order_status == "preordered"

    response = client.get("/inventory?asset_state=preorder_not_released_yet", headers=inv.auth_headers(token))
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["asset_state"] == "preorder_not_released_yet"


def test_past_release_date_defaults_to_released(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "past-release@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2020-01-01",
                "quantity": 1,
                "raw_item_price": 3.99,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    assert copy.release_status == "released"
    assert copy.order_status == "ordered"


def test_missing_release_date_defaults_to_unknown(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "unknown-release@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Radiant Black",
                "publisher": "Image",
                "issue_number": "1",
                "quantity": 1,
                "raw_item_price": 3.99,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    assert copy.release_status == "unknown"
    assert copy.order_status == "ordered"


def test_received_status_marks_copy_in_hand(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "received-state@example.com")
    created = inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2024-01-01",
                "order_status": "received",
                "received_at": "2026-05-24T12:30:00Z",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    detail = client.get(f"/inventory/{created['order_id']}", headers=inv.auth_headers(token))
    assert detail.status_code in {404, 200}
    copy = session.exec(select(InventoryCopy)).one()
    inventory_detail = client.get(f"/inventory/{copy.id}", headers=inv.auth_headers(token))
    assert inventory_detail.status_code == 200
    body = inventory_detail.json()
    assert body["order_status"] == "received"
    assert body["asset_state"] == "in_hand"
    assert body["is_in_hand"] is True


def test_cancelled_copies_excluded_from_in_hand_counts(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "cancelled-counts@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "1",
                "order_status": "received",
                "received_at": "2026-05-24T12:30:00Z",
                "quantity": 1,
                "raw_item_price": 4.99,
            },
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "2",
                "order_status": "cancelled",
                "quantity": 1,
                "raw_item_price": 4.99,
            },
        ],
    )
    summary = client.get("/inventory/summary", headers=inv.auth_headers(token))
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_copies"] == 2
    assert body["in_hand_copies"] == 1
    assert body["cancelled_copies"] == 1


def test_preorder_copy_does_not_require_cover_or_ocr(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "preorder-no-scan@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2099-07-15",
                "quantity": 1,
                "raw_item_price": 3.5,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    detail = client.get(f"/inventory/{copy.id}", headers=inv.auth_headers(token))
    assert detail.status_code == 200
    body = detail.json()
    assert body["asset_state"] == "preorder_not_released_yet"
    assert body["is_in_hand"] is False
    assert body["cover_images"] == []


def test_import_order_inventory_status_fields_round_trip(
    client: TestClient,
) -> None:
    token = inv.register_and_login(client, "roundtrip-release-status@example.com")
    created = client.post(
        "/imports/manual",
        json={
            "raw_text": "preorder import",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Spider-Man",
                    "release_date": "2099-08-01",
                    "issue_number": "1",
                    "order_status": "preordered",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=inv.auth_headers(token),
    )
    assert created.status_code == 201
    item = created.json()["parsed_payload_json"]["items"][0]
    assert item["release_status"] == "not_released_yet"
    assert item["order_status"] == "preordered"
    assert item["purchase_date"] == "2026-05-21"

    confirmed = client.post(
        f"/imports/{created.json()['id']}/confirm",
        headers=inv.auth_headers(token),
    )
    assert confirmed.status_code == 200

    order_detail = client.get(f"/orders/{confirmed.json()['order_id']}", headers=inv.auth_headers(token))
    assert order_detail.status_code == 200
    order_item = order_detail.json()["items"][0]
    assert order_item["release_status"] == "not_released_yet"
    assert order_item["order_status"] == "preordered"
    assert order_item["asset_state"] == "preorder_not_released_yet"

    inventory_id = order_item["inventory_copy_ids"][0]
    inv_detail = client.get(f"/inventory/{inventory_id}", headers=inv.auth_headers(token))
    assert inv_detail.status_code == 200
    assert inv_detail.json()["order_status"] == "preordered"
    assert inv_detail.json()["release_status"] == "not_released_yet"


def test_release_status_fields_do_not_change_metadata_identity_key(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "release-status-no-key-mutation@example.com")
    inv.create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2099-06-01",
                "quantity": 1,
                "raw_item_price": 5.00,
            },
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2020-01-01",
                "order_status": "received",
                "received_at": "2026-05-24T00:00:00Z",
                "quantity": 1,
                "raw_item_price": 5.00,
            },
        ],
    )
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id.asc())).all()
    assert len(copies) == 2
    assert copies[0].metadata_identity_key == copies[1].metadata_identity_key
    assert Decimal(str(copies[0].acquisition_cost)) == Decimal("5.00")
