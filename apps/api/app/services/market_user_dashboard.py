from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.collector_market_intelligence import (
    CollectorDemandScore,
    HistoricalPerformanceSignal,
    MarketDemandProfile,
    MarketDemandSignal,
)
from app.models.user_preference_intelligence import (
    UserPreferenceProfile,
    UserPreferenceScore,
    UserPreferenceSignal,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.user_preference_intelligence import UserPreferenceProfile, UserPreferenceScore, UserPreferenceSignal
from app.schemas.market_user_intelligence import (
    MarketDemandBucketRead,
    MarketDemandEntityRead,
    MarketUserDashboardRead,
    PreferenceSignalRead,
    UpcomingMarketUserFitRead,
    UserPreferenceRead,
)
from app.services.market_user_intelligence import score_release_market_user_fit
from app.services.user_preference_engine import safe_default_preferences


def _top_market_demand(session: Session, *, limit: int) -> list[MarketDemandEntityRead]:
    rows = session.exec(
        select(MarketDemandProfile).order_by(MarketDemandProfile.demand_score.desc(), MarketDemandProfile.id.desc())
    ).all()
    out: list[MarketDemandEntityRead] = []
    for row in rows[:limit]:
        out.append(
            MarketDemandEntityRead(
                entity_type=row.entity_type,
                entity_name=row.entity_name,
                demand_score=float(row.demand_score),
                confidence_score=float(row.confidence_score),
            )
        )
    return out


def _demand_distribution(session: Session) -> list[MarketDemandBucketRead]:
    rows = session.exec(select(MarketDemandProfile)).all()
    buckets = {"90+": 0, "75-89": 0, "60-74": 0, "<60": 0}
    for row in rows:
        score = float(row.demand_score)
        if score >= 90:
            buckets["90+"] += 1
        elif score >= 75:
            buckets["75-89"] += 1
        elif score >= 60:
            buckets["60-74"] += 1
        else:
            buckets["<60"] += 1
    return [MarketDemandBucketRead(bucket=label, count=count) for label, count in buckets.items()]


def _top_user_preferences(session: Session, *, owner_user_id: int, limit: int) -> list[UserPreferenceRead]:
    profiles = session.exec(
        select(UserPreferenceProfile)
        .where(UserPreferenceProfile.owner_user_id == owner_user_id, UserPreferenceProfile.status == "ACTIVE")
        .order_by(UserPreferenceProfile.id.desc())
    ).all()
    ranked: list[UserPreferenceRead] = []
    for profile in profiles:
        score_row = session.exec(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.preference_profile_id == profile.id)
            .order_by(UserPreferenceScore.id.desc())
        ).first()
        ranked.append(
            UserPreferenceRead(
                id=int(profile.id or 0),
                preference_type=profile.preference_type,
                preference_key=profile.preference_key,
                preference_label=profile.preference_label,
                status=profile.status,
                preference_score=float(score_row.preference_score) if score_row else 50.0,
                confidence_score=float(score_row.confidence_score) if score_row else 0.25,
            )
        )
    ranked.sort(key=lambda row: row.preference_score, reverse=True)
    return ranked[:limit]


def _preference_signals(session: Session, *, owner_user_id: int, limit: int) -> list[PreferenceSignalRead]:
    rows = session.exec(
        select(UserPreferenceSignal)
        .where(UserPreferenceSignal.owner_user_id == owner_user_id)
        .order_by(UserPreferenceSignal.id.desc())
    ).all()
    out: list[PreferenceSignalRead] = []
    for row in rows[:limit]:
        profile = session.get(UserPreferenceProfile, row.preference_profile_id)
        out.append(
            PreferenceSignalRead(
                signal_type=row.signal_type,
                signal_strength=float(row.signal_strength),
                source_type=row.source_type,
                preference_label=profile.preference_label if profile else "",
            )
        )
    return out


def _upcoming_high_fit(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
) -> list[UpcomingMarketUserFitRead]:
    horizon = date.today() + timedelta(days=90)
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_status.in_(["SCHEDULED", "ANNOUNCED", "PREORDER"]))
    ).all()
    scored: list[UpcomingMarketUserFitRead] = []
    for issue, series in rows:
        if issue.release_date and issue.release_date > horizon:
            continue
        fit = score_release_market_user_fit(session, owner_user_id=owner_user_id, issue=issue, series=series)
        scored.append(
            UpcomingMarketUserFitRead(
                release_issue_id=int(issue.id or 0),
                series_name=series.series_name,
                issue_number=issue.issue_number,
                title=issue.title,
                release_date=issue.release_date,
                combined_market_user_score=float(fit["combined_market_user_score"]),
            )
        )
    scored.sort(key=lambda row: row.combined_market_user_score, reverse=True)
    return scored[:limit]


def build_market_user_dashboard(session: Session, *, owner_user_id: int, limit: int = 25) -> MarketUserDashboardRead:
    top_market = _top_market_demand(session, limit=limit)
    top_prefs = _top_user_preferences(session, owner_user_id=owner_user_id, limit=limit)
    if not top_prefs:
        defaults = safe_default_preferences()
        top_prefs = [
            UserPreferenceRead(
                id=0,
                preference_type=str(row["preference_type"]),
                preference_key=str(row["preference_key"]),
                preference_label=str(row["preference_label"]),
                status=str(row["status"]),
                preference_score=float(row["preference_score"]),
                confidence_score=float(row["confidence_score"]),
            )
            for row in defaults
        ]
    return MarketUserDashboardRead(
        top_market_demand=top_market,
        top_user_preferences=top_prefs,
        preference_signals=_preference_signals(session, owner_user_id=owner_user_id, limit=limit),
        market_demand_distribution=_demand_distribution(session),
        upcoming_high_fit=_upcoming_high_fit(session, owner_user_id=owner_user_id, limit=limit),
        total_market_profiles=len(session.exec(select(MarketDemandProfile)).all()),
        total_active_preferences=len(
            session.exec(
                select(UserPreferenceProfile).where(
                    UserPreferenceProfile.owner_user_id == owner_user_id,
                    UserPreferenceProfile.status == "ACTIVE",
                )
            ).all()
        ),
    )


def list_market_demand_entities(session: Session, *, limit: int, offset: int) -> tuple[list[MarketDemandEntityRead], int]:
    rows = session.exec(
        select(MarketDemandProfile).order_by(MarketDemandProfile.demand_score.desc(), MarketDemandProfile.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    items = [
        MarketDemandEntityRead(
            entity_type=row.entity_type,
            entity_name=row.entity_name,
            demand_score=float(row.demand_score),
            confidence_score=float(row.confidence_score),
        )
        for row in page
    ]
    return items, total
