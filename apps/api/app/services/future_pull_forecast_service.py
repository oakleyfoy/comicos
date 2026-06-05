"""P62-04 Future Pull Forecasting."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.buy_queue_intelligence import BuyQueueItem, BuyQueueSnapshot
from app.models.collector_intelligence import (
    FORECAST_CONF_HIGH,
    FORECAST_CONF_LOW,
    FORECAST_CONF_MEDIUM,
    FuturePullForecast,
    FuturePullForecastItem,
    utc_now,
)
from app.models.pull_list import PullList
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.collector_intelligence_scoring import issue_intelligence_scores
from app.services.release_horizon_engine import list_issues_in_horizon_window


def _latest_buy_queue_items(session: Session, *, owner_user_id: int) -> list[BuyQueueItem]:
    snap = session.exec(
        select(BuyQueueSnapshot)
        .where(BuyQueueSnapshot.owner_user_id == owner_user_id)
        .order_by(BuyQueueSnapshot.id.desc())
    ).first()
    if snap is None or snap.id is None:
        return []
    return list(session.exec(select(BuyQueueItem).where(BuyQueueItem.snapshot_id == int(snap.id))).all())


def generate_future_pull_forecast(session: Session, *, owner_user_id: int) -> FuturePullForecast:
    today = date.today()
    pull_rows = session.exec(select(PullList).where(PullList.owner_user_id == owner_user_id)).all()
    pull_series = {p.series_name.lower() for p in pull_rows}
    pull_publishers = Counter(p.publisher.lower() for p in pull_rows if p.status == "ACTIVE")
    bq_items = _latest_buy_queue_items(session, owner_user_id=owner_user_id)
    bq_series = set()
    for item in bq_items:
        if item.release_issue_id:
            bq_series.add(item.title.split("#")[0].strip().lower())

    horizon = list_issues_in_horizon_window(session, owner_user_id=owner_user_id, max_release_days=90)
    issue_ids = [int(i.id or 0) for i, _ in horizon if i.id]
    scores = issue_intelligence_scores(session, owner_user_id=owner_user_id, issue_ids=issue_ids)

    entries: list[tuple[str, str, int | None, str, str, dict]] = []
    seen_series: set[str] = set()

    for issue, series in horizon:
        key = series.series_name.lower()
        if key in seen_series:
            continue
        seen_series.add(key)
        iid = int(issue.id or 0)
        s = scores.get(iid, {})
        reasons: list[str] = []
        confidence = FORECAST_CONF_LOW
        if key in pull_series:
            reasons.append("ongoing_run")
            confidence = FORECAST_CONF_HIGH
        elif series.publisher.lower() in pull_publishers:
            reasons.append("publisher_following")
            confidence = FORECAST_CONF_MEDIUM if confidence == FORECAST_CONF_LOW else confidence
        if any(key in bq for bq in bq_series):
            reasons.append("buy_queue_interest")
            confidence = FORECAST_CONF_HIGH if confidence != FORECAST_CONF_HIGH else confidence
        if float(s.get("velocity_score", 50)) >= 65:
            reasons.append("demand_trend")
            if confidence == FORECAST_CONF_LOW:
                confidence = FORECAST_CONF_MEDIUM
        if float(s.get("user_preference_score", 50)) >= 68:
            reasons.append("similar_ownership")
            if confidence == FORECAST_CONF_LOW:
                confidence = FORECAST_CONF_MEDIUM
        if not reasons:
            reasons.append("forward_catalog")
        explanation = ", ".join(reasons)
        entries.append(
            (
                series.series_name,
                issue.title or series.series_name,
                iid if iid > 0 else None,
                confidence,
                explanation,
                {"reasons": reasons, "demand_score": s.get("demand_score", 50)},
            )
        )

    entries.sort(key=lambda e: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[e[3]], e[0]))

    forecast = FuturePullForecast(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        total_items=len(entries),
        metadata_json={"horizon_days": 90},
    )
    session.add(forecast)
    session.flush()
    fid = int(forecast.id or 0)
    for series_name, title, rid, conf, expl, rjson in entries[:200]:
        session.add(
            FuturePullForecastItem(
                forecast_id=fid,
                owner_user_id=owner_user_id,
                release_issue_id=rid,
                series_name=series_name,
                title=title,
                confidence=conf,
                explanation=expl,
                reasons_json=rjson,
            )
        )
    session.commit()
    session.refresh(forecast)
    return forecast


def get_latest_pull_forecast(session: Session, *, owner_user_id: int) -> FuturePullForecast | None:
    return session.exec(
        select(FuturePullForecast)
        .where(FuturePullForecast.owner_user_id == owner_user_id)
        .order_by(FuturePullForecast.id.desc())
    ).first()


def list_forecast_items(
    session: Session, *, forecast_id: int, limit: int = 100, offset: int = 0
) -> tuple[list[FuturePullForecastItem], int]:
    rows = session.exec(
        select(FuturePullForecastItem)
        .where(FuturePullForecastItem.forecast_id == forecast_id)
        .order_by(FuturePullForecastItem.confidence.asc(), FuturePullForecastItem.id.asc())
    ).all()
    total = len(rows)
    return rows[offset : offset + limit], total
