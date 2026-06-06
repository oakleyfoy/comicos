"""P83 portfolio scenario planning."""

from __future__ import annotations

from sqlmodel import Session

from app.models.p82_p84_collector_expansion import CollectionScenarioRun, utc_now
from app.schemas.p82_p84_collector_expansion import CollectionScenarioRead
from app.services.collection_valuation_service import build_collection_forecast, build_collection_risk
from app.services.p78_sell_queue_service import build_sell_queue


def run_collection_scenario(session: Session, *, owner_user_id: int, scenario_type: str) -> CollectionScenarioRead:
    forecast = build_collection_forecast(session, owner_user_id=owner_user_id, persist=False)
    risk = build_collection_risk(session, owner_user_id=owner_user_id, persist=False)
    current = forecast.current_value
    st = scenario_type.strip().upper()
    cash = 0.0
    projected = current
    risk_delta = 0.0
    roi = 0.0
    affected: list[dict] = []
    explanation = ""

    if st == "SELL_DUPLICATES":
        queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=30, offset=0, refresh_upstream=False)
        dupes = [i for i in queue.items if i.owned_copies > i.target_hold_copies][:10]
        cash = sum(i.fmv for i in dupes)
        projected = current - cash * 0.15
        risk_delta = -8.0
        roi = 12.0
        affected = [{"title": i.title, "copies": i.owned_copies} for i in dupes]
        explanation = "Sell duplicate copies above hold targets to raise cash and reduce concentration risk."
    elif st == "GRADE_TOP_CANDIDATES":
        queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=20, offset=0, refresh_upstream=False)
        picks = sorted(queue.items, key=lambda x: x.fmv, reverse=True)[:5]
        projected = current * 1.06
        roi = 18.0
        affected = [{"title": i.title, "fmv": i.fmv} for i in picks]
        explanation = "Grade top FMV raw copies to capture grading upside."
    elif st == "MARKET_DROP":
        projected = current * 0.92
        risk_delta = 12.0
        explanation = "Simulated 8% market decline across liquid holdings."
    elif st == "MARKET_GAIN":
        projected = current * 1.1
        risk_delta = -5.0
        roi = 10.0
        explanation = "Simulated 10% market appreciation scenario."
    elif st == "LIQUIDATE_SELL_QUEUE":
        queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=50, offset=0, refresh_upstream=False)
        high = [i for i in queue.items if i.priority == "HIGH"]
        cash = sum(i.fmv for i in high)
        projected = current - cash * 0.2
        risk_delta = -15.0
        affected = [{"title": i.title} for i in high[:12]]
        explanation = "Liquidate high-priority sell queue candidates."
    else:
        explanation = "Unknown scenario."

    row = CollectionScenarioRun(
        owner_user_id=owner_user_id,
        scenario_type=st,
        projected_value=round(projected, 2),
        cash_generated=round(cash, 2),
        risk_change=round(risk_delta, 1),
        roi_impact=round(roi, 1),
        affected_books_json=affected,
        explanation=explanation,
        result_json={"baseline_risk": risk.risk_score},
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return CollectionScenarioRead(
        id=int(row.id or 0),
        scenario_type=st,
        projected_value=float(row.projected_value),
        cash_generated=float(row.cash_generated),
        risk_change=float(row.risk_change),
        roi_impact=float(row.roi_impact),
        affected_books=affected,
        explanation=explanation,
    )
