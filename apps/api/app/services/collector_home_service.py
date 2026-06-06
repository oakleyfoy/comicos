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
_SECTION_TIMEOUT_SECONDS = 1.5
# Sell queue is heavy on large inventories; keep it off home until bounded.
_COLLECTOR_HOME_ENABLE_SELL_SECTIONS = False
# Acquisition + daily actions both hit forward title index (~10s+ on prod).
_COLLECTOR_HOME_ENABLE_ACQUISITION_SECTIONS = False

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


def _run_bounded_soft(
    *,
    owner_user_id: int,
    timeout_seconds: float,
    fn: Callable[[Session, int], T],
) -> tuple[T | None, str | None]:
    try:
        return _run_bounded(owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=fn), None
    except Exception as exc:  # noqa: BLE001
        return None, _short_error(exc)


def _remaining_seconds(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


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


def _section_from_prefetch(
    key: str,
    title: str,
    *,
    empty_hint: str,
    prefetched: list[dict] | None,
    skip_reason: str,
    load_error: str | None = None,
) -> P85CollectorHomeSectionRead:
    if load_error:
        return P85CollectorHomeSectionRead(
            key=key,
            title=title,
            items=[],
            empty_hint=empty_hint,
            count=0,
            status="ERROR",
            error=load_error,
        )
    if prefetched is None:
        return _section_skipped(key, title, empty_hint=empty_hint, reason=skip_reason)
    return _section_ok(key, title, prefetched, empty_hint=empty_hint)


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


def _load_portfolio_movement(
    _session: Session | None,
    *,
    owner_user_id: int,
    timeout_seconds: float,
) -> dict:
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


def _prefetch_acquisition_rows(owner_user_id: int, *, timeout_seconds: float) -> tuple[list | None, str | None]:
    def _load(bounded_session: Session, uid: int) -> list:
        return list(
            list_acquisition_opportunities(
                bounded_session,
                owner_user_id=uid,
                recommendation=None,
                limit=_HOME_LIMIT,
                offset=0,
                refresh=False,
            ).items
        )

    rows, err = _run_bounded_soft(
        owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load
    )
    if rows is None and err is None:
        err = "Section timed out; open the dedicated page for full data."
    return rows, err


def _prefetch_foc_rows(owner_user_id: int, *, timeout_seconds: float) -> list | None:
    def _load(bounded_session: Session, uid: int) -> list:
        return list(
            list_future_pull_list(
                bounded_session,
                owner_user_id=uid,
                limit=_HOME_LIMIT,
                offset=0,
                refresh=False,
            ).items
        )

    return _run_bounded(owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load)


def _prefetch_discovery_rows(owner_user_id: int, *, timeout_seconds: float) -> list | None:
    def _load(bounded_session: Session, uid: int) -> list:
        return list(list_alerts(bounded_session, owner_user_id=uid, limit=_HOME_LIMIT, offset=0).items)

    return _run_bounded(owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load)


def _prefetch_storage_rows(owner_user_id: int, *, timeout_seconds: float) -> list[dict] | None:
    def _load(bounded_session: Session, uid: int) -> list[dict]:
        return _storage_issue_items(bounded_session, owner_user_id=uid)

    return _run_bounded(owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load)


def _prefetch_todays_actions(
    owner_user_id: int,
    *,
    timeout_seconds: float,
) -> tuple[list[P85CollectorHomeActionRead], str, str]:
    def _load(bounded_session: Session, uid: int) -> tuple[list[P85CollectorHomeActionRead], str, str]:
        return _load_todays_actions(bounded_session, owner_user_id=uid)

    payload, err = _run_bounded_soft(
        owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load
    )
    if payload is not None:
        return payload
    if err:
        return [], "ERROR", err
    return [], "SKIPPED", "Daily actions timed out; open Daily Actions for the full list."


def _prefetch_budget_status(owner_user_id: int, *, timeout_seconds: float) -> dict:
    def _load(bounded_session: Session, uid: int) -> dict:
        return _load_budget_status(bounded_session, owner_user_id=uid)

    payload, err = _run_bounded_soft(
        owner_user_id=owner_user_id, timeout_seconds=timeout_seconds, fn=_load
    )
    if payload is not None:
        return payload
    if err:
        return {
            "status": "ERROR",
            "error": err,
            "state": None,
            "monthly_budget": None,
            "monthly_spend": None,
        }
    return {
        "status": "SKIPPED",
        "error": "Budget status timed out.",
        "state": None,
        "monthly_budget": None,
        "monthly_spend": None,
    }


def _prefetch_portfolio_movement(owner_user_id: int, *, timeout_seconds: float) -> dict:
    return _load_portfolio_movement(
        None,
        owner_user_id=owner_user_id,
        timeout_seconds=timeout_seconds,
    )


def build_collector_home(session: Session, *, owner_user_id: int) -> P85CollectorHomeRead:
    started = time.monotonic()
    deadline = started + _HOME_DEADLINE_SECONDS
    timed_out = "Section timed out; open the dedicated page for full data."

    prefetch_timeout = min(_SECTION_TIMEOUT_SECONDS, _remaining_seconds(deadline))
    wait_cap = prefetch_timeout + 0.35
    acquisition_error: str | None = None
    acquisition_rows: list | None = None
    foc_rows: list | None = None
    discovery_rows: list | None = None
    storage_rows: list[dict] | None = None
    todays: list[P85CollectorHomeActionRead] = []
    todays_status = "OK"
    todays_error = ""
    budget_status: dict = {
        "status": "SKIPPED",
        "error": "",
        "state": None,
        "monthly_budget": None,
        "monthly_spend": None,
    }
    portfolio_movement: dict = {
        "status": "SKIPPED",
        "error": "",
        "current_value": None,
        "risk_category": None,
        "risk_score": None,
    }

    worker_count = 7 if _COLLECTOR_HOME_ENABLE_ACQUISITION_SECTIONS else 6
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        fut_today = pool.submit(
            _prefetch_todays_actions, owner_user_id, timeout_seconds=prefetch_timeout
        )
        fut_budget = pool.submit(
            _prefetch_budget_status, owner_user_id, timeout_seconds=prefetch_timeout
        )
        fut_port = pool.submit(
            _prefetch_portfolio_movement, owner_user_id, timeout_seconds=prefetch_timeout
        )
        fut_foc = pool.submit(_prefetch_foc_rows, owner_user_id, timeout_seconds=prefetch_timeout)
        fut_disc = pool.submit(
            _prefetch_discovery_rows, owner_user_id, timeout_seconds=prefetch_timeout
        )
        fut_stor = pool.submit(
            _prefetch_storage_rows, owner_user_id, timeout_seconds=prefetch_timeout
        )
        fut_acq = None
        if _COLLECTOR_HOME_ENABLE_ACQUISITION_SECTIONS:
            fut_acq = pool.submit(
                _prefetch_acquisition_rows, owner_user_id, timeout_seconds=prefetch_timeout
            )
        try:
            todays, todays_status, todays_error = fut_today.result(timeout=wait_cap)
            budget_status = fut_budget.result(timeout=wait_cap)
            portfolio_movement = fut_port.result(timeout=wait_cap)
            foc_rows = fut_foc.result(timeout=wait_cap)
            discovery_rows = fut_disc.result(timeout=wait_cap)
            storage_rows = fut_stor.result(timeout=wait_cap)
            if fut_acq is not None:
                acquisition_rows, acquisition_error = fut_acq.result(timeout=wait_cap)
        except concurrent.futures.TimeoutError:
            logger.warning("collector_home parallel prefetch wait exceeded %.2fs", wait_cap)
            foc_rows = discovery_rows = storage_rows = None
            acquisition_rows = None
            acquisition_error = timed_out

    buy_alert_items: list[dict] | None = None
    marketplace_items: list[dict] | None = None
    if acquisition_rows is not None:
        buy_alert_items = [
            {"title": i.title, "score": i.opportunity_score, "url": f"/marketplace-opportunity/{i.id}"}
            for i in acquisition_rows
            if i.recommendation == "STRONG_BUY"
        ]
        marketplace_items = [
            {"title": i.title, "recommendation": i.recommendation}
            for i in acquisition_rows
        ]

    foc_alert_items: list[dict] | None = None
    future_pull_items: list[dict] | None = None
    if foc_rows is not None:
        foc_alert_items = [{"title": p.title, "status": p.pipeline_status} for p in foc_rows]
        future_pull_items = [
            {"title": p.title, "action": p.recommendation_action}
            for p in foc_rows
        ]

    discovery_items: list[dict] | None = None
    if discovery_rows is not None:
        discovery_items = [{"title": a.title, "priority": a.priority} for a in discovery_rows]

    def sell_items():
        if not _COLLECTOR_HOME_ENABLE_SELL_SECTIONS:
            return []
        return list(
            build_sell_queue(
                session, owner_user_id=owner_user_id, limit=_HOME_LIMIT, offset=0, refresh_upstream=False
            ).items
        )

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

    acquisition_section_defs = (
        [
            _section_skipped(
                "buy_alerts",
                "Buy alerts",
                empty_hint="Open Marketplace Opportunities for buy alerts.",
                reason="Temporarily disabled on Collector Home (slow title index).",
            ),
            _section_skipped(
                "marketplace_deals",
                "Marketplace deals",
                empty_hint="Open Marketplace Opportunities for deals.",
                reason="Temporarily disabled on Collector Home (slow title index).",
            ),
        ]
        if not _COLLECTOR_HOME_ENABLE_ACQUISITION_SECTIONS
        else [
            _section_from_prefetch(
                "buy_alerts",
                "Buy alerts",
                empty_hint="Scan marketplace opportunities or check discovery feed.",
                prefetched=buy_alert_items,
                skip_reason=timed_out,
                load_error=acquisition_error,
            ),
            _section_from_prefetch(
                "marketplace_deals",
                "Marketplace deals",
                empty_hint="Run marketplace acquisition scan or refresh deals.",
                prefetched=marketplace_items,
                skip_reason=timed_out,
                load_error=acquisition_error,
            ),
        ]
    )

    sections = [
        acquisition_section_defs[0],
        *sell_section_defs,
        _section_from_prefetch(
            "foc_alerts",
            "FOC alerts",
            empty_hint="Add future releases or watchlists to see FOC reminders.",
            prefetched=foc_alert_items,
            skip_reason=timed_out,
        ),
        _section_from_prefetch(
            "storage_issues",
            "Storage issues",
            empty_hint="Assign storage locations as you add inventory.",
            prefetched=storage_rows,
            skip_reason=timed_out,
        ),
        acquisition_section_defs[1],
        _section_from_prefetch(
            "future_pull_list",
            "Future pull list",
            empty_hint="Personalize discovery to build your future pull list.",
            prefetched=future_pull_items,
            skip_reason=timed_out,
        ),
        _section_from_prefetch(
            "discovery_alerts",
            "Discovery alerts",
            empty_hint="No active discovery alerts — check the discovery dashboard.",
            prefetched=discovery_items,
            skip_reason=timed_out,
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
