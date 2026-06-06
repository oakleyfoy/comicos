"""P80-01 mobile scanning platform integration tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant
from app.models.external_catalog import ExternalCatalogIssue
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.services.storage_label_service import build_storage_label
from test_inventory import auth_headers, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _seed_copy(session: Session, *, owner_user_id: int, upc: str | None = None) -> int:
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
        copy_number=1,
        acquisition_cost=Decimal("10"),
        release_status="released",
        order_status="received",
        grade_status="raw",
        hold_status="hold",
        current_fmv=Decimal("42"),
    )
    session.add(copy)
    session.flush()
    if upc:
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
    session.add(
        P68MarketPriceSnapshot(
            owner_user_id=owner_user_id,
            inventory_copy_id=int(copy.id or 0),
            raw_fmv=42.0,
            blended_fmv=45.0,
            confidence=0.82,
            liquidity_score=68.0,
            sales_count=6,
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
            conviction_score=88.0,
            confidence_score=0.77,
            estimated_fmv=45.0,
            acquisition_cost=10.0,
            unrealized_gain=35.0,
            rationale="Strong hold candidate.",
        )
    )
    session.commit()
    return int(copy.id or 0)


def test_mobile_scan_upc_identification_and_intelligence(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-scan@example.com")
    from sqlmodel import select

    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p80-scan@example.com")).one().id or 0)
    copy_id = _seed_copy(session, owner_user_id=owner_id, upc="012345678905")

    scan = client.post(
        "/api/v1/mobile/scan",
        headers=auth_headers(token),
        json={"barcode": "012345678905"},
    )
    assert scan.status_code == 201, scan.text
    data = scan.json()["data"]
    assert data["identification"]["confidence"] in {"HIGH", "MEDIUM"}
    assert data["book_intelligence"]["ownership"]["owned"] is True
    assert data["book_intelligence"]["ownership"]["total_copies"] == 1
    assert data["book_intelligence"]["fmv"]["authoritative_fmv"] == 45.0
    assert data["book_intelligence"]["recommendation"]["recommendation"] == "HOLD"
    assert data["book_intelligence"]["action_card"]["action"] in {"HOLD", "STORE", "GRADE", "WATCH"}
    scan_id = data["scan_id"]

    loaded = client.get(f"/api/v1/mobile/scan/{scan_id}", headers=auth_headers(token))
    assert loaded.status_code == 200
    assert loaded.json()["data"]["scan_id"] == scan_id

    book = client.get(f"/api/v1/mobile/book/{copy_id}", headers=auth_headers(token))
    assert book.status_code == 200
    assert book.json()["data"]["ownership"]["total_copies"] == 1


def test_mobile_scan_p79_qr_storage_entity(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-qr@example.com")
    from sqlmodel import select

    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p80-qr@example.com")).one().id or 0)
    copy_id = _seed_copy(session, owner_user_id=owner_id)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    from app.services.storage_assignment_service import assign_inventory_copy

    assign_inventory_copy(
        session,
        owner_user_id=owner_id,
        inventory_copy_id=copy_id,
        box_id=box_id,
        use_suggested_slot=True,
        assigned_by_user_id=owner_id,
    )
    session.commit()
    label = build_storage_label(session, owner_user_id=owner_id, entity_type="box", entity_id=box_id)

    scan = client.post(
        "/api/v1/mobile/scan",
        headers=auth_headers(token),
        json={"barcode": label.qr_payload},
    )
    assert scan.status_code == 201, scan.text
    body = scan.json()["data"]
    assert body["identification"]["scan_source"] == "QR_STORAGE"
    assert body["identification"]["storage_entity"]["entity_type"] == "box"
    assert body["book_intelligence"] is not None


def test_mobile_scan_isolation(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "p80-owner@example.com")
    outsider = register_and_login(client, "p80-outsider@example.com")
    from sqlmodel import select

    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p80-owner@example.com")).one().id or 0)
    copy_id = _seed_copy(session, owner_user_id=owner_id, upc="9780316383129")

    denied = client.get(f"/api/v1/mobile/book/{copy_id}", headers=auth_headers(outsider))
    assert denied.status_code == 404
