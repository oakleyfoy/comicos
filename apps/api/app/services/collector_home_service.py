"""P85 unified collector home — aggregates P77–P84 without duplicating engines."""

from __future__ import annotations

import concurrent.futures
import logging
import time
from datetime import datetime, timezone
from typing import Callable, TypeVar

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.schemas.p85_production_hardening import (
    P85CollectorHomeActionRead,
    P85CollectorHomeRead,
    P85CollectorHomeSectionRead,
)
from app.services.collection_valuation_service import build_collection_forecast, build_collection_risk
from app.services.daily_action_engine import list_latest_daily_actions
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p81_discovery_personalization_service import list_alerts, list_future_pull_list
from app.services.storage_dashboard_service import build_storage_dashboard

logger = logging.getLogger(__name__)

_HOME_LIMIT = 10
_HOME_DEADLINE_SECONDS = 5.0
_SECTION_TIMEOUT_SECONDS = 2.0
# Sell queue is heavy on large inventories; keep it off home until bounded.
_COLLECTOR_HOME_ENABLE_SELL_SECTIONS = False

T = TypeVar("T")


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


def _section_error(key: str, title: str, *, empty_hint: str, exc: BaseException) -> P85CollectorHomeSectionRead:
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


def _run_bounded(
    *,
    owner_user_id: int,
    timeout_seconds: float,
    fn: Callable[[Session, int], T],
) -> T | None:
    from app.db.session import get_engine

    def _work() -> T:
        with Session(get_engine()) as bounded_session:
            return fn(bounded_session, owner_user_id)

    workers = 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future = pool.submit(_work)
        try:
            return future.result(timeout=max(0.05, timeout_seconds))
        except concurrent.futures.TimeoutError:
            logger.warning("collector_home bounded call timed out after %.2fs", timeout_seconds)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("collector_home bounded call failed: %s", exc, exc_info=True)
            raise


def _safe_section(
    key: str,
    title: str,
    *,
    empty_hint: str,
    build_items: Callable[[], list[dict]],
    deadline: float | None = None,
) -> P85CollectorHomeSectionRead:
    if deadline is not None and time.monotonic() >= deadline:
        return _section_skipped(
            key,
            title,
            empty_hint=empty_hint,
            reason="Skipped: collector home time budget exceeded.",
        )
    try:
        return _section_ok(key, title, build_items(), empty_hint=empty_hint)
    except Exception as exc:  # noqa: BLE001 — isolate subsystem failures for home page
        return _section_error(key, title, empty_hint=empty_hint, exc=exc)


def _load_todays_actions(session: Session, *, owner_user_id: int) -> tuple[list[P85CollectorHomeActionRead], str, str]:
    try:
        daily_items, _ = list_latest_daily_actions(
            session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0
        )
        todays: list[P85CollectorHomeActionRead] = []
        for row in daily_items:
            todays.append(
                P85CollectorHomeActionRead(
                    title=row.title,
                    action_type=row.action_type,
                    priority_score=float(row.priority_score),
                    source="daily_actions",
                    action_url="/daily-actions",
                )
            )
        return todays[:_HOME_LIMIT], "OK", ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("collector_home today_actions failed: %s", exc, exc_info=True)
        return [], "ERROR", _short_error(exc)


