"""P63-03 Acquisition Opportunity Intelligence (persisted snapshots)."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.market_intelligence_platform import (
    ACQ_ACTION_BUY_NOW,
    ACQ_ACTION_PASS,
    ACQ_ACTION_WAIT,
    ACQ_ACTION_WATCH_PRICE,
    ACQ_ACTION_WANT_LIST,
    ACQ_STATUS_NEW,
    AcquisitionOpportunityItem,
    AcquisitionOpportunitySnapshot,
    utc_now,
)
from app.models.want_list import WantListItem
from app.services.acquisition_opportunity_engine import WANT_LIST_ACTIVE_STATUSES, _estimate_fmv, _build_fmv_index
from app.services.collector_intelligence_scoring import issue_intelligence_scores
from app.services.release_horizon_engine import list_issues_in_horizon_window
from app.services.market_intelligence_inventory import load_owner_inventory_rows


def get_latest_acquisition_snapshot(session: Session, *, owner_user_id: int) -> AcquisitionOpportunitySnapshot | None:
    return session.exec(
        select(AcquisitionOpportunitySnapshot)
        .where(AcquisitionOpportunitySnapshot.owner_user_id == owner_user_id)
        .order_by(
            AcquisitionOpportunitySnapshot.generated_at.desc(),
            AcquisitionOpportunitySnapshot.id.desc(),
        )
    ).first()


def list_acquisition_items(
    session: Session,
    *,
    snapshot_id: int,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[AcquisitionOpportunityItem], int]:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    rows = session.exec(
        select(AcquisitionOpportunityItem)
        .where(AcquisitionOpportunityItem.snapshot_id == snapshot_id)
        .order_by(AcquisitionOpportunityItem.opportunity_score.desc(), AcquisitionOpportunityItem.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = len(session.exec(select(AcquisitionOpportunityItem).where(AcquisitionOpportunityItem.snapshot_id == snapshot_id)).all())
    return rows, total


def update_acquisition_item_status(
    session: Session,
    *,
    item_id: int,
    owner_user_id: int,
    status: str,
) -> AcquisitionOpportunityItem:
    row = session.get(AcquisitionOpportunityItem, item_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("acquisition_item_not_found")
    row.status = status.strip().upper()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _owned_keys(session: Session, *, owner_user_id: int) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in load_owner_inventory_rows(session, owner_user_id=owner_user_id):
        keys.add((row.publisher.lower(), row.title.lower(), row.issue_number.lower()))
    return keys


def build_acquisition_opportunities(session: Session, *, owner_user_id: int) -> AcquisitionOpportunitySnapshot:
    today = date.today()
    snap = AcquisitionOpportunitySnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        metadata_json={},
    )
    session.add(snap)
    session.flush()

    owned = _owned_keys(session, owner_user_id=owner_user_id)
    exact_fmv, series_fmv = _build_fmv_index(session, owner_user_id=owner_user_id)
    candidates: list[tuple[float, AcquisitionOpportunityItem]] = []

    want_rows = session.exec(
        select(WantListItem).where(
            WantListItem.owner_user_id == owner_user_id,
            WantListItem.status.in_(list(WANT_LIST_ACTIVE_STATUSES)),  # type: ignore[attr-defined]
        )
    ).all()
    for want in want_rows:
        est = _estimate_fmv(
            publisher=want.publisher or "",
            series_name=want.series_name or "",
            issue_number=want.issue_number or "",
            exact_index=exact_fmv,
            series_index=series_fmv,
        )
        target = round(est * 0.8, 2) if est else None
        score = 70.0 if (want.priority or "").upper() == "HIGH" else 58.0
        action = ACQ_ACTION_BUY_NOW if score >= 70 else ACQ_ACTION_WATCH_PRICE
        candidates.append(
            (
                score,
                AcquisitionOpportunityItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    title=f"{want.series_name} #{want.issue_number}",
                    publisher=want.publisher or "",
                    issue_number=want.issue_number or "",
                    opportunity_score=score,
                    demand_score=55.0,
                    velocity_score=50.0,
                    spec_score=50.0,
                    recommendation_score=score,
                    estimated_market_price=est,
                    target_buy_price=target,
                    reason="want_list_active",
                    action=action,
                    status=ACQ_STATUS_NEW,
                ),
            )
        )

    horizon = list_issues_in_horizon_window(session, owner_user_id=owner_user_id, max_release_days=90)
    issue_ids = [int(issue.id or 0) for issue, _ in horizon if issue.id]
    scores = issue_intelligence_scores(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    for issue, series in horizon:
        iid = int(issue.id or 0)
        key = (series.publisher.lower(), series.series_name.lower(), (issue.issue_number or "").lower())
        if key in owned:
            continue
        s = scores.get(iid, {})
        opp = round(
            float(s.get("recommendation_score", 50)) * 0.35
            + float(s.get("demand_score", 50)) * 0.25
            + float(s.get("velocity_score", 50)) * 0.2
            + float(s.get("spec_score", 50)) * 0.2,
            2,
        )
        if opp < 52:
            continue
        action = ACQ_ACTION_BUY_NOW if opp >= 75 else ACQ_ACTION_WAIT if opp >= 60 else ACQ_ACTION_WATCH_PRICE
        reason = "missing_run_issue"
        if float(s.get("spec_score", 50)) >= 70:
            reason = "spec_opportunity"
        elif float(s.get("velocity_score", 50)) >= 65:
            reason = "demand_rising"
        candidates.append(
            (
                opp,
                AcquisitionOpportunityItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    release_issue_id=iid,
                    title=issue.title or f"{series.series_name} #{issue.issue_number}",
                    publisher=series.publisher,
                    issue_number=issue.issue_number or "",
                    opportunity_score=opp,
                    demand_score=float(s.get("demand_score", 50)),
                    velocity_score=float(s.get("velocity_score", 50)),
                    spec_score=float(s.get("spec_score", 50)),
                    recommendation_score=float(s.get("recommendation_score", 50)),
                    reason=reason,
                    action=action,
                    status=ACQ_STATUS_NEW,
                ),
            )
        )

    candidates.sort(key=lambda t: (-t[0], t[1].title))
    high = watch = 0
    for _, item in candidates[:75]:
        if item.opportunity_score >= 70:
            high += 1
        elif item.action in (ACQ_ACTION_WATCH_PRICE, ACQ_ACTION_WANT_LIST):
            watch += 1
        session.add(item)

    snap.total_items = min(len(candidates), 75)
    snap.high_priority_count = high
    snap.watch_count = watch
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
