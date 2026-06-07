"""Fast P85 collector home built from cached operational snapshots."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.grade_before_sell import GradeBeforeSellRecommendation
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot
from app.models.p77_collector_profile import P77CollectorBudget
from app.models.p79_storage_analytics import P79StorageAnalyticsSnapshot
from app.models.p81_discovery import P81DiscoveryAlert, P81FuturePullListItem
from app.models.p82_p84_collector_expansion import (
    CollectionRiskSnapshot,
    CollectionValuationSnapshot,
    MarketplaceAcquisitionOpportunity,
)
from app.schemas.p85_production_hardening import (
    P85CollectorHomeRead,
    P85CollectorHomeSectionRead,
)

logger = logging.getLogger(__name__)

_HOME_LIMIT = 10
_SECTION_MAX_SECONDS = 0.5
_INDICATOR_STALE_DAYS = 14

IndicatorStatus = str  # HAS_ITEMS | EMPTY | STALE | UNKNOWN | ERROR


@dataclass(frozen=True)
class _SectionIndicator:
    count: int | None
    has_items: bool | None
    freshness_label: str | None
    indicator_status: IndicatorStatus


def _indicator_unknown() -> _SectionIndicator:
    return _SectionIndicator(None, None, None, "UNKNOWN")


def _indicator_error() -> _SectionIndicator:
    return _SectionIndicator(None, None, None, "ERROR")


def _freshness_label(updated_at: datetime | None) -> str | None:
    if updated_at is None:
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if updated_at.date() == datetime.now(timezone.utc).date():
        return "Updated today"
    return "Updated recently"


def _is_stale(updated_at: datetime | None) -> bool:
    if updated_at is None:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < datetime.now(timezone.utc) - timedelta(days=_INDICATOR_STALE_DAYS)


def _indicator_from_count(count: int, *, updated_at: datetime | None = None) -> _SectionIndicator:
    fresh = _freshness_label(updated_at)
    stale = _is_stale(updated_at)
    if stale and count > 0:
        return _SectionIndicator(count, True, fresh, "STALE")
    if count > 0:
        return _SectionIndicator(count, True, fresh, "HAS_ITEMS")
    return _SectionIndicator(0, False, fresh, "EMPTY")


def _attach_indicator(section: P85CollectorHomeSectionRead, indicator: _SectionIndicator) -> P85CollectorHomeSectionRead:
    return section.model_copy(
        update={
            "count": indicator.count,
            "has_items": indicator.has_items,
            "freshness_label": indicator.freshness_label,
            "indicator_status": indicator.indicator_status,
        }
    )


def _timed_indicator(name: str, build) -> _SectionIndicator:
    started = time.perf_counter()
    try:
        indicator = build()
    except Exception as exc:  # noqa: BLE001
        logger.warning("collector_home indicator=%s status=ERROR error=%s", name, exc)
        return _indicator_error()
    elapsed = time.perf_counter() - started
    if elapsed > _SECTION_MAX_SECONDS:
        logger.warning("collector_home indicator=%s elapsed_ms=%s status=UNKNOWN", name, round(elapsed * 1000, 1))
        return _indicator_unknown()
    return indicator


def _short_error(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return message[:240]


def _section_ok(
    key: str,
    title: str,
    items: list[dict],
    *,
    empty_hint: str,
    indicator: _SectionIndicator | None = None,
) -> P85CollectorHomeSectionRead:
    n = len(items)
    if n > 0:
        ind = _indicator_from_count(n)
    else:
        ind = _SectionIndicator(0, False, None, "EMPTY")
    section = P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=items[:_HOME_LIMIT],
        empty_hint=empty_hint if not items else "",
        count=n,
        status="OK",
        error="",
    )
    return _attach_indicator(section, ind)


def _section_skipped(
    key: str,
    title: str,
    *,
    empty_hint: str,
    reason: str,
    indicator: _SectionIndicator | None = None,
) -> P85CollectorHomeSectionRead:
    ind = indicator or _indicator_unknown()
    section = P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=[],
        empty_hint=empty_hint,
        count=0,
        status="SKIPPED",
        error=reason[:240],
    )
    return _attach_indicator(section, ind)


def _section_error(
    key: str,
    title: str,
    *,
    empty_hint: str,
    exc: BaseException,
) -> P85CollectorHomeSectionRead:
    logger.warning("collector_home section %s failed: %s", key, exc, exc_info=True)
    section = P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=[],
        empty_hint=empty_hint,
        count=0,
        status="ERROR",
        error=_short_error(exc),
    )
    return _attach_indicator(section, _indicator_error())


def _timed_section(
    key: str,
    title: str,
    *,
    empty_hint: str,
    build_items,
) -> P85CollectorHomeSectionRead:
    started = time.perf_counter()
    try:
        items = build_items()
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.warning("collector_home section=%s elapsed_ms=%s status=ERROR", key, elapsed_ms)
        return _section_error(key, title, empty_hint=empty_hint, exc=exc)
    elapsed = time.perf_counter() - started
    elapsed_ms = round(elapsed * 1000, 1)
    if elapsed > _SECTION_MAX_SECONDS:
        logger.warning("collector_home section=%s elapsed_ms=%s status=SKIPPED_SLOW", key, elapsed_ms)
        return _section_skipped(
            key,
            title,
            empty_hint=empty_hint,
            reason=f"Skipped: cached section exceeded {_SECTION_MAX_SECONDS:.1f}s ({elapsed_ms}ms).",
            indicator=_indicator_unknown(),
        )
    logger.info("collector_home section=%s elapsed_ms=%s status=OK", key, elapsed_ms)
    return _section_ok(key, title, items, empty_hint=empty_hint)


def _static_safe_collector_home() -> P85CollectorHomeRead:
    """Emergency-safe home payload: no DB/service fan-out from Collector Home."""
    skipped = "Temporarily skipped on Collector Home; open the dedicated page for full data."
    sections = [
        _section_skipped(
            "buy_alerts",
            "Buy alerts",
            empty_hint="Open Marketplace Opportunities for buy alerts.",
            reason=skipped,
        ),
        _section_skipped(
            "sell_alerts",
            "Sell alerts",
            empty_hint="Open Sell Queue for sell recommendations.",
            reason=skipped,
        ),
        _section_skipped(
            "grade_alerts",
            "Grade alerts",
            empty_hint="Open Sell Queue for grade candidates.",
            reason=skipped,
        ),
        _section_skipped(
            "foc_alerts",
            "FOC alerts",
            empty_hint="Open Future Pull List for FOC reminders.",
            reason=skipped,
        ),
        _section_skipped(
            "storage_issues",
            "Storage issues",
            empty_hint="Open Storage Dashboard for location status.",
            reason=skipped,
        ),
        _section_skipped(
            "marketplace_deals",
            "Marketplace deals",
            empty_hint="Open Marketplace Opportunities for deals.",
            reason=skipped,
        ),
        _section_skipped(
            "future_pull_list",
            "Future pull list",
            empty_hint="Open Future Pull List for recommendations.",
            reason=skipped,
        ),
        _section_skipped(
            "discovery_alerts",
            "Discovery alerts",
            empty_hint="Open Discovery Dashboard for alerts.",
            reason=skipped,
        ),
    ]
    return P85CollectorHomeRead(
        headline="Collector Home is in fast safe mode.",
        todays_actions=[],
        todays_actions_status="SKIPPED",
        todays_actions_error="Open Daily Actions for the full list.",
        sections=sections,
        budget_status={
            "status": "SKIPPED",
            "error": "Open Budget settings for current budget status.",
            "state": None,
            "monthly_budget": None,
            "monthly_spend": None,
        },
        portfolio_movement={
            "status": "SKIPPED",
            "error": "Open Portfolio views for current value and risk.",
            "current_value": None,
            "risk_category": None,
            "risk_score": None,
        },
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _timed_payload(name: str, build):
    started = time.monotonic()
    try:
        payload = build()
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        logger.warning("collector_home payload=%s elapsed_ms=%s status=ERROR error=%s", name, elapsed_ms, exc)
        return None
    elapsed = time.monotonic() - started
    elapsed_ms = round(elapsed * 1000, 1)
    if elapsed > _SECTION_MAX_SECONDS:
        logger.warning("collector_home payload=%s elapsed_ms=%s status=SKIPPED_SLOW", name, elapsed_ms)
        return None
    logger.info("collector_home payload=%s elapsed_ms=%s status=OK", name, elapsed_ms)
    return payload


def _budget_status(session: Session, *, owner_user_id: int) -> dict:
    budget = session.exec(
        select(P77CollectorBudget).where(P77CollectorBudget.owner_user_id == owner_user_id).limit(1)
    ).first()
    if budget is None:
        return {
            "status": "SKIPPED",
            "error": "No collector budget configured.",
            "state": None,
            "monthly_budget": None,
            "monthly_spend": None,
        }
    return {
        "status": "OK",
        "error": "",
        "state": "CONFIGURED" if float(budget.monthly_budget or 0) > 0 else "UNSET",
        "monthly_budget": float(budget.monthly_budget or 0),
        "monthly_spend": None,
        "budget_period": budget.budget_period,
        "updated_at": budget.updated_at.isoformat() if budget.updated_at else "",
    }


def _portfolio_movement(session: Session, *, owner_user_id: int) -> dict:
    valuation = session.exec(
        select(CollectionValuationSnapshot)
        .where(CollectionValuationSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionValuationSnapshot.created_at.desc(), CollectionValuationSnapshot.id.desc())
        .limit(1)
    ).first()
    risk = session.exec(
        select(CollectionRiskSnapshot)
        .where(CollectionRiskSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectionRiskSnapshot.created_at.desc(), CollectionRiskSnapshot.id.desc())
        .limit(1)
    ).first()
    if valuation is None and risk is None:
        return {
            "status": "SKIPPED",
            "error": "No cached valuation snapshot available.",
            "current_value": None,
            "risk_category": None,
            "risk_score": None,
        }
    return {
        "status": "OK",
        "error": "",
        "current_value": float(valuation.current_value) if valuation else None,
        "risk_category": risk.risk_category if risk else None,
        "risk_score": float(risk.risk_score) if risk else None,
        "snapshot_date": (
            valuation.snapshot_date.isoformat()
            if valuation
            else risk.snapshot_date.isoformat()
            if risk
            else ""
        ),
    }


def _foc_alert_items(session: Session, *, owner_user_id: int) -> list[dict]:
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc(), P74FocRecommendationSnapshot.id.desc())
        .limit(1)
    ).first()
    if snap is None:
        return []
    rows = session.exec(
        select(P74FocAlert)
        .where(P74FocAlert.snapshot_id == int(snap.id or 0))
        .order_by(P74FocAlert.priority_score.desc(), P74FocAlert.id.asc())
        .limit(_HOME_LIMIT)
    ).all()
    if rows:
        return [
            {
                "title": row.title,
                "message": row.message,
                "priority": row.priority_score,
                "type": row.alert_type,
            }
            for row in rows
        ]
    return [
        {"title": "FOC this week", "count": snap.foc_this_week},
        {"title": "FOC next week", "count": snap.foc_next_week},
        {"title": "FOC within 30 days", "count": snap.foc_within_30_days},
        {"title": "Missed FOC", "count": snap.foc_missed},
    ]


def _count_marketplace_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    recommendations: tuple[str, ...],
) -> _SectionIndicator:
    base = (
        select(func.count())
        .select_from(MarketplaceAcquisitionOpportunity)
        .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
        .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
        .where(MarketplaceAcquisitionOpportunity.recommendation.in_(recommendations))
    )
    n = int(session.exec(base).one() or 0)
    latest = session.exec(
        select(MarketplaceAcquisitionOpportunity.updated_at)
        .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
        .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
        .order_by(MarketplaceAcquisitionOpportunity.updated_at.desc())
        .limit(1)
    ).first()
    return _indicator_from_count(n, updated_at=latest)


def _count_hold_sell_recommendations(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    n = int(
        session.exec(
            select(func.count())
            .select_from(HoldSellRecommendation)
            .where(HoldSellRecommendation.owner_user_id == owner_user_id)
            .where(HoldSellRecommendation.recommendation == "SELL")
        ).one()
        or 0
    )
    latest = session.exec(
        select(HoldSellRecommendation.created_at)
        .where(HoldSellRecommendation.owner_user_id == owner_user_id)
        .order_by(HoldSellRecommendation.created_at.desc())
        .limit(1)
    ).first()
    return _indicator_from_count(n, updated_at=latest)


def _count_grade_candidates(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    n = int(
        session.exec(
            select(func.count())
            .select_from(GradeBeforeSellRecommendation)
            .where(GradeBeforeSellRecommendation.owner_user_id == owner_user_id)
            .where(GradeBeforeSellRecommendation.recommendation == "GRADE_BEFORE_SELL")
        ).one()
        or 0
    )
    latest = session.exec(
        select(GradeBeforeSellRecommendation.created_at)
        .where(GradeBeforeSellRecommendation.owner_user_id == owner_user_id)
        .order_by(GradeBeforeSellRecommendation.created_at.desc())
        .limit(1)
    ).first()
    return _indicator_from_count(n, updated_at=latest)


def _indicator_foc(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc(), P74FocRecommendationSnapshot.id.desc())
        .limit(1)
    ).first()
    if snap is None:
        return _SectionIndicator(0, False, None, "EMPTY")
    alert_count = int(
        session.exec(
            select(func.count())
            .select_from(P74FocAlert)
            .where(P74FocAlert.snapshot_id == int(snap.id or 0))
        ).one()
        or 0
    )
    if alert_count > 0:
        return _indicator_from_count(alert_count, updated_at=snap.generated_at)
    total = (
        int(snap.foc_this_week or 0)
        + int(snap.foc_next_week or 0)
        + int(snap.foc_within_30_days or 0)
        + int(snap.foc_missed or 0)
    )
    return _indicator_from_count(total, updated_at=snap.generated_at)


def _indicator_storage(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    snap = session.exec(
        select(P79StorageAnalyticsSnapshot)
        .where(P79StorageAnalyticsSnapshot.owner_user_id == owner_user_id)
        .order_by(P79StorageAnalyticsSnapshot.generated_at.desc(), P79StorageAnalyticsSnapshot.id.desc())
        .limit(1)
    ).first()
    if snap is None:
        return _indicator_unknown()
    n = int(snap.unassigned_inventory_count or 0)
    return _indicator_from_count(n, updated_at=snap.generated_at)


def _count_future_pull_list(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    n = int(
        session.exec(
            select(func.count())
            .select_from(P81FuturePullListItem)
            .where(P81FuturePullListItem.owner_user_id == owner_user_id)
        ).one()
        or 0
    )
    latest = session.exec(
        select(P81FuturePullListItem.updated_at)
        .where(P81FuturePullListItem.owner_user_id == owner_user_id)
        .order_by(P81FuturePullListItem.updated_at.desc())
        .limit(1)
    ).first()
    return _indicator_from_count(n, updated_at=latest)


def _count_discovery_alerts(session: Session, *, owner_user_id: int) -> _SectionIndicator:
    n = int(
        session.exec(
            select(func.count())
            .select_from(P81DiscoveryAlert)
            .where(P81DiscoveryAlert.owner_user_id == owner_user_id)
            .where(P81DiscoveryAlert.status == "ACTIVE")
        ).one()
        or 0
    )
    latest = session.exec(
        select(P81DiscoveryAlert.updated_at)
        .where(P81DiscoveryAlert.owner_user_id == owner_user_id)
        .where(P81DiscoveryAlert.status == "ACTIVE")
        .order_by(P81DiscoveryAlert.updated_at.desc())
        .limit(1)
    ).first()
    return _indicator_from_count(n, updated_at=latest)


def build_collector_home(session: Session, *, owner_user_id: int) -> P85CollectorHomeRead:
    started = time.monotonic()
    skipped = "Temporarily skipped on Collector Home; open the dedicated page for full data."
    budget_status = _timed_payload(
        "budget_status",
        lambda: _budget_status(session, owner_user_id=owner_user_id),
    ) or {
        "status": "SKIPPED",
        "error": f"Skipped: budget exceeded {_SECTION_MAX_SECONDS:.1f}s.",
        "state": None,
        "monthly_budget": None,
        "monthly_spend": None,
    }
    portfolio_movement = _timed_payload(
        "portfolio_movement",
        lambda: _portfolio_movement(session, owner_user_id=owner_user_id),
    ) or {
        "status": "SKIPPED",
        "error": f"Skipped: portfolio snapshot exceeded {_SECTION_MAX_SECONDS:.1f}s.",
        "current_value": None,
        "risk_category": None,
        "risk_score": None,
    }

    uid = owner_user_id
    ind_buy = _timed_indicator(
        "buy_alerts",
        lambda: _count_marketplace_opportunities(session, owner_user_id=uid, recommendations=("STRONG_BUY",)),
    )
    ind_sell = _timed_indicator("sell_alerts", lambda: _count_hold_sell_recommendations(session, owner_user_id=uid))
    ind_grade = _timed_indicator("grade_alerts", lambda: _count_grade_candidates(session, owner_user_id=uid))
    ind_storage = _timed_indicator("storage_issues", lambda: _indicator_storage(session, owner_user_id=uid))
    ind_deals = _timed_indicator(
        "marketplace_deals",
        lambda: _count_marketplace_opportunities(
            session, owner_user_id=uid, recommendations=("STRONG_BUY", "GOOD_BUY")
        ),
    )
    ind_future = _timed_indicator("future_pull_list", lambda: _count_future_pull_list(session, owner_user_id=uid))
    ind_discovery = _timed_indicator("discovery_alerts", lambda: _count_discovery_alerts(session, owner_user_id=uid))

    sections = [
        _section_skipped(
            "buy_alerts",
            "Buy alerts",
            empty_hint="Open Marketplace Opportunities for buy alerts.",
            reason=skipped,
            indicator=ind_buy,
        ),
        _section_skipped(
            "sell_alerts",
            "Sell alerts",
            empty_hint="Open Sell Queue for sell recommendations.",
            reason=skipped,
            indicator=ind_sell,
        ),
        _section_skipped(
            "grade_alerts",
            "Grade alerts",
            empty_hint="Open Sell Queue for grade candidates.",
            reason=skipped,
            indicator=ind_grade,
        ),
        _attach_indicator(
            _timed_section(
                "foc_alerts",
                "FOC alerts",
                empty_hint="No cached FOC alerts yet; open FOC Dashboard to generate a snapshot.",
                build_items=lambda: _foc_alert_items(session, owner_user_id=owner_user_id),
            ),
            _timed_indicator("foc_alerts", lambda: _indicator_foc(session, owner_user_id=uid)),
        ),
        _section_skipped(
            "storage_issues",
            "Storage issues",
            empty_hint="Open Storage Dashboard for location status.",
            reason=skipped,
            indicator=ind_storage,
        ),
        _section_skipped(
            "marketplace_deals",
            "Marketplace deals",
            empty_hint="Open Marketplace Opportunities for deals.",
            reason=skipped,
            indicator=ind_deals,
        ),
        _section_skipped(
            "future_pull_list",
            "Future pull list",
            empty_hint="Open Future Pull List for recommendations.",
            reason=skipped,
            indicator=ind_future,
        ),
        _section_skipped(
            "discovery_alerts",
            "Discovery alerts",
            empty_hint="Open Discovery Dashboard for alerts.",
            reason=skipped,
            indicator=ind_discovery,
        ),
    ]

    elapsed = time.monotonic() - started
    logger.info("collector_home total elapsed_ms=%s owner=%s", round(elapsed * 1000, 1), owner_user_id)

    return P85CollectorHomeRead(
        headline="Fast operational dashboard",
        todays_actions=[],
        todays_actions_status="SKIPPED",
        todays_actions_error="Open Daily Actions for the full list.",
        sections=sections,
        budget_status=budget_status,
        portfolio_movement=portfolio_movement,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
