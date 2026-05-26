from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import InventoryLiquiditySnapshot, ListingStalenessEvent, ListingVelocitySnapshot
from app.services.liquidity_engine import _liquidity_status, _quantize_money, _quantize_pct
from test_inventory import auth_headers, create_order, register_and_login


def _inventory_copy_id(client: TestClient, token: str) -> int:
    response = client.get("/inventory", headers=auth_headers(token))
    assert response.status_code == 200
    return int(response.json()["items"][0]["inventory_copy_id"])


def _create_and_activate_listing(
    client: TestClient,
    token: str,
    inventory_copy_id: int,
    *,
    source_type: str,
    title: str,
    price: str,
    replay_prefix: str,
) -> int:
    create = client.post(
        "/listings",
        json={
            "inventory_copy_id": inventory_copy_id,
            "source_type": source_type,
            "title": title,
            "asking_price_amount": price,
            "asking_price_currency": "usd",
            "replay_key": f"{replay_prefix}-create",
        },
        headers=auth_headers(token),
    )
    assert create.status_code == 201
    listing_id = int(create.json()["id"])

    ready = client.patch(
        f"/listings/{listing_id}",
        json={"status": "READY", "replay_key": f"{replay_prefix}-ready"},
        headers=auth_headers(token),
    )
    assert ready.status_code == 200

    active = client.post(
        f"/listings/{listing_id}/activate",
        json={"replay_key": f"{replay_prefix}-activate"},
        headers=auth_headers(token),
    )
    assert active.status_code == 200
    return listing_id


def _create_and_record_sale(client: TestClient, token: str, listing_id: int, *, replay_prefix: str) -> int:
    create = client.post(
        "/sales",
        json={
            "listing_id": listing_id,
            "channel": "manual",
            "sale_date": "2026-05-24",
            "currency": "usd",
            "line_items": [{"quantity_sold": 1, "unit_sale_amount": "29.99"}],
            "financial_adjustments": [
                {"adjustment_type": "shipping_charged", "amount": "5.00", "currency": "usd"},
                {"adjustment_type": "platform_fee", "amount": "1.50", "currency": "usd"},
            ],
            "replay_key": f"{replay_prefix}-sale-create",
        },
        headers=auth_headers(token),
    )
    assert create.status_code == 201
    sale_id = int(create.json()["id"])

    record = client.post(f"/sales/{sale_id}/record", headers=auth_headers(token))
    assert record.status_code == 200
    return sale_id


