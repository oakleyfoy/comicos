from __future__ import annotations

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.market_user_intelligence import combined_market_user_score
from app.services.user_preference_engine import create_manual_preference


def test_combined_market_user_score_aggregation() -> None:
    with Session(get_engine()) as session:
        seed_market_demand_baselines(session)
        owner = session.exec(select(User).order_by(User.id.asc())).first()
        assert owner and owner.id
        create_manual_preference(
            session,
            owner_user_id=int(owner.id),
            preference_type="FRANCHISE",
            preference_label="Batman",
            preference_score=95.0,
        )
        score = combined_market_user_score(
            session,
            owner_user_id=int(owner.id),
            entity_type="FRANCHISE",
            entity_name="Batman",
        )
    assert score >= 80.0
