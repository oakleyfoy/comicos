from __future__ import annotations

from sqlmodel import Session, select

from app.models.character_intelligence import CharacterPopularityScore, CharacterProfile
from app.models.collector_market_intelligence import (
    CollectorDemandScore,
    HistoricalPerformanceSignal,
    MarketDemandProfile,
    MarketDemandSignal,
    SOURCE_VERSION,
)
from app.models.creator_intelligence import CreatorPopularityScore, CreatorProfile
from app.models.franchise_intelligence import FranchisePopularityScore, FranchiseProfile
from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.popularity_engine import character_score, creator_score, franchise_score


def _upsert_profile(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    entity_name: str,
    demand_score: float,
    confidence: float,
) -> MarketDemandProfile:
    row = session.exec(
        select(MarketDemandProfile).where(
            MarketDemandProfile.entity_type == entity_type,
            MarketDemandProfile.entity_name == entity_name,
        )
    ).first()
    if row:
        row.entity_id = entity_id
        row.demand_score = round(demand_score, 2)
        row.confidence_score = round(confidence, 3)
        row.source_version = SOURCE_VERSION
        session.add(row)
        return row
    profile = MarketDemandProfile(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        demand_score=round(demand_score, 2),
        confidence_score=round(confidence, 3),
        source_version=SOURCE_VERSION,
    )
    session.add(profile)
    session.flush()
    return profile


def _latest_collector_score(session: Session, *, entity_type: str, entity_name: str) -> CollectorDemandScore | None:
    return session.exec(
        select(CollectorDemandScore)
        .where(CollectorDemandScore.entity_type == entity_type, CollectorDemandScore.entity_name == entity_name)
        .order_by(CollectorDemandScore.id.desc())
    ).first()


def market_demand_score(session: Session, *, entity_type: str, entity_name: str) -> float:
    row = session.exec(
        select(MarketDemandProfile).where(
            MarketDemandProfile.entity_type == entity_type,
            MarketDemandProfile.entity_name == entity_name,
        )
    ).first()
    return float(row.demand_score) if row else 50.0


def collector_demand_components(session: Session, *, entity_type: str, entity_name: str) -> dict[str, float]:
    row = _latest_collector_score(session, entity_type=entity_type, entity_name=entity_name)
    if row:
        return {
            "collector_demand_score": float(row.collector_score),
            "liquidity_score": float(row.liquidity_score),
            "long_term_score": float(row.long_term_score),
            "volatility_score": float(row.volatility_score),
        }
    demand = market_demand_score(session, entity_type=entity_type, entity_name=entity_name)
    return {
        "collector_demand_score": round(demand - 2.0, 2),
        "liquidity_score": round(demand - 4.0, 2),
        "long_term_score": round(demand - 1.0, 2),
        "volatility_score": 45.0,
    }


