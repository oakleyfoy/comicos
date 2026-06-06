"""P74-02 FOC watch and purchase recommendation intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.p70_market_refresh import P70MarketFmvTrendPoint
from app.models.p74_foc_purchase import (
    P74FocAlert,
    P74FocRecommendationSnapshot,
    P74PurchaseRecommendation,
    P74RecommendationChangeEvent,
)
from app.models.pull_list import PullList, PullListIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import CollectionRun
from app.schemas.release_foc_purchase import (
    P74FocAlertSummaryRead,
    P74FocDashboardRead,
    P74FocWatchRead,
    P74PurchaseRecommendationChangeRead,
    P74PurchaseRecommendationRead,
)
from app.services.collector_intelligence_scoring import issue_intelligence_scores
from app.services.purchase_priority_score import (
    P74_ACTION_BUY,
    P74_ACTION_MUST_BUY,
    P74_ACTION_PASS,
    P74_ACTION_WATCH,
    compute_purchase_priority_score,
)
from app.services.quantity_recommendation_service import recommend_quantity
from app.services.recommendation_v3_scoring_context import build_recommendation_v3_scoring_context
from app.services.release_watchlists import list_watchlist_matches

FOC_THIS_WEEK = "FOC_THIS_WEEK"
FOC_NEXT_WEEK = "FOC_NEXT_WEEK"
FOC_WITHIN_30 = "FOC_WITHIN_30_DAYS"
FOC_MISSED = "FOC_MISSED"
FOC_UNKNOWN = "FOC_UNKNOWN"

CHANGE_UPGRADED = "UPGRADED"
CHANGE_DOWNGRADED = "DOWNGRADED"
CHANGE_UNCHANGED = "UNCHANGED"
CHANGE_NEW = "NEW"

ACTION_RANK = {P74_ACTION_PASS: 0, P74_ACTION_WATCH: 1, P74_ACTION_BUY: 2, P74_ACTION_MUST_BUY: 3}


def _foc_bucket(foc_date: date | None, *, today: date) -> str:
    if foc_date is None:
        return FOC_UNKNOWN
    days = (foc_date - today).days
    if days < 0:
        return FOC_MISSED
    if days <= 7:
        return FOC_THIS_WEEK
    if days <= 14:
        return FOC_NEXT_WEEK
    if days <= 30:
        return FOC_WITHIN_30
    return FOC_UNKNOWN


def _market_strength(session: Session, owner_user_id: int) -> float:
    count = len(
        session.exec(
            select(P70MarketFmvTrendPoint.id).where(P70MarketFmvTrendPoint.owner_user_id == owner_user_id).limit(50)
        ).all()
    )
    return min(100.0, float(count * 2))


def _owned_quantity(session: Session, owner_user_id: int, series_name: str) -> int:
    runs = session.exec(
        select(CollectionRun)
        .where(CollectionRun.owner_user_id == owner_user_id)
        .where(CollectionRun.series_name == series_name)
        .limit(1)
    ).first()
    if runs is None:
        return 0
    return min(20, int(runs.issue_count_owned or 0))


def _ordered_quantity(session: Session, owner_user_id: int, release_id: int) -> int:
    lists = session.exec(select(PullList.id).where(PullList.owner_user_id == owner_user_id)).all()
    if not lists:
        return 0
    rows = session.exec(
        select(PullListIssue)
        .where(PullListIssue.pull_list_id.in_(lists))
        .where(PullListIssue.release_id == release_id)
    ).all()
    return len(rows)


def _watchlist_match(session: Session, owner_user_id: int, release_id: int) -> bool:
    matches = list_watchlist_matches(session, owner_user_id=owner_user_id, limit=500)
    return any(m.release_issue.id == release_id for m in matches)


def _latest_recommendations_by_issue(
    session: Session, owner_user_id: int
) -> dict[int, P74PurchaseRecommendation]:
    rows = session.exec(
        select(P74PurchaseRecommendation)
        .where(P74PurchaseRecommendation.owner_user_id == owner_user_id)
        .order_by(P74PurchaseRecommendation.generated_at.desc(), P74PurchaseRecommendation.id.desc())
    ).all()
    latest: dict[int, P74PurchaseRecommendation] = {}
    for row in rows:
        rid = int(row.release_issue_id)
        if rid not in latest:
            latest[rid] = row
    return latest


def _classify_change(
    prev: P74PurchaseRecommendation | None,
    *,
    current_action: str,
    current_qty: int,
    reason: str,
) -> P74RecommendationChangeEvent | None:
    if prev is None:
        return P74RecommendationChangeEvent(
            owner_user_id=0,
            release_issue_id=0,
            change_kind=CHANGE_NEW,
            previous_action="",
            current_action=current_action,
            previous_quantity=0,
            current_quantity=current_qty,
            reason=reason or "Initial P74-02 recommendation.",
        )
    pa, ca = prev.purchase_action, current_action
    pq, cq = prev.quantity_recommended, current_qty
    if pa == ca and pq == cq:
        kind = CHANGE_UNCHANGED
    elif ACTION_RANK.get(ca, 0) > ACTION_RANK.get(pa, 0) or cq > pq:
        kind = CHANGE_UPGRADED
    elif ACTION_RANK.get(ca, 0) < ACTION_RANK.get(pa, 0) or cq < pq:
        kind = CHANGE_DOWNGRADED
    else:
        kind = CHANGE_UNCHANGED
    if kind == CHANGE_UNCHANGED:
        return None
    return P74RecommendationChangeEvent(
        owner_user_id=0,
        release_issue_id=0,
        change_kind=kind,
        previous_action=pa,
        current_action=ca,
        previous_quantity=pq,
        current_quantity=cq,
        reason=reason,
    )


def generate_foc_purchase_snapshot(session: Session, *, owner_user_id: int) -> P74FocRecommendationSnapshot:
    today = date.today()
    rows = list(
        session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    )
    buckets = {FOC_THIS_WEEK: 0, FOC_NEXT_WEEK: 0, FOC_WITHIN_30: 0, FOC_MISSED: 0, FOC_UNKNOWN: 0}
    for issue, _ in rows:
        buckets[_foc_bucket(issue.foc_date, today=today)] += 1

    prev_latest = _latest_recommendations_by_issue(session, owner_user_id)
    issue_ids = [int(i.id or 0) for i, _ in rows]
    v3_ctx = build_recommendation_v3_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    scores = issue_intelligence_scores(session, owner_user_id=owner_user_id, issue_ids=issue_ids, v3_ctx=v3_ctx)
    market = _market_strength(session, owner_user_id)

    snap = P74FocRecommendationSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        foc_this_week=buckets[FOC_THIS_WEEK],
        foc_next_week=buckets[FOC_NEXT_WEEK],
        foc_within_30_days=buckets[FOC_WITHIN_30],
        foc_missed=buckets[FOC_MISSED],
        foc_unknown=buckets[FOC_UNKNOWN],
    )
    session.add(snap)
    session.flush()
    snap_id = int(snap.id or 0)

    key_signals = {
        int(s.issue_id)
        for s in session.exec(
            select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)
        ).all()
    }

    for issue, series in rows:
        iid = int(issue.id or 0)
        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == iid)).all()
        has_ratio = any(v.ratio_value for v in variants)
        foc_days = (issue.foc_date - today).days if issue.foc_date else None
        s = scores.get(iid, {})
        rec_score = float(s.get("recommendation_score", 50.0))
        demand = float(s.get("demand_score", 50.0))
        owned = _owned_quantity(session, owner_user_id, series.series_name)
        ordered = _ordered_quantity(session, owner_user_id, iid)
        wl = _watchlist_match(session, owner_user_id, iid)
        is_one = issue.issue_number.strip().lstrip("#") == "1"
        priority, action = compute_purchase_priority_score(
            recommendation_score=rec_score,
            demand_score=demand,
            is_number_one=is_one,
            is_key_signal=iid in key_signals,
            variant_count=len(variants),
            has_ratio_variant=has_ratio,
            watchlist_match=wl,
            market_signal_strength=market,
            owned_quantity=owned,
            ordered_quantity=ordered,
            foc_days=foc_days,
        )
        qty, qty_reason = recommend_quantity(
            purchase_action=action,
            priority_score=priority,
            owned_quantity=owned,
            ordered_quantity=ordered,
            is_number_one=is_one,
            demand_score=demand,
            foc_days=foc_days,
        )
        bucket = _foc_bucket(issue.foc_date, today=today)
        reasoning = qty_reason
        row = P74PurchaseRecommendation(
            owner_user_id=owner_user_id,
            snapshot_id=snap_id,
            release_issue_id=iid,
            publisher=series.publisher,
            series_name=series.series_name,
            issue_number=issue.issue_number,
            foc_date=issue.foc_date,
            release_date=issue.release_date,
            foc_bucket=bucket,
            priority_score=priority,
            purchase_action=action,
            quantity_recommended=qty,
            owned_quantity=owned,
            ordered_quantity=ordered,
            watchlist_match=wl,
            reasoning=reasoning,
            scores_json={"recommendation_score": rec_score, "demand_score": demand},
        )
        session.add(row)
        session.flush()

        change = _classify_change(
            prev_latest.get(iid),
            current_action=action,
            current_qty=qty,
            reason=reasoning,
        )
        if change is not None:
            change.owner_user_id = owner_user_id
            change.release_issue_id = iid
            session.add(change)

        if bucket == FOC_THIS_WEEK and action in {P74_ACTION_BUY, P74_ACTION_MUST_BUY}:
            session.add(
                P74FocAlert(
                    owner_user_id=owner_user_id,
                    snapshot_id=snap_id,
                    release_issue_id=iid,
                    alert_type="FOC_THIS_WEEK",
                    title=f"{series.series_name} #{issue.issue_number}",
                    message=f"FOC this week — {action} qty {qty}",
                    priority_score=priority,
                )
            )
        if bucket == FOC_MISSED:
            session.add(
                P74FocAlert(
                    owner_user_id=owner_user_id,
                    snapshot_id=snap_id,
                    release_issue_id=iid,
                    alert_type="MISSED_FOC",
                    title=f"{series.series_name} #{issue.issue_number}",
                    message="FOC date has passed.",
                    priority_score=priority,
                )
            )

    session.commit()
    session.refresh(snap)
    return snap


def build_foc_watch(session: Session, *, owner_user_id: int) -> P74FocWatchRead:
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc())
        .limit(1)
    ).first()
    if snap is None:
        snap = generate_foc_purchase_snapshot(session, owner_user_id=owner_user_id)
    return P74FocWatchRead(
        snapshot_id=int(snap.id or 0),
        foc_this_week=snap.foc_this_week,
        foc_next_week=snap.foc_next_week,
        foc_within_30_days=snap.foc_within_30_days,
        foc_missed=snap.foc_missed,
        foc_unknown=snap.foc_unknown,
    )


def list_purchase_recommendations(
    session: Session, *, owner_user_id: int, limit: int = 50
) -> list[P74PurchaseRecommendationRead]:
    snap = session.exec(
        select(P74FocRecommendationSnapshot)
        .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P74FocRecommendationSnapshot.generated_at.desc())
        .limit(1)
    ).first()
    if snap is None:
        generate_foc_purchase_snapshot(session, owner_user_id=owner_user_id)
        snap = session.exec(
            select(P74FocRecommendationSnapshot)
            .where(P74FocRecommendationSnapshot.owner_user_id == owner_user_id)
            .order_by(P74FocRecommendationSnapshot.generated_at.desc())
            .limit(1)
        ).first()
    assert snap is not None
    rows = session.exec(
        select(P74PurchaseRecommendation)
        .where(P74PurchaseRecommendation.snapshot_id == int(snap.id or 0))
        .order_by(P74PurchaseRecommendation.priority_score.desc(), P74PurchaseRecommendation.id.asc())
        .limit(limit)
    ).all()
    return [P74PurchaseRecommendationRead.model_validate(r) for r in rows]


def list_recommendation_changes(
    session: Session, *, owner_user_id: int, limit: int = 50
) -> list[P74PurchaseRecommendationChangeRead]:
    rows = session.exec(
        select(P74RecommendationChangeEvent)
        .where(P74RecommendationChangeEvent.owner_user_id == owner_user_id)
        .where(P74RecommendationChangeEvent.change_kind != CHANGE_UNCHANGED)
        .order_by(P74RecommendationChangeEvent.created_at.desc(), P74RecommendationChangeEvent.id.desc())
        .limit(limit)
    ).all()
    return [P74PurchaseRecommendationChangeRead.model_validate(r) for r in rows]


def build_foc_dashboard(session: Session, *, owner_user_id: int) -> P74FocDashboardRead:
    snap = generate_foc_purchase_snapshot(session, owner_user_id=owner_user_id)
    recs = list_purchase_recommendations(session, owner_user_id=owner_user_id, limit=100)
    changes = list_recommendation_changes(session, owner_user_id=owner_user_id, limit=50)
    alerts = session.exec(
        select(P74FocAlert)
        .where(P74FocAlert.snapshot_id == int(snap.id or 0))
        .order_by(P74FocAlert.priority_score.desc())
    ).all()
    this_week = [r for r in recs if r.foc_bucket == FOC_THIS_WEEK]
    upgrades = [c for c in changes if c.change_kind == CHANGE_UPGRADED]
    downgrades = [c for c in changes if c.change_kind == CHANGE_DOWNGRADED]
    missed = [r for r in recs if r.foc_bucket == FOC_MISSED]
    watchlist = [r for r in recs if r.watchlist_match]
    last_chance = [r for r in recs if r.foc_bucket == FOC_THIS_WEEK and r.priority_score >= 70]
    return P74FocDashboardRead(
        snapshot_id=int(snap.id or 0),
        generated_at=snap.generated_at,
        foc_watch=build_foc_watch(session, owner_user_id=owner_user_id),
        foc_this_week=this_week,
        last_chance=last_chance,
        recommended_preorders=[r for r in recs if r.purchase_action in {P74_ACTION_BUY, P74_ACTION_MUST_BUY}],
        quantity_changes=[c for c in changes if c.previous_quantity != c.current_quantity],
        recommendation_upgrades=upgrades,
        recommendation_downgrades=downgrades,
        missed_foc=missed,
        watchlist_matches=watchlist,
        alerts=[
            P74FocAlertSummaryRead(alert_type=a.alert_type, title=a.title, message=a.message) for a in alerts
        ],
    )
