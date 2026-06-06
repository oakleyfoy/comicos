from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant
from app.models.external_catalog import ExternalCatalogIssue
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from test_inventory import auth_headers, register_and_login


def _seed_sell_copy(session: Session, *, owner_user_id: int, copies: int = 3) -> int:
    pub = Publisher(name="DC")
    session.add(pub)
    session.flush()
    ct = ComicTitle(name="Absolute Batman", publisher_id=int(pub.id or 0))
    session.add(ct)
    session.flush()
    issue = ComicIssue(comic_title_id=int(ct.id or 0), issue_number="1")
    session.add(issue)
    session.flush()
    variant = Variant(comic_issue_id=int(issue.id or 0), cover_name="Cover A")
    session.add(variant)
    session.flush()
    order = Order(
        user_id=owner_user_id,
        retailer="Shop",
        order_date=date(2026, 5, 1),
        source_type="manual",
        shipping_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("15"),
    )
    session.add(order)
    session.flush()
    item = OrderItem(
        order_id=int(order.id or 0),
        variant_id=int(variant.id or 0),
        quantity=1,
        raw_item_price=Decimal("5"),
        allocated_shipping=Decimal("0"),
        allocated_tax=Decimal("0"),
        all_in_unit_cost=Decimal("5"),
    )
    session.add(item)
    session.flush()
    first_id = None
    for n in range(1, copies + 1):
        copy = InventoryCopy(
            user_id=owner_user_id,
            order_item_id=int(item.id or 0),
            variant_id=int(variant.id or 0),
            copy_number=n,
            acquisition_cost=Decimal("5"),
            release_status="released",
            order_status="received",
            grade_status="raw",
            hold_status="hold",
            current_fmv=Decimal("32"),
        )
        session.add(copy)
        session.flush()
        if first_id is None:
            first_id = int(copy.id or 0)
            session.add(
                ExternalCatalogIssue(
                    source_name="TEST",
                    source_issue_id=f"abs-bat-1-{n}",
                    title="Absolute Batman #1",
                    series_name="Absolute Batman",
                    issue_number="1",
                    publisher="DC",
                    upc="012345678901",
                )
            )
            session.add(
                P68MarketPriceSnapshot(
                    owner_user_id=owner_user_id,
                    inventory_copy_id=first_id,
                    blended_fmv=Decimal("32"),
                    median_sale=Decimal("30"),
                    average_sale=Decimal("31"),
                    sales_count=8,
                    liquidity_score=72.0,
                    confidence=0.8,
                    price_trend_30d="RISING",
                    primary_provider="TEST",
                    metadata_json={"sales_velocity": 3.2, "liquidity_band": "HIGH"},
                )
            )
    session.commit()
    return int(first_id or 0)


def test_sell_queue_and_quantities(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-queue@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-queue@example.com")).one().id or 0)
    _seed_sell_copy(session, owner_user_id=owner_id, copies=5)
    client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={"default_copy_count": 2},
    )
    response = client.get("/api/v1/sell-queue", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["items"]
    row = data["items"][0]
    assert row["priority"] in {"HIGH", "MEDIUM", "WATCH"}
    assert row["owned_copies"] >= 3
    assert row["target_hold_copies"] == 2


def test_listing_draft_and_pricing(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-draft@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-draft@example.com")).one().id or 0)
    copy_id = _seed_sell_copy(session, owner_user_id=owner_id, copies=1)
    create = client.post(
        "/api/v1/listing-drafts",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "status": "DRAFT"},
    )
    assert create.status_code == 201, create.text
    draft = create.json()["data"]
    assert draft["title"]
    assert draft["quick_sale_price"] > 0
    assert draft["market_price"] > 0
    assert draft["premium_price"] > draft["market_price"]

    pricing = client.get(f"/api/v1/listing-drafts/{draft['id']}/pricing", headers=auth_headers(token))
    assert pricing.status_code == 200
    assert pricing.json()["data"]["fmv"] >= 0

    update = client.put(
        f"/api/v1/listing-drafts/{draft['id']}",
        headers=auth_headers(token),
        json={"status": "READY", "title": "Absolute Batman #1 NM DC"},
    )
    assert update.status_code == 200
    assert update.json()["data"]["status"] == "READY"


def test_sell_bundles(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-bundle@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-bundle@example.com")).one().id or 0)
    _seed_sell_copy(session, owner_user_id=owner_id, copies=4)
    bundles = client.get("/api/v1/sell-queue/bundles", headers=auth_headers(token))
    assert bundles.status_code == 200
    assert "items" in bundles.json()["data"]
