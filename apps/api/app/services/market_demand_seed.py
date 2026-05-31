from __future__ import annotations

from sqlmodel import Session, select

from app.models.collector_market_intelligence import (
    CollectorDemandScore,
    HistoricalPerformanceSignal,
    MarketDemandProfile,
    MarketDemandSignal,
    SOURCE_VERSION,
)
from app.services.market_demand_baseline_data import MARKET_DEMAND_BASELINES


def _profile_for_entity(session: Session, *, entity_type: str, entity_name: str) -> MarketDemandProfile | None:
    return session.exec(
        select(MarketDemandProfile).where(
            MarketDemandProfile.entity_type == entity_type,
            MarketDemandProfile.entity_name == entity_name,
        )
    ).first()


def seed_market_demand_baselines(session: Session) -> int:
    """Insert deterministic baseline market demand rows when missing."""
    created = 0
    for entity_type, entity_name, demand, liquidity, long_term, volatility in MARKET_DEMAND_BASELINES:
        existing = _profile_for_entity(session, entity_type=entity_type, entity_name=entity_name)
        if existing:
            continue
        profile = MarketDemandProfile(
            entity_type=entity_type,
            entity_id=0,
            entity_name=entity_name,
            demand_score=round(demand, 2),
            confidence_score=0.85,
            source_version=SOURCE_VERSION,
        )
        session.add(profile)
        session.flush()
        session.add(
            MarketDemandSignal(
                profile_id=int(profile.id or 0),
                signal_type="BASELINE_SEED",
                signal_strength=round(demand, 2),
                signal_payload_json={"source": "market_demand_seed", "entity_type": entity_type},
            )
        )
        session.add(
            HistoricalPerformanceSignal(
                entity_type=entity_type,
                entity_name=entity_name,
                performance_type="BASELINE_HOLD",
                performance_score=round(long_term, 2),
                confidence_score=0.8,
            )
        )
        session.add(
            CollectorDemandScore(
                entity_type=entity_type,
                entity_name=entity_name,
                collector_score=round(demand - 2.0, 2),
                liquidity_score=round(liquidity, 2),
                long_term_score=round(long_term, 2),
                volatility_score=round(volatility, 2),
            )
        )
        created += 1
    session.commit()
    return created


def market_demand_profile_count(session: Session) -> int:
    return len(session.exec(select(MarketDemandProfile)).all())
