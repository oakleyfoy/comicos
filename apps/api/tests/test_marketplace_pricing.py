from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MarketplaceOffer, MarketplacePriceRecommendation, MarketplacePricingEvent, MarketplacePricingRule
from app.services.marketplace_pricing_rules import evaluate_pricing_rules
from test_inventory import auth_headers, create_order, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _inventory_copy_id(client: TestClient, token: str) -> int:
    create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=1", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    return int(listing.json()["items"][0]["inventory_copy_id"])


def _connect_marketplace(client: TestClient, token: str, organization_id: int, suffix: str) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": "ebay",
            "marketplace_account_id": f"ebay-pricing-{suffix}",
            "display_name": "Pricing eBay",
            "credential_type": "oauth_token",
            "credential_reference": f"vault://marketplace/ebay-pricing-{suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["account"]["id"])


def _create_listing(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    account_id: int,
    inventory_item_id: int,
    title: str = "Pricing Test Listing",
    price: str = "10.00",
) -> int:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-listings",
        headers=auth_headers(token),
        json={
            "marketplace_account_id": account_id,
            "inventory_item_id": inventory_item_id,
            "listing_title": title,
            "listing_description": "Pricing test listing",
            "listing_price": price,
            "listing_currency": "USD",
            "listing_quantity": 1,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["draft"]["id"])


