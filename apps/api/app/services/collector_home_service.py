"""Fast P85 collector home built from cached operational snapshots."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot
from app.models.p77_collector_profile import P77CollectorBudget
from app.models.p82_p84_collector_expansion import CollectionRiskSnapshot, CollectionValuationSnapshot
from app.schemas.p85_production_hardening import (
    P85CollectorHomeRead,
    P85CollectorHomeSectionRead,
)

logger = logging.getLogger(__name__)

_HOME_LIMIT = 10
_SECTION_MAX_SECONDS = 0.5


def _short_error(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return message[:240]


def _section_ok(key: str, title: str, items: list[dict], *, empty_hint: str) -> P85CollectorHomeSectionRead:
    return P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=items[:_HOME_LIMIT],
        empty_hint=empty_hint if not items else "",
        count=len(items),
        status="OK",
        error="",
    )


def _section_skipped(key: str, title: str, *, empty_hint: str, reason: str) -> P85CollectorHomeSectionRead:
    return P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=[],
        empty_hint=empty_hint,
        count=0,
        status="SKIPPED",
        error=reason[:240],
    )


def _section_error(
    key: str,
    title: str,
    *,
    empty_hint: str,
    exc: BaseException,
) -> P85CollectorHomeSectionRead:
    logger.warning("collector_home section %s failed: %s", key, exc, exc_info=True)
    return P85CollectorHomeSectionRead(
        key=key,
        title=title,
        items=[],
        empty_hint=empty_hint,
        count=0,
        status="ERROR",
        error=_short_error(exc),
    )


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
        _timed_section(
            "foc_alerts",
            "FOC alerts",
            empty_hint="No cached FOC alerts yet; open FOC Dashboard to generate a snapshot.",
            build_items=lambda: _foc_alert_items(session, owner_user_id=owner_user_id),
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
