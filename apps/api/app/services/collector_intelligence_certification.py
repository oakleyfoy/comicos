"""P62 collector suite certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.services.auto_watchlist_service import build_auto_watchlists, get_latest_watchlists, list_watchlist_items
from app.services.foc_intelligence_service import generate_foc_alerts, get_latest_foc_snapshot, list_foc_items
from app.services.future_pull_forecast_service import generate_future_pull_forecast, get_latest_pull_forecast, list_forecast_items
from app.services.p62_feature_flags import (
    p62_auto_watchlist_enabled,
    p62_foc_enabled,
    p62_pull_forecast_enabled,
)


def certify_foc_intelligence(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    snap = generate_foc_alerts(session, owner_user_id=owner_user_id)
    items, total = list_foc_items(session, snapshot_id=int(snap.id or 0), limit=500, offset=0)
    ok_order = all(items[i].urgency_score >= items[i + 1].urgency_score for i in range(len(items) - 1)) if len(items) > 1 else True
    ok_dates = all(i.foc_date is not None for i in items) if items else True
    ok = snap.total_items == total and (total == 0 or (ok_order and ok_dates))
    if ok:
        notes.append(f"FOC alerts={total}")
    else:
        notes.append("FOC certification failed ordering or dates")
    return {
        "component": "P62-03_FOC",
        "certified": ok and p62_foc_enabled(),
        "status": "PASS" if ok else "NOT_READY",
        "summary": "FOC intelligence certified" if ok else "FOC not ready",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def certify_pull_forecast(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    fc = generate_future_pull_forecast(session, owner_user_id=owner_user_id)
    items, total = list_forecast_items(session, forecast_id=int(fc.id or 0), limit=500, offset=0)
    ok_conf = all(i.confidence in ("HIGH", "MEDIUM", "LOW") for i in items)
    ok_expl = all(bool(i.explanation) for i in items) if items else True
    ok = fc.total_items == total and ok_conf and ok_expl
    if ok:
        notes.append(f"Forecast items={total}")
    return {
        "component": "P62-04_PULL_FORECAST",
        "certified": ok and p62_pull_forecast_enabled(),
        "status": "PASS" if ok else "NOT_READY",
        "summary": "Pull forecast certified" if ok else "Pull forecast not ready",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def certify_auto_watchlists(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    built = build_auto_watchlists(session, owner_user_id=owner_user_id)
    latest = get_latest_watchlists(session, owner_user_id=owner_user_id)
    ok_build = len(latest) >= 1 or len(built) >= 1
    explained = True
    for wl in latest[:5]:
        for item in list_watchlist_items(session, watchlist_id=int(wl.id or 0)):
            if not item.inclusion_reason:
                explained = False
    if ok_build:
        notes.append(f"Watchlist types={len(latest)}")
    return {
        "component": "P62-05_AUTO_WATCHLIST",
        "certified": ok_build and explained and p62_auto_watchlist_enabled(),
        "status": "PASS" if ok_build else "NOT_READY",
        "summary": "Auto watchlists certified" if ok_build else "Auto watchlists not ready",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_collector_platform_certification(session: Session, *, owner_user_id: int) -> dict:
    foc = certify_foc_intelligence(session, owner_user_id=owner_user_id)
    forecast = certify_pull_forecast(session, owner_user_id=owner_user_id)
    watch = certify_auto_watchlists(session, owner_user_id=owner_user_id)
    ready = foc["certified"] and forecast["certified"] and watch["certified"]
    return {
        "platform_ready": ready,
        "foc": foc,
        "pull_forecast": forecast,
        "auto_watchlists": watch,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
