from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant
from app.models.external_catalog import ExternalCatalogIssue
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from test_inventory import auth_headers, register_and_login


def _seed_copy(session: Session, *, owner_user_id: int, upc: str | None = None, copy_number: int = 1) -> int:
    pub = Publisher(name="Marvel")
    session.add(pub)
    session.flush()
    title = ComicTitle(name="Battle Beast", publisher_id=int(pub.id or 0))
    session.add(title)
    session.flush()
    issue = ComicIssue(comic_title_id=int(title.id or 0), issue_number="1")
    session.add(issue)
    session.flush()
    variant = Variant(comic_issue_id=int(issue.id or 0), cover_name="Cover A")
    session.add(variant)
    session.flush()
    order = Order(
        user_id=owner_user_id,
        retailer="Test Shop",
        order_date=date(2026, 6, 1),
        source_type="manual",
        shipping_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("10"),
    )
    session.add(order)
    session.flush()
    item = OrderItem(
        order_id=int(order.id or 0),
        variant_id=int(variant.id or 0),
        quantity=1,
        raw_item_price=Decimal("10"),
        allocated_shipping=Decimal("0"),
        allocated_tax=Decimal("0"),
        all_in_unit_cost=Decimal("10"),
    )
    session.add(item)
    session.flush()
    copy = InventoryCopy(
        user_id=owner_user_id,
        order_item_id=int(item.id or 0),
        variant_id=int(variant.id or 0),
        copy_number=copy_number,
        acquisition_cost=Decimal("10"),
        release_status="released",
        order_status="received",
        grade_status="raw",
        hold_status="hold",
        current_fmv=Decimal("28"),
    )
    session.add(copy)
    session.flush()
    if upc and copy_number == 1:
        session.add(
            ExternalCatalogIssue(
                source_name="TEST",
                title="Battle Beast #1",
                publisher="Marvel",
                series_name="Battle Beast",
                issue_number="1",
                normalized_title_key="battle-beast-1",
                importance_signals_json={"upc": upc},
            )
        )
        session.flush()
    if copy_number == 1:
        session.add(
            P68MarketPriceSnapshot(
                owner_user_id=owner_user_id,
                inventory_copy_id=int(copy.id or 0),
                raw_fmv=28.0,
                blended_fmv=28.0,
                confidence=0.82,
                liquidity_score=72.0,
                sales_count=8,
                primary_provider="EBAY_SOLD",
                price_trend_30d="RISING",
                price_trend_90d="STABLE",
            )
        )
        session.add(
            HoldSellRecommendation(
                owner_user_id=owner_user_id,
                inventory_item_id=int(copy.id or 0),
                recommendation="HOLD",
                conviction_score=91.0,
                confidence_score=0.77,
                estimated_fmv=28.0,
                acquisition_cost=10.0,
                unrealized_gain=18.0,
                rationale="Strong hold candidate.",
            )
        )
    session.commit()
    return int(copy.id or 0)


def test_collector_scan_ownership_and_action_card(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-collector@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p80-collector@example.com")).one().id or 0)
    _seed_copy(session, owner_user_id=owner_id, upc="012345678905")

    response = client.post(
        "/api/v1/collector/scan",
        headers=auth_headers(token),
        json={"barcode": "012345678905"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["book_intelligence"]["ownership"]["total_copies"] == 1
    assert data["book_intelligence"]["fmv"]["authoritative_fmv"] == 28.0
    assert data["action_card"]["action"] in {"HOLD", "GRADE", "WATCH", "BUY", "PASS"}


def test_collector_price_evaluation_great_buy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-price@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p80-price@example.com")).one().id or 0)
    copy_id = _seed_copy(session, owner_user_id=owner_id, upc="012345678912")

    scan = client.post(
        "/api/v1/collector/scan",
        headers=auth_headers(token),
        json={"barcode": "012345678912", "vendor_price": 15},
    )
    assert scan.status_code == 200, scan.text
    assessment = scan.json()["data"]["price_assessment"]
    assert assessment["assessment"] == "GREAT_BUY"
    assert assessment["spread_percent"] is not None
    assert assessment["spread_percent"] > 50

    eval_resp = client.post(
        "/api/v1/collector/evaluate-price",
        headers=auth_headers(token),
        json={"inventory_id": copy_id, "asking_price": 15},
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["data"]["price_assessment"]["assessment"] == "GREAT_BUY"


def test_collector_duplicate_ownership_pass(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-dup@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p80-dup@example.com")).one().id or 0)
    first_id = _seed_copy(session, owner_user_id=owner_id, upc="012345678999")
    first = session.get(InventoryCopy, first_id)
    assert first is not None
    for n in range(2, 5):
        session.add(
            InventoryCopy(
                user_id=owner_id,
                order_item_id=first.order_item_id,
                variant_id=first.variant_id,
                copy_number=n,
                acquisition_cost=Decimal("10"),
                release_status="released",
                order_status="received",
                grade_status="raw",
                hold_status="hold",
                current_fmv=Decimal("28"),
            )
        )
    session.commit()

    response = client.post(
        "/api/v1/collector/scan",
        headers=auth_headers(token),
        json={"barcode": "012345678999", "vendor_price": 30},
    )
    assert response.status_code == 200, response.text
    card = response.json()["data"]["action_card"]
    assert card["action"] == "PASS"
    assert card["inventory_target_exceeded"] is True


def test_collector_dashboard_and_gaps(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-dash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p80-dash@example.com")).one().id or 0)
    _seed_copy(session, owner_user_id=owner_id, upc="012345678920")

    gaps = client.get("/api/v1/collector/gaps", headers=auth_headers(token))
    assert gaps.status_code == 200
    assert "items" in gaps.json()["data"]

    dashboard = client.get("/api/v1/collector/dashboard", headers=auth_headers(token))
    assert dashboard.status_code == 200
    body = dashboard.json()["data"]
    assert "gap_summary" in body
    assert "collection_gaps" in body

    opps = client.get("/api/v1/collector/opportunities", headers=auth_headers(token))
    assert opps.status_code == 200
