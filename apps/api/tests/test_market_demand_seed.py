from __future__ import annotations

from sqlmodel import Session

from app.db.session import get_engine
from app.services.market_demand_baseline_data import MARKET_DEMAND_BASELINES
from app.services.market_demand_seed import market_demand_profile_count, seed_market_demand_baselines


def test_market_demand_seed_loads_baselines() -> None:
    with Session(get_engine()) as session:
        created = seed_market_demand_baselines(session)
        count = market_demand_profile_count(session)
    assert created >= 0
    assert count >= len(MARKET_DEMAND_BASELINES)