def _key_issue_boost_for_name(session: Session, *, name: str) -> float:
    needle = name.lower()
    rows = session.exec(
        select(KeyIssueProfile, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
    ).all()
    boosts: list[float] = []
    for profile, issue, series in rows:
        hay = f"{series.series_name} {issue.title} {issue.issue_number}".lower()
        if needle in hay or hay in needle:
            boosts.append(float(profile.importance_score))
    if not boosts:
        return 0.0
    return round(sum(boosts) / len(boosts) * 0.15, 2)


def refresh_market_demand(session: Session) -> dict[str, int]:
    seeded = seed_market_demand_baselines(session)
    profiles_updated = 0
    signals_added = 0
    collector_rows = 0

    for profile in session.exec(select(CharacterProfile).where(CharacterProfile.status == "ACTIVE")).all():
        pop = character_score(session, character_id=int(profile.id or 0))
        latest = session.exec(
            select(CharacterPopularityScore)
            .where(CharacterPopularityScore.character_id == profile.id)
            .order_by(CharacterPopularityScore.id.desc())
        ).first()
        demand = pop or (float(latest.demand_score) if latest else 65.0)
        demand += _key_issue_boost_for_name(session, name=profile.character_name)
        conf = float(latest.confidence_score) if latest else 0.75
        entity = _upsert_profile(
            session,
            entity_type="CHARACTER",
            entity_id=int(profile.id or 0),
            entity_name=profile.character_name,
            demand_score=min(demand, 100.0),
            confidence=conf,
        )
        session.add(
            MarketDemandSignal(
                profile_id=int(entity.id or 0),
                signal_type="P51_01_CHARACTER",
                signal_strength=round(demand, 2),
                signal_payload_json={"character_id": int(profile.id or 0)},
            )
        )
        profiles_updated += 1
        signals_added += 1

    for profile in session.exec(select(FranchiseProfile).where(FranchiseProfile.status == "ACTIVE")).all():
        pop = franchise_score(session, franchise_id=int(profile.id or 0))
        latest = session.exec(
            select(FranchisePopularityScore)
            .where(FranchisePopularityScore.franchise_id == profile.id)
            .order_by(FranchisePopularityScore.id.desc())
        ).first()
        demand = pop or (float(latest.demand_score) if latest else 68.0)
        demand += _key_issue_boost_for_name(session, name=profile.franchise_name)
        conf = float(latest.confidence_score) if latest else 0.75
        entity = _upsert_profile(
            session,
            entity_type="FRANCHISE",
            entity_id=int(profile.id or 0),
            entity_name=profile.franchise_name,
            demand_score=min(demand, 100.0),
            confidence=conf,
        )
        session.add(
            MarketDemandSignal(
                profile_id=int(entity.id or 0),
                signal_type="P51_01_FRANCHISE",
                signal_strength=round(demand, 2),
                signal_payload_json={"franchise_id": int(profile.id or 0)},
            )
        )
        profiles_updated += 1
        signals_added += 1

    for profile in session.exec(select(CreatorProfile).where(CreatorProfile.status == "ACTIVE")).all():
        pop = creator_score(session, creator_id=int(profile.id or 0))
        latest = session.exec(
            select(CreatorPopularityScore)
            .where(CreatorPopularityScore.creator_id == profile.id)
            .order_by(CreatorPopularityScore.id.desc())
        ).first()
        demand = pop or (float(latest.demand_score) if latest else 62.0)
        conf = float(latest.confidence_score) if latest else 0.72
        entity = _upsert_profile(
            session,
            entity_type="CREATOR",
            entity_id=int(profile.id or 0),
            entity_name=profile.creator_name,
            demand_score=min(demand, 100.0),
            confidence=conf,
        )
        session.add(
            MarketDemandSignal(
                profile_id=int(entity.id or 0),
                signal_type="P51_01_CREATOR",
                signal_strength=round(demand, 2),
                signal_payload_json={"creator_id": int(profile.id or 0)},
            )
        )
        profiles_updated += 1
        signals_added += 1

    for profile in session.exec(select(MarketDemandProfile)).all():
        components = collector_demand_components(
            session, entity_type=profile.entity_type, entity_name=profile.entity_name
        )
        if _latest_collector_score(session, entity_type=profile.entity_type, entity_name=profile.entity_name):
            continue
        session.add(
            CollectorDemandScore(
                entity_type=profile.entity_type,
                entity_name=profile.entity_name,
                collector_score=components["collector_demand_score"],
                liquidity_score=components["liquidity_score"],
                long_term_score=components["long_term_score"],
                volatility_score=components["volatility_score"],
            )
        )
        session.add(
            HistoricalPerformanceSignal(
                entity_type=profile.entity_type,
                entity_name=profile.entity_name,
                performance_type="MARKET_REFRESH",
                performance_score=components["long_term_score"],
                confidence_score=float(profile.confidence_score),
            )
        )
        collector_rows += 1

    session.commit()
    return {
        "seeded_baselines": seeded,
        "profiles_updated": profiles_updated,
        "signals_added": signals_added,
        "collector_scores_added": collector_rows,
    }
