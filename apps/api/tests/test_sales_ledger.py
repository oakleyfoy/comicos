from __future__ import annotations

from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlmodel import Session

from app.core.config import get_settings
from app.models import (
    InventoryCopy,
    Listing,
    ListingLifecycleEvent,
    MetadataAudit,
    SaleFinancialAdjustment,
    SaleRecord,
    User,
)

from test_inventory import auth_headers, create_order, register_and_login


def _copy_id(client: TestClient, token: str) -> int:
    return int(client.get("/inventory", headers=auth_headers(token)).json()["items"][0]["inventory_copy_id"])


def _ready_listing_id(client: TestClient, token: str, *, title: str = "Sale listing") -> int:
    create_order(client, token)
    cid = _copy_id(client, token)
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": cid,
            "source_type": "manual",
            "title": title,
            "replay_key": f"rk-listing-{uuid.uuid4().hex[:12]}",
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code in (200, 201)
    lid = int(rsp.json()["id"])
    assert client.patch(f"/listings/{lid}", json={"status": "READY"}, headers=auth_headers(token)).status_code == 200
    return lid


def _assert_json_safe_no_decimal(value):
    if isinstance(value, Decimal):
        raise AssertionError(f"unexpected Decimal in JSON metadata: {value}")
    if isinstance(value, dict):
        for nested in value.values():
            _assert_json_safe_no_decimal(nested)
    if isinstance(value, list):
        for nested in value:
            _assert_json_safe_no_decimal(nested)


def test_sale_create_replay_and_metadata_safe(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "sale-replay@example.com")
    lid = _ready_listing_id(client, token)

    rsp = client.post(
        "/sales",
        json={
            "listing_id": lid,
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "usd",
            "buyer_reference": " buyer-1 ",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "29.99"}],
            "financial_adjustments": [
                {"adjustment_type": "shipping_charged", "amount": "5.00", "currency": "usd"},
                {"adjustment_type": "platform_fee", "amount": "1.50", "currency": "usd"},
            ],
            "replay_key": "rk-sale-create-1",
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201
    sale_id = int(rsp.json()["id"])
    assert rsp.json()["status"] == "DRAFT"
    assert rsp.json()["currency"] == "USD"
    assert rsp.json()["buyer_reference"] == "buyer-1"

    dup = client.post(
        "/sales",
        json={
            "listing_id": lid,
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "usd",
            "buyer_reference": "buyer-1",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "29.99"}],
            "financial_adjustments": [
                {"adjustment_type": "shipping_charged", "amount": "5.00", "currency": "usd"},
                {"adjustment_type": "platform_fee", "amount": "1.50", "currency": "usd"},
            ],
            "replay_key": "rk-sale-create-1",
        },
        headers=auth_headers(token),
    )
    assert dup.status_code == 200
    assert int(dup.json()["id"]) == sale_id

    events = client.get(f"/sales/{sale_id}/events", headers=auth_headers(token)).json()["items"]
    assert len(events) == 1
    assert events[0]["event_type"] == "CREATED"
    _assert_json_safe_no_decimal(events[0]["metadata_json"])


def test_sale_math_and_listing_transition(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "sale-record@example.com")
    lid = _ready_listing_id(client, token, title="Recorded sale")
    copy_id = _copy_id(client, token)
    inv = session.get(InventoryCopy, copy_id)
    assert inv is not None
    acquisition_cost = Decimal(str(inv.acquisition_cost))

    rsp = client.post(
        "/sales",
        json={
            "listing_id": lid,
            "channel": "ebay",
            "sale_date": "2026-05-24",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "50.00"}],
            "financial_adjustments": [
                {"adjustment_type": "shipping_charged", "amount": "5.00", "currency": "USD"},
                {"adjustment_type": "tax_collected", "amount": "3.00", "currency": "USD"},
                {"adjustment_type": "platform_fee", "amount": "4.00", "currency": "USD"},
                {"adjustment_type": "payment_fee", "amount": "2.00", "currency": "USD"},
                {"adjustment_type": "shipping_cost", "amount": "5.00", "currency": "USD"},
                {"adjustment_type": "other", "amount": "1.00", "currency": "USD"},
            ],
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201
    sale_id = int(rsp.json()["id"])

    recorded = client.post(f"/sales/{sale_id}/record", headers=auth_headers(token))
    assert recorded.status_code == 200
    body = recorded.json()
    assert body["status"] == "RECORDED"
    assert body["gross_sale_amount"] == "58.00"
    assert body["net_proceeds_amount"] == "46.00"
    assert body["realized_profit_amount"] == str((Decimal("46.00") - acquisition_cost).quantize(Decimal("0.01")))

    sale_row = session.get(SaleRecord, sale_id)
    assert sale_row is not None
    assert sale_row.status == "RECORDED"
    assert sale_row.recorded_at is not None
    assert sale_row.realized_margin_pct is not None

    listing_row = session.get(Listing, lid)
    assert listing_row is not None
    assert listing_row.status == "SOLD"
    assert listing_row.sold_at is not None

    listing_events = session.exec(
        select(ListingLifecycleEvent).where(ListingLifecycleEvent.listing_id == lid, ListingLifecycleEvent.event_type == "SOLD")
    ).all()
    assert len(listing_events) == 1