def test_pricing_rule_creation_evaluation_generation_and_review(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-pricing-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-pricing-org")
    account_id = _connect_marketplace(client, owner, organization_id, "rules")
    inventory_item_id = _inventory_copy_id(client, owner)
    listing_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id)

    fixed_margin = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/rules",
        headers=auth_headers(owner),
        json={
            "rule_key": "fixed_margin_20",
            "rule_name": "Fixed margin twenty",
            "rule_status": "active",
            "rule_payload_json": {"rule_type": "fixed_margin", "margin_amount": "2.00", "priority": 10},
        },
    )
    minimum_floor = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/rules",
        headers=auth_headers(owner),
        json={
            "rule_key": "minimum_floor_15",
            "rule_name": "Minimum floor fifteen",
            "rule_status": "active",
            "rule_payload_json": {"rule_type": "minimum_floor", "floor_price": "15.00", "priority": 20},
        },
    )
    assert fixed_margin.status_code == 201, fixed_margin.text
    assert minimum_floor.status_code == 201, minimum_floor.text

    session.expire_all()
    rules = session.exec(
        select(MarketplacePricingRule)
        .where(MarketplacePricingRule.organization_id == organization_id)
        .order_by(MarketplacePricingRule.created_at.asc(), MarketplacePricingRule.id.asc())
    ).all()
    evaluation = evaluate_pricing_rules(current_listing_price=Decimal("10.00"), pricing_rules=rules)
    assert evaluation.recommended_price == Decimal("15.00")
    assert evaluation.applied_rule_keys == ("fixed_margin_20", "minimum_floor_15")

    generated = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/recommendations/generate",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "marketplace_listing_draft_id": listing_id,
            "recommendation_type": "suggested_price",
            "current_listing_price": "10.00",
        },
    )
    assert generated.status_code == 201, generated.text
    recommendation = generated.json()["data"]
    assert recommendation["recommended_price"] == "15.00"
    assert recommendation["recommendation_status"] == "generated"

    reviewed = client.patch(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/recommendations/{recommendation['id']}/review",
        headers=auth_headers(owner),
        json={"recommendation_status": "applied_internal", "review_reason": "Internal approval"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["recommendation_status"] == "applied_internal"
    assert reviewed.json()["data"]["reviewed_at"] is not None

    updated_rule = client.patch(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/rules/{int(fixed_margin.json()['data']['id'])}",
        headers=auth_headers(owner),
        json={"rule_status": "inactive", "rule_name": "Fixed margin twenty updated"},
    )
    assert updated_rule.status_code == 200, updated_rule.text
    assert updated_rule.json()["data"]["rule_status"] == "inactive"
    assert updated_rule.json()["data"]["rule_name"] == "Fixed margin twenty updated"

    recommendations = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/recommendations?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert recommendations.status_code == 200, recommendations.text
    assert recommendations.json()["data"]["items"][0]["id"] == recommendation["id"]

    rules_response = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/rules?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert rules_response.status_code == 200, rules_response.text
    assert [row["rule_key"] for row in rules_response.json()["data"]["items"]] == ["fixed_margin_20", "minimum_floor_15"]

    session.expire_all()
    events = session.exec(
        select(MarketplacePricingEvent)
        .where(MarketplacePricingEvent.organization_id == organization_id)
        .order_by(MarketplacePricingEvent.created_at.asc(), MarketplacePricingEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "marketplace_pricing_rule_created",
        "marketplace_pricing_rule_created",
        "marketplace_price_recommendation_generated",
        "marketplace_price_recommendation_reviewed",
        "marketplace_pricing_rule_updated",
    ]


def test_offer_ingestion_duplicate_detection_status_update_and_summary(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-pricing-offer-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-pricing-offer-org")
    account_id = _connect_marketplace(client, owner, organization_id, "offers")
    inventory_item_id = _inventory_copy_id(client, owner)
    listing_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id)

    first = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "marketplace_listing_draft_id": listing_id,
            "marketplace_offer_identifier": "offer-1001",
            "offer_status": "received",
            "offer_amount": "12.50",
            "offer_currency": "USD",
            "buyer_identifier": "buyer-1001",
        },
    )
    duplicate = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest",
        headers=auth_headers(owner),
        json={
            "marketplace_account_id": account_id,
            "marketplace_listing_draft_id": listing_id,
            "marketplace_offer_identifier": "offer-1001",
            "offer_status": "received",
            "offer_amount": "12.50",
            "offer_currency": "USD",
            "buyer_identifier": "buyer-1001",
        },
    )
    assert first.status_code == 201, first.text
    assert duplicate.status_code == 201, duplicate.text
    assert first.json()["data"]["id"] == duplicate.json()["data"]["id"]

    updated = client.patch(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/{first.json()['data']['id']}/status",
        headers=auth_headers(owner),
        json={"offer_status": "accepted_internal"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["offer_status"] == "accepted_internal"

    offers = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers?limit=20&offset=0",
        headers=auth_headers(owner),
    )
    assert offers.status_code == 200, offers.text
    payload = offers.json()["data"]
    assert payload["summary"]["total_offers"] == 1
    assert payload["summary"]["accepted_internal_offers"] == 1
    assert payload["items"][0]["offer_status"] == "accepted_internal"

    session.expire_all()
    db_offers = session.exec(select(MarketplaceOffer).where(MarketplaceOffer.organization_id == organization_id)).all()
    assert len(db_offers) == 1
    events = session.exec(
        select(MarketplacePricingEvent)
        .where(MarketplacePricingEvent.organization_id == organization_id)
        .order_by(MarketplacePricingEvent.created_at.asc(), MarketplacePricingEvent.id.asc())
    ).all()
    assert [row.event_type for row in events] == [
        "marketplace_offer_ingested",
        "marketplace_duplicate_offer_detected",
        "marketplace_offer_status_updated",
    ]


def test_pricing_org_isolation_denied_and_audited(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-pricing-isolation-owner@example.com")
    outsider = register_and_login(client, "marketplace-pricing-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-pricing-isolation-org")
    _create_organization(client, outsider, slug="marketplace-pricing-isolation-outsider-org")
    account_id = _connect_marketplace(client, owner, organization_id, "isolation")
    inventory_item_id = _inventory_copy_id(client, owner)
    listing_id = _create_listing(client, owner, organization_id, account_id=account_id, inventory_item_id=inventory_item_id)

    created = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/rules",
        headers=auth_headers(owner),
        json={
            "rule_key": "isolation_rule",
            "rule_name": "Isolation rule",
            "rule_status": "active",
            "rule_payload_json": {"rule_type": "minimum_floor", "floor_price": "8.00"},
        },
    )
    assert created.status_code == 201, created.text

    denied = client.get(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/recommendations",
        headers=auth_headers(outsider),
    )
    assert denied.status_code == 403, denied.text

    denied_offer = client.post(
        f"/api/v1/organizations/{organization_id}/marketplace-pricing/offers/ingest",
        headers=auth_headers(outsider),
        json={
            "marketplace_account_id": account_id,
            "marketplace_listing_draft_id": listing_id,
            "marketplace_offer_identifier": "outsider-offer",
            "offer_status": "received",
            "offer_amount": "9.99",
            "offer_currency": "USD",
        },
    )
    assert denied_offer.status_code == 403, denied_offer.text

    session.expire_all()
    events = session.exec(
        select(MarketplacePricingEvent)
        .where(MarketplacePricingEvent.organization_id == organization_id)
        .where(MarketplacePricingEvent.event_type == "unauthorized_marketplace_pricing_access_attempt")
        .order_by(MarketplacePricingEvent.created_at.asc(), MarketplacePricingEvent.id.asc())
    ).all()
    assert len(events) >= 2
