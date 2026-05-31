from __future__ import annotations

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.collector_market_intelligence import MarketDemandProfile
from app.services.market_demand_engine import collector_demand_components, market_demand_score, refresh_market_demand
from app.services.market_demand_seed import seed_market_demand_baselines


def test_market_demand_engine_creates_scores() -> None:
    with Session(get_engine()) as session:
        seed_market_demand_baselines(session)
        result = refresh_market_demand(session)
        batman = session.exec(
            select(MarketDemandProfile).where(
                MarketDemandProfile.entity_type == "FRANCHISE",
                MarketDemandProfile.entity_name == "Batman",
            )
        ).one()
        components = collector_demand_components(session, entity_type="FRANCHISE", entity_name="Batman")
        score = market_demand_score(session, entity_type="FRANCHISE", entity_name="Batman")
    assert result["seeded_baselines"] >= 0
    assert batman.demand_score >= 90.0
    assert score >= 90.0
    assert components["collector_demand_score"] > 0.0
