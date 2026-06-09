from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import select

from app.models import (
    DraftImport,
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from app.schemas.ai import ParseOrderResponse
from app.services.retailer_sync.retailer_import_enrichment import enrich_drafts_from_retailer_orders


def test_retailer_order_enrichment_creates_draft_import(session) -> None:
    user = User(email="retailer-draft@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    account = RetailerAccount(
        owner_user_id=int(user.id),
        retailer="midtown",
        display_name="Midtown Comics",
        username="collector@example.com",
        encrypted_password="encrypted",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    order = RetailerOrderSnapshot(
        owner_user_id=int(user.id),
        retailer_account_id=int(account.id),
        retailer="midtown",
        retailer_order_number="ABC123",
        order_date=date(2026, 6, 8),
        order_status="Shipped",
        order_total=Decimal("9.98"),
        raw_snapshot_json={},
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    item = RetailerOrderItemSnapshot(
        owner_user_id=int(user.id),
        retailer_order_snapshot_id=int(order.id),
        retailer="midtown",
        retailer_order_number="ABC123",
        retailer_item_id="SKU-1",
        product_url="https://www.midtowncomics.com/product/1234/immortal-thor-1-cover-a",
        image_url="https://img.example/immortal.jpg",
        thumbnail_url="https://img.example/immortal-thumb.jpg",
        title="Immortal Thor #1 Cover A",
        publisher="Marvel",
        issue_number="1",
        cover_name="Cover A",
        quantity=2,
        unit_price=Decimal("4.99"),
        total_price=Decimal("9.98"),
        item_status="Shipped",
        shipped_qty=2,
        raw_item_json={},
    )
    session.add(item)
    session.commit()

    touched = enrich_drafts_from_retailer_orders(session, account=account, order_snapshots=[order])
    assert len(touched) == 1

    draft = session.exec(select(DraftImport)).one()
    payload = ParseOrderResponse.model_validate(draft.parsed_payload_json)
    assert payload.source_type == "retailer_account"
    assert payload.retailer == "Midtown Comics"
    assert payload.items[0].retailer_order_number == "ABC123"
    assert payload.items[0].retailer_cover_url == "https://img.example/immortal.jpg"
    assert (
        payload.items[0].retailer_product_url
        == "https://www.midtowncomics.com/product/1234/immortal-thor-1-cover-a"
    )
