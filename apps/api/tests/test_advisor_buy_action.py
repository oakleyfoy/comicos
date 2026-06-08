"""Advisor buy action URL resolution (P90-07)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.models import User
from app.services.advisor_buy_action_service import enrich_buy_action_dict, resolve_buy_action_target
from test_inventory import register_and_login


def test_advisor_buy_action_with_verified_listing(client, session: Session) -> None:
    register_and_login(client, "buy-action-verified@example.com")
    user = session.exec(select(User).where(User.email == "buy-action-verified@example.com")).one()
    uid = int(user.id)
    opp = MarketplaceAcquisitionOpportunity(
        owner_user_id=uid,
        marketplace="EBAY",
        external_listing_id="999888777",
        listing_url="https://www.ebay.com/itm/999888777",
        title="Test Book #1",
        status="ACTIVE",
        recommendation="STRONG_BUY",
        opportunity_score=90.0,
        asking_price=5.0,
        estimated_fmv=10.0,
        discount_to_fmv=50.0,
    )
    session.add(opp)
    session.flush()
    assert opp.id
    now = datetime.now(timezone.utc)
    session.add(
        P88MarketplaceListing(
            owner_user_id=uid,
            opportunity_id=int(opp.id),
            marketplace="EBAY",
            item_id="999888777",
            title="Test Book #1",
            listing_url="https://www.ebay.com/itm/999888777",
            price=5.0,
            shipping_cost=0.0,
            is_active=True,
            health_status="ACTIVE",
            last_verified_at=now,
            marketplace_name="eBay",
        )
    )
    session.commit()

    target = resolve_buy_action_target(
        session,
        owner_user_id=uid,
        entity_type="marketplace_acquisition",
        entity_id=int(opp.id),
        comic_title="Test Book #1",
        fallback_route="/marketplace-opportunity/1",
    )
    assert target["has_verified_listing"] is True
    assert target["action_url_type"] == "MARKETPLACE_LISTING"
    assert "ebay.com/itm/999888777" in target["action_url"]

    item: dict = {
        "category": "BUY",
        "entity_type": "marketplace_acquisition",
        "entity_id": int(opp.id),
        "comic": "Test Book #1",
        "reason": "50% below FMV",
    }
    enrich_buy_action_dict(session, owner_user_id=uid, item=item)
    assert item["action_url_type"] == "MARKETPLACE_LISTING"


def test_advisor_buy_action_without_listing_uses_opportunity_detail(client, session: Session) -> None:
    register_and_login(client, "buy-action-unverified@example.com")
    user = session.exec(select(User).where(User.email == "buy-action-unverified@example.com")).one()
    uid = int(user.id)
    opp = MarketplaceAcquisitionOpportunity(
        owner_user_id=uid,
        marketplace="EBAY",
        external_listing_id="SIM-EBAY-1",
        listing_url="https://www.ebay.com/itm/sim-1",
        title="Sim Book",
        status="ACTIVE",
        recommendation="GOOD_BUY",
        opportunity_score=75.0,
        asking_price=5.0,
        estimated_fmv=10.0,
        discount_to_fmv=50.0,
    )
    session.add(opp)
    session.commit()
    assert opp.id

    target = resolve_buy_action_target(
        session,
        owner_user_id=uid,
        entity_type="marketplace_acquisition",
        entity_id=int(opp.id),
        comic_title="Sim Book",
        fallback_route="/x",
    )
    assert target["has_verified_listing"] is False
    assert target["action_url_type"] == "OPPORTUNITY_DETAIL"
    assert f"/marketplace-opportunity/{opp.id}" in target["action_url"]
