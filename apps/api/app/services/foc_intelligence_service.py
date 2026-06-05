"""P62-03 FOC Intelligence."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.collector_intelligence import (
    FOC_STATUS_DISMISSED,
    FOC_STATUS_NEW,
    FOCAlertItem,
    FOCAlertSnapshot,
    utc_now,
)
from app.models.demand_intelligence import TREND_RISING
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.collector_intelligence_scoring import issue_intelligence_scores
from app.services.recommendation_v3_scoring_context import build_recommendation_v3_scoring_context


def _days_until(d: date | None, *, today: date) -> int | None:
    if d is None:
        return None
    return (d - today).days


def generate_foc_alerts(
    session: Session,
    *,
    owner_user_id: int,
    window_days: int = 30,
) -> FOCAlertSnapshot:
    today = date.today()
    cutoff = today + timedelta(days=window_days)
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    candidates: list[tuple[ReleaseIssue, ReleaseSeries, int, dict[str, float]]] = []
    issue_ids: list[int] = []
    for issue, series in rows:
        if issue.foc_date is None:
            continue
        if issue.foc_date < today or issue.foc_date > cutoff:
            continue
        iid = int(issue.id or 0)
        issue_ids.append(iid)
        candidates.append((issue, series, iid, {}))

    v3_ctx = build_recommendation_v3_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    scores = issue_intelligence_scores(session, owner_user_id=owner_user_id, issue_ids=issue_ids, v3_ctx=v3_ctx)

    scored: list[tuple[ReleaseIssue, ReleaseSeries, float, str, int, dict]] = []
    for issue, series, iid, _ in candidates:
        s = scores.get(iid, {})
        rec = float(s.get("recommendation_score", 50.0))
        demand = float(s.get("demand_score", 50.0))
        velocity = float(s.get("velocity_score", 50.0))
        spec = float(s.get("spec_score", 50.0))
        pref = float(s.get("user_preference_score", 50.0))
        foc_days = _days_until(issue.foc_date, today=today) or 99
        urgency = round(
            rec * 0.28 + demand * 0.22 + velocity * 0.18 + spec * 0.12 + pref * 0.1 + max(0, 30 - foc_days) * 0.8,
            2,
        )
        vel_row = v3_ctx.velocity_for_issue(iid)
        reasons: list[str] = [f"foc_in_{foc_days}d"]
        if rec >= 70:
            reasons.append("high_v3")
        if demand >= 65:
            reasons.append("high_demand")
        if vel_row and vel_row.trend_label == TREND_RISING:
            reasons.append("rising_velocity")
            urgency = round(min(100.0, urgency + 5.0), 2)
        if spec >= 70:
            reasons.append("spec_opportunity")
        if pref >= 65:
            reasons.append("owner_preference")
        qty = 2 if urgency >= 80 else 1
        scored.append((issue, series, urgency, "; ".join(reasons), qty, s))

    scored.sort(key=lambda t: (-t[2], t[0].foc_date or date.max))

    snap = FOCAlertSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        total_items=len(scored),
        metadata_json={"window_days": window_days, "archived": False},
    )
    session.add(snap)
    session.flush()
    sid = int(snap.id or 0)
    for issue, series, urgency, reason, qty, s in scored:
        session.add(
            FOCAlertItem(
                snapshot_id=sid,
                owner_user_id=owner_user_id,
                release_issue_id=int(issue.id or 0),
                title=issue.title or f"{series.series_name} #{issue.issue_number}",
                publisher=series.publisher or "",
                foc_date=issue.foc_date,
                release_date=issue.release_date,
                recommendation_score=float(s.get("recommendation_score", 50.0)),
                demand_score=float(s.get("demand_score", 50.0)),
                velocity_score=float(s.get("velocity_score", 50.0)),
                spec_score=float(s.get("spec_score", 50.0)),
                urgency_score=urgency,
                alert_reason=reason,
                suggested_quantity=qty,
                status=FOC_STATUS_NEW,
            )
        )
    session.commit()
    session.refresh(snap)
    return snap


def get_latest_foc_snapshot(session: Session, *, owner_user_id: int) -> FOCAlertSnapshot | None:
    rows = session.exec(
        select(FOCAlertSnapshot)
        .where(FOCAlertSnapshot.owner_user_id == owner_user_id)
        .order_by(FOCAlertSnapshot.id.desc())
        .limit(10)
    ).all()
    for snap in rows:
        if not (snap.metadata_json or {}).get("archived"):
            return snap
    return None


def list_foc_items(session: Session, *, snapshot_id: int, limit: int = 100, offset: int = 0) -> tuple[list[FOCAlertItem], int]:
    rows = session.exec(
        select(FOCAlertItem)
        .where(FOCAlertItem.snapshot_id == snapshot_id)
        .order_by(FOCAlertItem.urgency_score.desc(), FOCAlertItem.id.asc())
    ).all()
    total = len(rows)
    return rows[offset : offset + limit], total


def archive_foc_snapshot(session: Session, *, snapshot_id: int, owner_user_id: int) -> FOCAlertSnapshot:
    snap = session.get(FOCAlertSnapshot, snapshot_id)
    if snap is None or snap.owner_user_id != owner_user_id:
        raise ValueError("FOC snapshot not found")
    snap.metadata_json = {**(snap.metadata_json or {}), "archived": True, "archived_at": utc_now().isoformat()}
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def update_foc_item_status(session: Session, *, item_id: int, owner_user_id: int, status: str) -> FOCAlertItem:
    allowed = {FOC_STATUS_NEW, "REVIEWED", "ORDERED", FOC_STATUS_DISMISSED}
    status_u = status.strip().upper()
    if status_u not in allowed:
        raise ValueError("Invalid FOC status")
    item = session.get(FOCAlertItem, item_id)
    if item is None or item.owner_user_id != owner_user_id:
        raise ValueError("FOC item not found")
    item.status = status_u
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
