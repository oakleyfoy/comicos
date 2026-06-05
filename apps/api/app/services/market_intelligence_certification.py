"""P63 platform certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.services.market_signal_service import build_market_signals, get_latest_market_signal_snapshot, list_market_signal_items
from app.services.p63_acquisition_opportunity_service import (
    build_acquisition_opportunities,
    get_latest_acquisition_snapshot,
    list_acquisition_items,
)
from app.services.p63_feature_flags import (
    p63_acquisition_opportunities_enabled,
    p63_market_intelligence_enabled,
    p63_market_signals_enabled,
    p63_portfolio_performance_enabled,
    p63_sell_signals_enabled,
)
from app.services.portfolio_performance_service import (
    build_portfolio_performance_snapshot,
    get_latest_portfolio_snapshot,
    list_portfolio_items,
)
from app.services.sell_signal_service import build_sell_signals, get_latest_sell_signal_snapshot, list_sell_signal_items


def _component_result(*, component: str, ok: bool, notes: list[str]) -> dict:
    return {
        "component": component,
        "certified": ok,
        "status": "PASS" if ok else "NOT_READY",
        "summary": f"{component} certified" if ok else f"{component} not ready",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def certify_portfolio_performance(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    snap = build_portfolio_performance_snapshot(session, owner_user_id=owner_user_id)
    items, total = list_portfolio_items(session, snapshot_id=int(snap.id or 0))
    ok = snap.total_items == total and (total > 0 or snap.total_items == 0)
    if total == 0:
        notes.append("empty_owner")
        ok = False
    else:
        notes.append(f"portfolio_items={total}")
    certified = ok and p63_portfolio_performance_enabled() and p63_market_intelligence_enabled()
    return _component_result(component="P63-01_PORTFOLIO", ok=certified, notes=notes)


def certify_sell_signals(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    snap = build_sell_signals(session, owner_user_id=owner_user_id)
    items, total = list_sell_signal_items(session, snapshot_id=int(snap.id or 0))
    ok_order = all(items[i].sell_score >= items[i + 1].sell_score for i in range(len(items) - 1)) if len(items) > 1 else True
    ok = snap.total_items == total and ok_order and total > 0
    if total == 0:
        notes.append("empty_owner")
        ok = False
    else:
        notes.append(f"sell_items={total}")
    certified = ok and p63_sell_signals_enabled() and p63_market_intelligence_enabled()
    return _component_result(component="P63-02_SELL_SIGNALS", ok=certified, notes=notes)


def certify_acquisition_opportunities(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    snap = build_acquisition_opportunities(session, owner_user_id=owner_user_id)
    items, total = list_acquisition_items(session, snapshot_id=int(snap.id or 0))
    ok = snap.total_items == total
    notes.append(f"acquisition_items={total}")
    certified = ok and p63_acquisition_opportunities_enabled() and p63_market_intelligence_enabled()
    return _component_result(component="P63-03_ACQUISITION", ok=certified, notes=notes)


def certify_market_signals(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    build_portfolio_performance_snapshot(session, owner_user_id=owner_user_id)
    build_sell_signals(session, owner_user_id=owner_user_id)
    build_acquisition_opportunities(session, owner_user_id=owner_user_id)
    snap = build_market_signals(session, owner_user_id=owner_user_id)
    items, total = list_market_signal_items(session, snapshot_id=int(snap.id or 0))
    ok_expl = all(bool(i.signal_reason) for i in items) if items else True
    ok = snap.total_items == total and ok_expl and total > 0
    if total == 0:
        ok = False
        notes.append("no_signals")
    else:
        notes.append(f"signals={total}")
    certified = ok and p63_market_signals_enabled() and p63_market_intelligence_enabled()
    return _component_result(component="P63-04_MARKET_SIGNALS", ok=certified, notes=notes)


def get_market_platform_certification(session: Session, *, owner_user_id: int) -> dict:
    portfolio = certify_portfolio_performance(session, owner_user_id=owner_user_id)
    sell = certify_sell_signals(session, owner_user_id=owner_user_id)
    acq = certify_acquisition_opportunities(session, owner_user_id=owner_user_id)
    signals = certify_market_signals(session, owner_user_id=owner_user_id)
    ready = all(
        c["certified"]
        for c in (portfolio, sell, acq, signals)
    )
    return {
        "platform_ready": ready,
        "portfolio": portfolio,
        "sell_signals": sell,
        "acquisition": acq,
        "market_signals": signals,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
