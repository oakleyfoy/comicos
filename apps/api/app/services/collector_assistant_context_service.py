"""P64 upstream context loader (read-only)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, func, select

from app.models.asset_ledger import InventoryCopy
from app.models.collector_assistant import RUN_STATUS_NOT_READY
from app.services.auto_watchlist_service import get_latest_watchlists, list_watchlist_items
from app.services.buy_queue_service import get_latest_buy_queue_snapshot, list_buy_queue_items
from app.services.foc_intelligence_service import get_latest_foc_snapshot, list_foc_items
from app.services.future_pull_forecast_service import get_latest_pull_forecast, list_forecast_items
from app.services.market_signal_service import get_latest_market_signal_snapshot, list_market_signal_items
from app.services.p63_acquisition_opportunity_service import get_latest_acquisition_snapshot, list_acquisition_items
from app.services.portfolio_performance_service import get_latest_portfolio_snapshot, list_portfolio_items
from app.services.sell_signal_service import get_latest_sell_signal_snapshot, list_sell_signal_items


@dataclass
class CollectorAssistantContext:
    owner_user_id: int
    ready: bool
    readiness_reason: str
    inventory_count: int
    fingerprint: str
    freshness: dict = field(default_factory=dict)
    buy_queue_items: list = field(default_factory=list)
    foc_items: list = field(default_factory=list)
    pull_forecast_items: list = field(default_factory=list)
    watchlist_items: list = field(default_factory=list)
    portfolio_items: list = field(default_factory=list)
    portfolio_header: dict = field(default_factory=dict)
    sell_items: list = field(default_factory=list)
    acquisition_items: list = field(default_factory=list)
    market_signal_items: list = field(default_factory=list)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def load_collector_assistant_context(session: Session, *, owner_user_id: int) -> CollectorAssistantContext:
    inv_count = int(
        session.exec(select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).one()
    )

    freshness: dict = {}
    fp_parts: dict = {}

    bq_snap = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    buy_items: list = []
    if bq_snap:
        buy_items, _ = list_buy_queue_items(session, snapshot_id=int(bq_snap.id or 0), limit=100)
        freshness["p62_buy_queue"] = _iso(bq_snap.generated_at)
        fp_parts["buy_queue"] = int(bq_snap.id or 0)

    foc_snap = get_latest_foc_snapshot(session, owner_user_id=owner_user_id)
    foc_items: list = []
    if foc_snap:
        foc_items, _ = list_foc_items(session, snapshot_id=int(foc_snap.id or 0), limit=100)
        freshness["p62_foc"] = _iso(foc_snap.generated_at)
        fp_parts["foc"] = int(foc_snap.id or 0)

    fc_snap = get_latest_pull_forecast(session, owner_user_id=owner_user_id)
    forecast_items: list = []
    if fc_snap:
        forecast_items, _ = list_forecast_items(session, forecast_id=int(fc_snap.id or 0), limit=50)
        freshness["p62_pull_forecast"] = _iso(fc_snap.generated_at)
        fp_parts["pull_forecast"] = int(fc_snap.id or 0)

    watch_items: list = []
    for wl in get_latest_watchlists(session, owner_user_id=owner_user_id)[:8]:
        freshness.setdefault("p62_watchlists", _iso(wl.generated_at))
        watch_items.extend(list_watchlist_items(session, watchlist_id=int(wl.id or 0))[:15])
    if watch_items:
        fp_parts["watchlists"] = len(watch_items)

    port_snap = get_latest_portfolio_snapshot(session, owner_user_id=owner_user_id)
    port_items: list = []
    port_header: dict = {}
    if port_snap:
        port_items, _ = list_portfolio_items(session, snapshot_id=int(port_snap.id or 0), limit=200)
        port_header = {
            "total_unrealized_gain_pct": float(port_snap.total_unrealized_gain_pct),
            "total_items": port_snap.total_items,
        }
        freshness["p63_portfolio"] = _iso(port_snap.generated_at)
        fp_parts["portfolio"] = int(port_snap.id or 0)

    sell_snap = get_latest_sell_signal_snapshot(session, owner_user_id=owner_user_id)
    sell_items: list = []
    if sell_snap:
        sell_items, _ = list_sell_signal_items(session, snapshot_id=int(sell_snap.id or 0), limit=100)
        freshness["p63_sell"] = _iso(sell_snap.generated_at)
        fp_parts["sell"] = int(sell_snap.id or 0)

    acq_snap = get_latest_acquisition_snapshot(session, owner_user_id=owner_user_id)
    acq_items: list = []
    if acq_snap:
        acq_items, _ = list_acquisition_items(session, snapshot_id=int(acq_snap.id or 0), limit=75)
        freshness["p63_acquisition"] = _iso(acq_snap.generated_at)
        fp_parts["acquisition"] = int(acq_snap.id or 0)

    ms_snap = get_latest_market_signal_snapshot(session, owner_user_id=owner_user_id)
    signal_items: list = []
    if ms_snap:
        signal_items, _ = list_market_signal_items(session, snapshot_id=int(ms_snap.id or 0), limit=80)
        freshness["p63_market_signals"] = _iso(ms_snap.generated_at)
        fp_parts["market_signals"] = int(ms_snap.id or 0)

    raw = json.dumps(fp_parts, sort_keys=True)
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]

    ready = True
    reason = "ok"
    if inv_count > 0 and port_snap is None:
        ready = False
        reason = "missing_p63_portfolio"
    elif inv_count == 0 and not bq_snap and not foc_snap and not acq_snap:
        ready = False
        reason = "empty_owner"
    elif inv_count > 0 and sell_snap is None:
        ready = False
        reason = "missing_p63_sell_signals"

    return CollectorAssistantContext(
        owner_user_id=owner_user_id,
        ready=ready,
        readiness_reason=reason,
        inventory_count=inv_count,
        fingerprint=fingerprint,
        freshness=freshness,
        buy_queue_items=buy_items,
        foc_items=foc_items,
        pull_forecast_items=forecast_items,
        watchlist_items=watch_items,
        portfolio_items=port_items,
        portfolio_header=port_header,
        sell_items=sell_items,
        acquisition_items=acq_items,
        market_signal_items=signal_items,
    )