def test_sale_line_item_and_adjustment_math(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "sale-math@example.com")
    create_order(client, token)

    rsp = client.post(
        "/sales",
        json={
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "usd",
            "line_items": [{"quantity_sold": 2, "unit_sale_amount": "10.00"}],
            "financial_adjustments": [
                {"adjustment_type": "shipping_charged", "amount": "5.00", "currency": "usd"},
                {"adjustment_type": "platform_fee", "amount": "1.00", "currency": "usd"},
                {"adjustment_type": "discount", "amount": "2.00", "currency": "usd"},
            ],
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201
    sale_id = int(rsp.json()["id"])
    assert rsp.json()["gross_sale_amount"] == "23.00"
    assert rsp.json()["net_proceeds_amount"] == "22.00"
    assert rsp.json()["realized_profit_amount"] is None

    sale = session.get(SaleRecord, sale_id)
    assert sale is not None
    assert sale.item_subtotal_amount == Decimal("20.00")
    assert sale.gross_sale_amount == Decimal("23.00")
    adjustment = session.scalar(
        select(func.count(SaleFinancialAdjustment.id)).where(SaleFinancialAdjustment.sale_record_id == sale_id)
    )
    assert int(adjustment or 0) == 3


def test_cannot_record_twice_or_sell_sold_listing_again(client: TestClient) -> None:
    token = register_and_login(client, "sale-dupe@example.com")
    lid = _ready_listing_id(client, token, title="Dupe sale")

    first = client.post(
        "/sales",
        json={
            "listing_id": lid,
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "25.00"}],
        },
        headers=auth_headers(token),
    )
    assert first.status_code == 201
    sale_id = int(first.json()["id"])
    assert client.post(f"/sales/{sale_id}/record", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/sales/{sale_id}/record", headers=auth_headers(token)).status_code == 409

    second = client.post(
        "/sales",
        json={
            "listing_id": lid,
            "channel": "manual",
            "sale_date": "2026-05-25",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "25.00"}],
        },
        headers=auth_headers(token),
    )
    assert second.status_code == 201
    assert client.post(f"/sales/{int(second.json()['id'])}/record", headers=auth_headers(token)).status_code == 409


def test_sale_void_events_and_reads_do_not_mutate_audit(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "sale-ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "sale-void@example.com")
    _ready_listing_id(client, token, title="Void sale")

    created = client.post(
        "/sales",
        json={
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "25.00"}],
        },
        headers=auth_headers(token),
    )
    sale_id = int(created.json()["id"])

    before = session.scalar(select(func.count(MetadataAudit.id)))
    assert client.get(f"/sales/{sale_id}", headers=auth_headers(token)).status_code == 200
    assert client.get(f"/sales/{sale_id}/events", headers=auth_headers(token)).status_code == 200
    assert int(session.scalar(select(func.count(MetadataAudit.id))) or 0) == int(before or 0)

    voided = client.post(f"/sales/{sale_id}/void", headers=auth_headers(token))
    assert voided.status_code == 200
    sale_events = client.get(f"/sales/{sale_id}/events", headers=auth_headers(token)).json()["items"]
    assert {evt["event_type"] for evt in sale_events} >= {"CREATED", "VOIDED"}


def test_sales_owner_and_ops_scope_and_filters(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "sale-ops-filter@example.com")
    get_settings.cache_clear()

    owner_a = register_and_login(client, "sale-owner-a@example.com")
    owner_b = register_and_login(client, "sale-owner-b@example.com")
    ops = register_and_login(client, "sale-ops-filter@example.com")
    create_order(client, owner_a)
    create_order(client, owner_b)

    sale_a = client.post(
        "/sales",
        json={
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "15.00"}],
        },
        headers=auth_headers(owner_a),
    ).json()
    sale_b = client.post(
        "/sales",
        json={
            "channel": "ebay",
            "sale_date": "2026-05-25",
            "currency": "USD",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "18.00"}],
        },
        headers=auth_headers(owner_b),
    ).json()
    client.post(f"/sales/{int(sale_a['id'])}/record", headers=auth_headers(owner_a))
    client.post(f"/sales/{int(sale_b['id'])}/record", headers=auth_headers(owner_b))

    assert client.get(f"/sales/{int(sale_a['id'])}", headers=auth_headers(owner_b)).status_code == 404

    ops_owner_a = client.get(
        "/ops/sales",
        params={"owner_user_id": int(session.scalar(select(User.id).where(User.email == "sale-owner-a@example.com")) or 0)},
        headers=auth_headers(ops),
    )
    assert ops_owner_a.status_code == 200
    assert ops_owner_a.json()["total_items"] == 1

    ops_recorded = client.get("/ops/sales", params={"status": "RECORDED"}, headers=auth_headers(ops))
    assert ops_recorded.status_code == 200
    assert ops_recorded.json()["total_items"] >= 2

    ops_ebay = client.get("/ops/sale-events", params={"channel": "ebay"}, headers=auth_headers(ops))
    assert ops_ebay.status_code == 200
    assert ops_ebay.json()["total_items"] >= 1

    adjustments = client.get("/ops/sale-financial-adjustments", params={"status": "RECORDED"}, headers=auth_headers(ops))
    assert adjustments.status_code == 200
