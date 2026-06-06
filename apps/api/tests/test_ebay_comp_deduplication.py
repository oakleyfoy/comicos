from __future__ import annotations

from decimal import Decimal

from sqlmodel import select

from app.models import EbayCompImportRun, EbayCompRecord, User
from app.services.ebay_sold_search_service import build_ebay_sold_search_request
from app.services.ebay_comp_import_service import import_ebay_comp_results
from test_inventory import register_and_login


def _payload(*, title: str, listing_id: str, price: str) -> dict:
    return {
        "totalEntries": 1,
        "itemSummaries": [
            {
                "itemId": listing_id,
                "title": title,
                "price": {"value": price, "currency": "USD"},
                "shippingOptions": [{"shippingCost": {"value": "4.00", "currency": "USD"}}],
                "endedDate": "2026-06-01T12:34:56.000Z",
                "condition": "Raw",
                "listingType": "FIXED_PRICE",
                "itemWebUrl": "https://example.test/item/999",
            }
        ],
    }


def test_exact_duplicate_import_is_not_reinserted(client, session) -> None:
    register_and_login(client, "ebay-comp-dupe@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "ebay-comp-dupe@example.com")).one())
    search_request = build_ebay_sold_search_request(title="Battle Beast", issue_number="1", publisher="Image", limit=25)
    payload = _payload(title="Battle Beast #1", listing_id="v1|dupe", price="12.00")

    first = import_ebay_comp_results(
        session,
        owner_user_id=owner_id,
        search_request=search_request,
        search_payload=payload,
        search_criteria={"title": "Battle Beast", "issue_number": "1", "publisher": "Image", "limit": 25},
    )
    second = import_ebay_comp_results(
        session,
        owner_user_id=owner_id,
        search_request=search_request,
        search_payload=payload,
        search_criteria={"title": "Battle Beast", "issue_number": "1", "publisher": "Image", "limit": 25},
    )
    session.commit()

    assert first.inserted == 1
    assert second.duplicates == 1
    assert len(session.exec(select(EbayCompRecord).where(EbayCompRecord.owner_user_id == owner_id)).all()) == 1
    assert len(session.exec(select(EbayCompImportRun).where(EbayCompImportRun.owner_user_id == owner_id)).all()) == 2


def test_reimport_updates_existing_comp_without_creating_a_duplicate(client, session) -> None:
    register_and_login(client, "ebay-comp-update@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "ebay-comp-update@example.com")).one())
    search_request = build_ebay_sold_search_request(title="Absolute Batman", issue_number="1", limit=25)
    first_payload = _payload(title="Absolute Batman #1", listing_id="v1|update", price="19.99")
    second_payload = _payload(title="Absolute Batman #1", listing_id="v1|update", price="24.99")

    first = import_ebay_comp_results(
        session,
        owner_user_id=owner_id,
        search_request=search_request,
        search_payload=first_payload,
        search_criteria={"title": "Absolute Batman", "issue_number": "1", "limit": 25},
    )
    second = import_ebay_comp_results(
        session,
        owner_user_id=owner_id,
        search_request=search_request,
        search_payload=second_payload,
        search_criteria={"title": "Absolute Batman", "issue_number": "1", "limit": 25},
    )
    session.commit()

    row = session.exec(select(EbayCompRecord).where(EbayCompRecord.owner_user_id == owner_id)).one()
    assert first.inserted == 1
    assert second.updated == 1
    assert row.sold_price == Decimal("24.99")
    assert row.total_price == Decimal("28.99")
    assert len(session.exec(select(EbayCompRecord).where(EbayCompRecord.owner_user_id == owner_id)).all()) == 1
