from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p89_market_price_snapshot import P89MarketPriceSnapshot
from app.services.market_trend_service import compute_trend_direction
from app.services.p89_market_pricing_service import (
    generate_market_price_snapshots,
    gather_market_bundles,
)
from test_inventory import auth_headers, create_order, register_and_login


def test_trend_direction() -> None:
    assert compute_trend_direction(current_average=110, prior_average=100) == "UP"
    assert compute_trend_direction(current_average=98, prior_average=100) == "FLAT"


def test_snapshot_generation_from_stored_listings(client: TestClient, session: Session) -> None:
    email = "p89-mkt-price@example.com"
    token = register_and_login(client, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    from app.models import User

    user = session.exec(select(User).where(User.email == email)).one()
    opp = MarketplaceAcquisitionOpportunity(
        owner_user_id=int(user.id),
        marketplace="EBAY",
        external_listing_id="ext-1",
        title="X-Men #1",
        publisher="Marvel",
        series="X-Men",
        issue="1",
        variant="Cover A",
        asking_price=35.0,
        estimated_fmv=40.0,
        recommendation="GOOD_BUY",
    )
    session.add(opp)
    session.flush()
    session.add(
        P88MarketplaceListing(
            owner_user_id=int(user.id),
            opportunity_id=int(opp.id or 0),
            marketplace="EBAY",
            item_id="item-1",
            title="X-Men #1",
            price=32.0,
            shipping_cost=4.0,
            is_active=True,
            health_status="ACTIVE",
            listing_confidence="HIGH",
        )
    )
    session.add(
        P88MarketplaceListing(
            owner_user_id=int(user.id),
            opportunity_id=int(opp.id or 0),
            marketplace="EBAY",
            item_id="item-2",
            title="X-Men #1 higher",
            price=42.0,
            shipping_cost=0.0,
            is_active=True,
            health_status="ACTIVE",
            listing_confidence="MEDIUM",
        )
    )
    session.commit()

    bundles = gather_market_bundles(session, owner_user_id=int(user.id))
    assert any(b.active_prices for b in bundles.values())

    summary = generate_market_price_snapshots(session, owner_user_id=int(user.id), snapshot_date=date.today(), dry_run=False)
    session.commit()
    assert summary["snapshots_created"] >= 1

    rows = list(session.exec(select(P89MarketPriceSnapshot).where(P89MarketPriceSnapshot.owner_user_id == int(user.id))).all())
    assert rows
    row = rows[0]
    assert row.quick_sale_price > 0
    assert row.market_price > 0
    assert row.premium_price >= row.market_price
    assert row.pricing_confidence in {"HIGH", "MEDIUM", "LOW"}


def test_api_dashboard_and_portfolio(client: TestClient, session: Session) -> None:
    email = "p89-mkt-api@example.com"
    token = register_and_login(client, email)
    gen = client.post("/api/v1/market-pricing/generate", headers=auth_headers(token))
    assert gen.status_code == 200
    dash = client.get("/api/v1/market-pricing/dashboard", headers=auth_headers(token))
    assert dash.status_code == 200
    totals = client.get("/api/v1/market-pricing/portfolio-totals", headers=auth_headers(token))
    assert totals.status_code == 200
    data = totals.json()["data"]
    assert "market_value_total" in data


def test_runner_dry_run(client: TestClient, session: Session) -> None:
    email = "p89-mkt-dry@example.com"
    register_and_login(client, email)
    from app.models import User

    user = session.exec(select(User).where(User.email == email)).one()
    before = len(list(session.exec(select(P89MarketPriceSnapshot)).all()))
    summary = generate_market_price_snapshots(session, owner_user_id=int(user.id), dry_run=True)
    after = len(list(session.exec(select(P89MarketPriceSnapshot)).all()))
    assert before == after
    assert "high_confidence" in summary
