"""P83 collection valuation, risk, and optimization."""

from __future__ import annotations

from collections import Counter
from datetime import date

from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.p82_p84_collector_expansion import CollectionRiskSnapshot, CollectionValuationSnapshot, utc_now
from app.schemas.p82_p84_collector_expansion import (
    CollectionForecastRead,
    CollectionOptimizationRead,
    CollectionRiskRead,
    CollectionValuationDashboardRead,
    ForecastHorizonRead,
)
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p78_sell_queue_service import build_sell_queue


_HORIZONS = {
    "30_DAYS": (1.02, 0.75),
    "90_DAYS": (1.05, 0.7),
    "6_MONTHS": (1.08, 0.65),
    "12_MONTHS": (1.12, 0.6),
}


def _collection_value(session: Session, *, owner_user_id: int) -> tuple[float, list[InventoryCopy]]:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
    total = sum(float(c.current_fmv or c.acquisition_cost or 0) for c in copies if (c.hold_status or "") != "sold")
    return round(total, 2), copies


def _publisher_exposure(session: Session, copies: list[InventoryCopy]) -> Counter:
    counts: Counter = Counter()
    for c in copies:
        if c.variant_id is None:
            continue
        v = session.get(Variant, c.variant_id)
        if not v or not v.comic_issue_id:
            continue
        issue = session.get(ComicIssue, v.comic_issue_id)
        if not issue or not issue.comic_title_id:
            continue
        title = session.get(ComicTitle, issue.comic_title_id)
        if title and title.publisher_id:
            pub = session.get(Publisher, title.publisher_id)
            if pub:
                counts[pub.name] += 1
    return counts


def build_collection_forecast(session: Session, *, owner_user_id: int, persist: bool = True) -> CollectionForecastRead:
    current, copies = _collection_value(session, owner_user_id=owner_user_id)
    horizons: list[ForecastHorizonRead] = []
    for key, (mult, conf) in _HORIZONS.items():
        fv = round(current * mult, 2)
        horizons.append(
            ForecastHorizonRead(
                horizon=key,
                forecast_value=fv,
                forecast_change=round(fv - current, 2),
                confidence=conf,
            )
        )
    top_gain = sorted(copies, key=lambda c: float(c.current_fmv or 0), reverse=True)[:5]
    gain_contrib = [
        {"copy_id": int(c.id or 0), "fmv": float(c.current_fmv or 0)} for c in top_gain
    ]
    risks = [{"factor": "Market trend sensitivity", "weight": "MEDIUM"}]
    snap_id = None
    if persist:
        snap = CollectionValuationSnapshot(
            owner_user_id=owner_user_id,
            snapshot_date=date.today(),
            current_value=current,
            forecast_json={"horizons": [h.model_dump() for h in horizons]},
            optimization_json={},
            created_at=utc_now(),
        )
        session.add(snap)
        session.flush()
        snap_id = int(snap.id or 0)
    return CollectionForecastRead(
        current_value=current,
        horizons=horizons,
        top_gain_contributors=gain_contrib,
        top_downside_risks=risks,
        snapshot_id=snap_id,
    )


def build_collection_risk(session: Session, *, owner_user_id: int, persist: bool = True) -> CollectionRiskRead:
    _, copies = _collection_value(session, owner_user_id=owner_user_id)
    pubs = _publisher_exposure(session, copies)
    total = max(1, len(copies))
    top_pub_share = (max(pubs.values()) / total * 100.0) if pubs else 0.0
    duplicates = sum(1 for c in copies if (c.hold_status or "") == "hold") // max(1, len(set(c.variant_id for c in copies)))
    low_liq = sum(1 for c in copies if float(c.current_fmv or 0) < 5)
    risk = 25.0
    factors: dict = {}
    if top_pub_share > 40:
        risk += 25
        factors["publisher_concentration"] = round(top_pub_share, 1)
    if duplicates > 3:
        risk += 15
        factors["duplicate_concentration"] = duplicates
    if low_liq > total * 0.3:
        risk += 12
        factors["low_liquidity_holdings"] = low_liq
    risk = min(100.0, risk)
    if risk >= 65:
        cat = "HIGH_RISK"
    elif risk >= 40:
        cat = "MODERATE_RISK"
    else:
        cat = "LOW_RISK"
    snap_id = None
    if persist:
        snap = CollectionRiskSnapshot(
            owner_user_id=owner_user_id,
            snapshot_date=date.today(),
            risk_score=risk,
            risk_category=cat,
            factors_json=factors,
            created_at=utc_now(),
        )
        session.add(snap)
        session.flush()
        snap_id = int(snap.id or 0)
    return CollectionRiskRead(risk_score=risk, risk_category=cat, factors=factors, snapshot_id=snap_id)  # type: ignore[arg-type]


def build_collection_optimization(session: Session, *, owner_user_id: int) -> CollectionOptimizationRead:
    queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=20, offset=0, refresh_upstream=False)
    buys = list_acquisition_opportunities(session, owner_user_id=owner_user_id, recommendation="STRONG_BUY", limit=10, offset=0)
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    sell_candidates = [{"title": i.title, "fmv": i.fmv, "priority": i.priority} for i in queue.items[:8]]
    grade_candidates = [{"title": i.title, "fmv": i.fmv} for i in queue.items if i.fmv >= 25][:5]
    hold_candidates = [{"title": i.title} for i in queue.items if i.priority == "WATCH"][:5]
    buy_targets = [{"title": b.title, "score": b.opportunity_score} for b in buys.items[:5]]
    reduce_exp = []
    if ctx.budget_state == "RED":
        reduce_exp.append("Discretionary spec buys")
    increase = [p.label for p in ctx.profile.publishers[:3]]
    return CollectionOptimizationRead(
        sell_candidates=sell_candidates,
        grade_candidates=grade_candidates,
        hold_candidates=hold_candidates,
        buy_targets=buy_targets,
        reduce_exposure=reduce_exp,
        increase_exposure=increase,
    )


def build_valuation_dashboard(session: Session, *, owner_user_id: int) -> CollectionValuationDashboardRead:
    return CollectionValuationDashboardRead(
        forecast=build_collection_forecast(session, owner_user_id=owner_user_id),
        risk=build_collection_risk(session, owner_user_id=owner_user_id),
        optimization=build_collection_optimization(session, owner_user_id=owner_user_id),
    )