def _load_budget_status(session: Session, *, owner_user_id: int) -> dict:
    try:
        ctx = load_personalization_context(session, owner_user_id=owner_user_id)
        return {
            "status": "OK",
            "error": "",
            "state": ctx.budget_state,
            "monthly_budget": ctx.monthly_budget,
            "monthly_spend": ctx.monthly_spend,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("collector_home budget_status failed: %s", exc, exc_info=True)
        return {
            "status": "ERROR",
            "error": _short_error(exc),
            "state": None,
            "monthly_budget": None,
            "monthly_spend": None,
        }


def _load_portfolio_movement(session: Session, *, owner_user_id: int, timeout_seconds: float) -> dict:
    def _compute(bounded_session: Session, uid: int) -> dict:
        forecast = build_collection_forecast(bounded_session, owner_user_id=uid, persist=False)
        risk = build_collection_risk(bounded_session, owner_user_id=uid, persist=False)
        return {
            "status": "OK",
            "error": "",
            "current_value": forecast.current_value,
            "risk_category": risk.risk_category,
            "risk_score": risk.risk_score,
        }

    try:
        result = _run_bounded(
            owner_user_id=owner_user_id,
            timeout_seconds=timeout_seconds,
            fn=_compute,
        )
        if result is None:
            return {
                "status": "SKIPPED",
                "error": "Portfolio summary timed out; open portfolio views for full detail.",
                "current_value": None,
                "risk_category": None,
                "risk_score": None,
            }
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("collector_home portfolio_movement failed: %s", exc, exc_info=True)
        return {
            "status": "ERROR",
            "error": _short_error(exc),
            "current_value": None,
            "risk_category": None,
            "risk_score": None,
        }


def _headline_for_owner(session: Session, *, owner_user_id: int) -> str:
    try:
        inv_count = len(
            list(
                session.exec(
                    select(InventoryCopy)
                    .where(InventoryCopy.user_id == owner_user_id)
                    .where(InventoryCopy.hold_status != "sold")
                    .limit(1)
                ).all()
            )
        )
        if inv_count == 0:
            return "Start by adding inventory or importing an order."
        return "What should I do today?"
    except Exception:  # noqa: BLE001
        return "What should I do today?"


def build_collector_home(session: Session, *, owner_user_id: int) -> P85CollectorHomeRead:
    started = time.monotonic()
    deadline = started + _HOME_DEADLINE_SECONDS

    todays, todays_status, todays_error = _load_todays_actions(session, owner_user_id=owner_user_id)
    budget_status = _load_budget_status(session, owner_user_id=owner_user_id)
    portfolio_timeout = min(_SECTION_TIMEOUT_SECONDS, max(0.25, deadline - time.monotonic()))
    portfolio_movement = _load_portfolio_movement(
        session, owner_user_id=owner_user_id, timeout_seconds=portfolio_timeout
    )

    acquisition_cache: dict[str, object] = {}
    sell_cache: dict[str, object] = {}
    foc_cache: dict[str, object] = {}

    def acquisition_items(*, strong_buy_only: bool) -> list:
        cache_key = "strong_buy" if strong_buy_only else "all"
        if cache_key not in acquisition_cache:
            acquisition_cache[cache_key] = list_acquisition_opportunities(
                session,
                owner_user_id=owner_user_id,
                recommendation="STRONG_BUY" if strong_buy_only else None,
                limit=_HOME_LIMIT,
                offset=0,
                refresh=False,
            ).items
        return list(acquisition_cache[cache_key])  # type: ignore[arg-type]

    def sell_items():
        if not _COLLECTOR_HOME_ENABLE_SELL_SECTIONS:
            return []
        if "items" not in sell_cache:
            sell_cache["items"] = build_sell_queue(
                session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0, refresh_upstream=False
            ).items
        return list(sell_cache["items"])  # type: ignore[arg-type]

    def foc_items():
        if "items" not in foc_cache:
            foc_cache["items"] = list_future_pull_list(
                session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0, refresh=False
            ).items
        return list(foc_cache["items"])  # type: ignore[arg-type]

    sell_section_defs = (
        [
            _section_skipped(
                "sell_alerts",
                "Sell alerts",
                empty_hint="Open Sell Queue for sell recommendations.",
                reason="Temporarily disabled on Collector Home (slow sell queue build).",
            ),
            _section_skipped(
                "grade_alerts",
                "Grade alerts",
                empty_hint="Open Sell Queue for grade candidates.",
                reason="Temporarily disabled on Collector Home (slow sell queue build).",
            ),
        ]
        if not _COLLECTOR_HOME_ENABLE_SELL_SECTIONS
        else [
            _safe_section(
                "sell_alerts",
                "Sell alerts",
                empty_hint="Review sell queue after FMV is set on your copies.",
                deadline=deadline,
                build_items=lambda: [
                    {"title": s.title, "fmv": s.fmv, "priority": s.priority}
                    for s in sell_items()
                    if s.priority in {"HIGH", "MEDIUM"}
                ],
            ),
            _safe_section(
                "grade_alerts",
                "Grade alerts",
                empty_hint="High-FMV raw copies will appear here from the sell queue.",
                deadline=deadline,
                build_items=lambda: [
                    {"title": g.title, "fmv": g.fmv}
                    for g in [s for s in sell_items() if s.fmv >= 20][:_HOME_LIMIT]
                ],
            ),
        ]
    )

    sections = [
        _safe_section(
            "buy_alerts",
            "Buy alerts",
            empty_hint="Scan marketplace opportunities or check discovery feed.",
            deadline=deadline,
            build_items=lambda: [
                {"title": i.title, "score": i.opportunity_score, "url": f"/marketplace-opportunity/{i.id}"}
                for i in acquisition_items(strong_buy_only=True)
            ],
        ),
        *sell_section_defs,
        _safe_section(
            "foc_alerts",
            "FOC alerts",
            empty_hint="Add future releases or watchlists to see FOC reminders.",
            deadline=deadline,
            build_items=lambda: [
                {"title": p.title, "status": p.pipeline_status}
                for p in foc_items()
            ],
        ),
        _safe_section(
            "storage_issues",
            "Storage issues",
            empty_hint="Assign storage locations as you add inventory.",
            deadline=deadline,
            build_items=lambda: _storage_issue_items(session, owner_user_id=owner_user_id),
        ),
        _safe_section(
            "marketplace_deals",
            "Marketplace deals",
            empty_hint="Run marketplace acquisition scan or refresh deals.",
            deadline=deadline,
            build_items=lambda: [
                {"title": i.title, "recommendation": i.recommendation}
                for i in acquisition_items(strong_buy_only=False)
            ],
        ),
        _safe_section(
            "future_pull_list",
            "Future pull list",
            empty_hint="Personalize discovery to build your future pull list.",
            deadline=deadline,
            build_items=lambda: [
                {"title": p.title, "action": p.recommendation_action}
                for p in foc_items()
            ],
        ),
        _safe_section(
            "discovery_alerts",
            "Discovery alerts",
            empty_hint="No active discovery alerts — check the discovery dashboard.",
            deadline=deadline,
            build_items=lambda: [
                {"title": a.title, "priority": a.priority}
                for a in list_alerts(session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0).items
            ],
        ),
    ]

    elapsed = time.monotonic() - started
    if elapsed > _HOME_DEADLINE_SECONDS:
        logger.warning(
            "collector_home exceeded %.1fs budget (%.2fs) owner=%s",
            _HOME_DEADLINE_SECONDS,
            elapsed,
            owner_user_id,
        )

    return P85CollectorHomeRead(
        headline=_headline_for_owner(session, owner_user_id=owner_user_id),
        todays_actions=todays,
        todays_actions_status=todays_status,
        todays_actions_error=todays_error,
        sections=sections,
        budget_status=budget_status,
        portfolio_movement=portfolio_movement,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _storage_issue_items(session: Session, *, owner_user_id: int) -> list[dict]:
    dash = build_storage_dashboard(session, owner_user_id=owner_user_id)
    if dash.unassigned_books > 0:
        return [{"type": "UNASSIGNED", "count": dash.unassigned_books, "label": "Unassigned copies"}]
    return []
