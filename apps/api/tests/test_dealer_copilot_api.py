from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketObservation, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _seed_recommendation_inputs(session: Session, *, owner_user_id: int) -> None:
    now = datetime.now(timezone.utc)
    seeds = [
        ("API Buy", 0.82, "BULLISH_TREND_FORECAST", 35.0, 2.0),
        ("API Sell", 0.64, "BEARISH_TREND_FORECAST", -8.0, 8.0),
        ("API Hold", 0.45, "NEUTRAL_TREND_FORECAST", 1.0, 4.0),
    ]
    for title, signal_confidence, forecast_type, forecast_value, risk_score in seeds:
        listing = create_listing(
            session,
            owner_id=owner_user_id,
            payload=MarketplaceListingCreate(
                listing_title=title,
                listing_description=f"{title} seed",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="20.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=20.0, confidence_score=signal_confidence, observed_at=now, created_at=now))
        session.add(MarketForecast(owner_user_id=owner_user_id, forecast_type=forecast_type, asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=forecast_value, confidence_score=max(signal_confidence, 0.6), created_at=now))
        session.add(MarketRiskAssessment(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=risk_score, confidence_score=0.72, created_at=now))
    session.add(MarketObservation(owner_user_id=owner_user_id, observation_uuid="dealer-api-observation", observation_type="market", title="Demand shift", description="Observation for watchlist", confidence_score=0.71, created_by_agent="market_observation_agent", created_at=now))
    session.commit()


def test_dealer_copilot_api_routes_are_owner_scoped_and_support_reviews(client: TestClient) -> None:
    owner_email = "dealer-api-owner@example.com"
    outsider_email = "dealer-api-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_recommendation_inputs(session, owner_user_id=int(owner.id or 0))

    run = client.post("/api/v1/dealer-copilot/run", headers=auth_headers(owner_token))
    assert run.status_code == 201, run.text
    assert run.json()["data"]["recommendations"]

    recommendations = client.get("/api/v1/dealer-copilot/recommendations?limit=100&offset=0", headers=auth_headers(owner_token))
    opportunities = client.get("/api/v1/dealer-copilot/opportunities?limit=100&offset=0", headers=auth_headers(owner_token))
    top_buys = client.get("/api/v1/dealer-copilot/top-buys?limit=10", headers=auth_headers(owner_token))
    top_sells = client.get("/api/v1/dealer-copilot/top-sells?limit=10", headers=auth_headers(owner_token))
    top_holds = client.get("/api/v1/dealer-copilot/top-holds?limit=10", headers=auth_headers(owner_token))
    top_grades = client.get("/api/v1/dealer-copilot/top-grades?limit=10", headers=auth_headers(owner_token))
    top_watch = client.get("/api/v1/dealer-copilot/top-watchlist?limit=10", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/dealer-copilot/dashboard", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/dealer-copilot/executions?limit=100&offset=0", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/dealer-copilot/recommendations?limit=100&offset=0", headers=auth_headers(outsider_token))

    assert recommendations.status_code == 200, recommendations.text
    assert opportunities.status_code == 200, opportunities.text
    assert top_buys.status_code == 200, top_buys.text
    assert top_sells.status_code == 200, top_sells.text
    assert top_holds.status_code == 200, top_holds.text
    assert top_grades.status_code == 200, top_grades.text
    assert top_watch.status_code == 200, top_watch.text
    assert dashboard.status_code == 200, dashboard.text
    assert executions.status_code == 200, executions.text
    assert outsider.json()["data"]["items"] == []

    items = recommendations.json()["data"]["items"]
    assert items
    recommendation_id = items[0]["id"]
    detail = client.get(f"/api/v1/dealer-copilot/recommendations/{recommendation_id}", headers=auth_headers(owner_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["evidence"]

    reviewed = client.post(f"/api/v1/dealer-copilot/recommendations/{recommendation_id}/reviewed", headers=auth_headers(owner_token))
    accepted = client.post(f"/api/v1/dealer-copilot/recommendations/{recommendation_id}/accepted", headers=auth_headers(owner_token))
    dismissed = client.post(f"/api/v1/dealer-copilot/recommendations/{recommendation_id}/dismissed", headers=auth_headers(owner_token))
    assert reviewed.status_code == 200, reviewed.text
    assert accepted.status_code == 200, accepted.text
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["data"]["recommendation"]["recommendation_status"] == "DISMISSED"

    outsider_detail = client.get(f"/api/v1/dealer-copilot/recommendations/{recommendation_id}", headers=auth_headers(outsider_token))
    assert outsider_detail.status_code == 404, outsider_detail.text