def test_liquidity_snapshot_generation_is_idempotent(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "liq-owner@example.com")
    create_order(client, token)
    inventory_copy_id = _inventory_copy_id(client, token)

    first_listing = _create_and_activate_listing(
        client,
        token,
        inventory_copy_id,
        source_type="manual",
        title="Manual sale listing",
        price="12.00",
        replay_prefix="liq-first",
    )
    _create_and_record_sale(client, token, first_listing, replay_prefix="liq-first")

    _create_and_activate_listing(
        client,
        token,
        inventory_copy_id,
        source_type="ebay_export",
        title="Ebay relist",
        price="14.00",
        replay_prefix="liq-second",
    )

    snapshot_date = "2026-09-30"
    first = client.get(
        "/liquidity",
        params={"snapshot_date": snapshot_date, "limit": "20", "offset": "0"},
        headers=auth_headers(token),
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["items"]

    snapshot_count = session.scalar(select(func.count(InventoryLiquiditySnapshot.id))) or 0
    second = client.get(
        "/liquidity",
        params={"snapshot_date": snapshot_date, "limit": "20", "offset": "0"},
        headers=auth_headers(token),
    )
    assert second.status_code == 200
    second_payload = second.json()

    assert len(second_payload["items"]) == len(first_payload["items"])
    assert [row["checksum"] for row in second_payload["items"]] == [row["checksum"] for row in first_payload["items"]]
    assert (session.scalar(select(func.count(InventoryLiquiditySnapshot.id))) or 0) == snapshot_count

    evidence = client.get(
        "/liquidity/evidence",
        params={"snapshot_date": snapshot_date, "limit": "100", "offset": "0"},
        headers=auth_headers(token),
    )
    assert evidence.status_code == 200
    assert evidence.json()["total_items"] >= 1

    velocity = client.get("/listing-velocity", params={"limit": "100", "offset": "0"}, headers=auth_headers(token))
    assert velocity.status_code == 200
    assert velocity.json()["items"]

    staleness = client.get(
        "/listing-staleness-events",
        params={"snapshot_date_from": "2026-09-01", "limit": "100", "offset": "0"},
        headers=auth_headers(token),
    )
    assert staleness.status_code == 200


def test_liquidity_staleness_events_and_channel_filtering(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "liq-stale@example.com")
    create_order(client, token)
    inventory_copy_id = _inventory_copy_id(client, token)

    _create_and_activate_listing(
        client,
        token,
        inventory_copy_id,
        source_type="manual",
        title="Private sale listing",
        price="10.00",
        replay_prefix="liq-stale-manual",
    )
    _create_and_activate_listing(
        client,
        token,
        inventory_copy_id,
        source_type="ebay_export",
        title="Ebay stale listing",
        price="11.00",
        replay_prefix="liq-stale-ebay",
    )

    response = client.get(
        "/liquidity",
        params={"snapshot_date": "2026-10-31", "channel": "private_sale", "limit": "20", "offset": "0"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert {row["channel"] for row in response.json()["items"]} == {"private_sale"}

    response = client.get(
        "/liquidity",
        params={"snapshot_date": "2026-10-31", "channel": "ebay", "limit": "20", "offset": "0"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert {row["channel"] for row in response.json()["items"]} == {"ebay"}

    events = session.exec(select(ListingStalenessEvent)).all()
    assert events
    assert {row.event_type for row in events} <= {"STALE_WARNING", "STALE_CONFIRMED", "LONG_RUNNING"}

    velocity_rows = session.exec(select(ListingVelocitySnapshot)).all()
    assert velocity_rows
    assert all(row.days_active is not None for row in velocity_rows)


def test_liquidity_classification_and_rounding_helpers() -> None:
    assert _quantize_money(Decimal("1.005")) == Decimal("1.01")
    assert _quantize_pct(Decimal("12.345")) == Decimal("12.35")
    assert (
        _liquidity_status(
            successful_sale_count=6,
            failed_listing_count=1,
            active_listing_count=0,
            sell_through_rate_pct=Decimal("80.00"),
            stale_listing_rate_pct=Decimal("10.00"),
            relist_rate_pct=Decimal("5.00"),
        )
        == "HIGH"
    )
    assert (
        _liquidity_status(
            successful_sale_count=0,
            failed_listing_count=4,
            active_listing_count=1,
            sell_through_rate_pct=Decimal("0.00"),
            stale_listing_rate_pct=Decimal("75.00"),
            relist_rate_pct=Decimal("10.00"),
        )
        == "ILLIQUID"
    )
    assert (
        _liquidity_status(
            successful_sale_count=1,
            failed_listing_count=1,
            active_listing_count=0,
            sell_through_rate_pct=Decimal("50.00"),
            stale_listing_rate_pct=Decimal("25.00"),
            relist_rate_pct=Decimal("20.00"),
        )
        == "INSUFFICIENT_DATA"
    )


def test_liquidity_owner_and_ops_visibility(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "liq-admin@example.com")

    owner_a = register_and_login(client, "liq-owner-a@example.com")
    owner_b = register_and_login(client, "liq-owner-b@example.com")
    admin = register_and_login(client, "liq-admin@example.com")

    for token, prefix in ((owner_a, "a"), (owner_b, "b")):
        create_order(client, token)
        inventory_copy_id = _inventory_copy_id(client, token)
        _create_and_activate_listing(
            client,
            token,
            inventory_copy_id,
            source_type="manual",
            title=f"Owner {prefix} listing",
            price="9.00",
            replay_prefix=f"liq-{prefix}",
        )
        client.get(
            "/liquidity",
            params={"snapshot_date": "2026-09-30", "limit": "10", "offset": "0"},
            headers=auth_headers(token),
        )

    owner_a_rows = client.get("/liquidity", headers=auth_headers(owner_a))
    owner_b_rows = client.get("/liquidity", headers=auth_headers(owner_b))
    assert owner_a_rows.status_code == 200
    assert owner_b_rows.status_code == 200
    assert all(row["owner_user_id"] == int(owner_a_rows.json()["items"][0]["owner_user_id"]) for row in owner_a_rows.json()["items"])
    assert all(row["owner_user_id"] == int(owner_b_rows.json()["items"][0]["owner_user_id"]) for row in owner_b_rows.json()["items"])

    ops_rows = client.get("/ops/liquidity", headers=auth_headers(admin))
    assert ops_rows.status_code == 200
    owners = {row["owner_user_id"] for row in ops_rows.json()["items"]}
    assert len(owners) >= 2
