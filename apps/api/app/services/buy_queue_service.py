"""P62-02 Buy Queue Intelligence service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from app.models.buy_queue_intelligence import (
    BUY_QUEUE_ITEM_BUY,
    BUY_QUEUE_ITEM_NEW,
    BUY_QUEUE_ITEM_SKIPPED,
    BUY_QUEUE_ITEM_WATCH,
    BuyQueueItem,
    BuyQueueSnapshot,
    utc_now,
)
from app.models.pull_list import PullList, PullListIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.cross_system_recommendation_engine import build_cross_system_candidates
from app.services.purchase_budgets import get_purchase_budget_row
from app.services.recommendation_catalog_quality import build_forward_release_title_index
from app.services.recommendation_title_index import resolve_release_pair
from app.services.recommendation_v2_scoring_context import build_recommendation_v2_scoring_context
from app.services.recommendation_v3_components import score_v3_demand_components
from app.services.recommendation_v3_scoring_context import build_recommendation_v3_scoring_context
from app.services.collector_display_identity import format_from_release
from app.services.release_horizon_engine import list_issues_in_horizon_window


@dataclass
class _ScoredQueueRow:
    issue: ReleaseIssue
    series: ReleaseSeries
    priority_score: float
    recommendation_score: float
    demand_score: float
    velocity_score: float
    spec_score: float
    user_preference_score: float
    buy_reason: str
    external_catalog_issue_id: int | None
    v2_priority: float


def _component_score(bundle, name: str) -> float:
    for comp in bundle.components:
        if comp.component_name == name:
            return float(comp.component_score)
    return 50.0


def _pull_list_release_ids(session: Session, *, owner_user_id: int) -> set[int]:
    lists = session.exec(select(PullList).where(PullList.owner_user_id == owner_user_id)).all()
    list_ids = [int(p.id or 0) for p in lists if p.id]
    if not list_ids:
        return set()
    rows = session.exec(select(PullListIssue).where(PullListIssue.pull_list_id.in_(list_ids))).all()
    return {int(r.release_id) for r in rows if r.release_id}


def _pull_series_keys(session: Session, *, owner_user_id: int) -> set[tuple[str, str]]:
    rows = session.exec(
        select(PullList).where(PullList.owner_user_id == owner_user_id, PullList.status == "ACTIVE")
    ).all()
    return {(r.publisher.lower(), r.series_name.lower()) for r in rows}


def _candidate_priority_by_issue(
    session: Session,
    *,
    owner_user_id: int,
    release_index: dict,
) -> dict[int, float]:
    candidates = build_cross_system_candidates(session, owner_user_id=owner_user_id, refresh_upstream=False)
    by_issue: dict[int, float] = {}
    for cand in candidates:
        pair = resolve_release_pair(cand.title, release_index)
        if pair is None or pair[0].id is None:
            continue
        iid = int(pair[0].id)
        by_issue[iid] = max(by_issue.get(iid, 0.0), float(cand.priority_score))
    return by_issue


def _score_queue_rows(
    session: Session,
    *,
    owner_user_id: int,
    horizon_days: int = 90,
) -> list[_ScoredQueueRow]:
    issues = list_issues_in_horizon_window(session, owner_user_id=owner_user_id, max_release_days=horizon_days)
    if not issues:
        return []
    issue_ids = [int(issue.id or 0) for issue, _ in issues if issue.id]
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    v2_by_issue = _candidate_priority_by_issue(session, owner_user_id=owner_user_id, release_index=release_index)
    v3_ctx = build_recommendation_v3_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    v2_ctx = build_recommendation_v2_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    pull_releases = _pull_list_release_ids(session, owner_user_id=owner_user_id)
    pull_series = _pull_series_keys(session, owner_user_id=owner_user_id)

    rows: list[_ScoredQueueRow] = []
    for issue, series in issues:
        iid = int(issue.id or 0)
        if iid <= 0:
            continue
        bundle = score_v3_demand_components(v3_ctx, release_issue_id=iid)
        demand_score = _component_score(bundle, "ISSUE_DEMAND_LEVEL_SCORE")
        velocity_score = _component_score(bundle, "DEMAND_VELOCITY_SCORE")
        spec_score = _component_score(bundle, "SPEC_OPPORTUNITY_SCORE")
        recommendation_score = float(bundle.preview_score)
        v2_priority = float(v2_by_issue.get(iid, 50.0))
        fit = v2_ctx.market_user_fit(session, issue=issue, series=series)
        user_pref = float(fit.get("user_preference_score") or 50.0)

        priority = round(
            recommendation_score * 0.45
            + v2_priority * 0.30
            + demand_score * 0.12
            + velocity_score * 0.08
            + spec_score * 0.05,
            2,
        )
        reasons: list[str] = [f"v3={recommendation_score:.1f}", f"v2={v2_priority:.1f}"]
        if user_pref >= 65:
            priority = round(min(100.0, priority + (user_pref - 50.0) * 0.15), 2)
            reasons.append("user_preference_fit")
        on_pull = iid in pull_releases or (
            series.publisher.lower(),
            series.series_name.lower(),
        ) in pull_series
        if on_pull:
            priority = round(min(100.0, priority + 4.0), 2)
            reasons.append("pull_list")

        demand_row = v3_ctx.demand_for_issue(iid)
        ext_id = int(demand_row.external_issue_id) if demand_row else v3_ctx.external_id_by_release_issue_id.get(iid)
        spec_row = v3_ctx.spec_for_issue(iid)
        if spec_row is not None:
            spec_score = float(spec_row.opportunity_score)
            reasons.append(f"spec_rank={spec_row.rank}")

        rows.append(
            _ScoredQueueRow(
                issue=issue,
                series=series,
                priority_score=priority,
                recommendation_score=recommendation_score,
                demand_score=demand_score,
                velocity_score=velocity_score,
                spec_score=spec_score,
                user_preference_score=user_pref,
                buy_reason="; ".join(reasons),
                external_catalog_issue_id=ext_id,
                v2_priority=v2_priority,
            )
        )
    rows.sort(key=lambda r: (-r.priority_score, r.issue.release_date or date.max, r.issue.title or ""))
    return rows


def _apply_budget(
    rows: list[_ScoredQueueRow],
    *,
    monthly_budget: float,
    weekly_budget: float,
    is_active: bool,
) -> list[tuple[_ScoredQueueRow, str, int, float]]:
    """Return row, status, quantity, estimated_cost."""
    if not is_active:
        budget_cap = 0.0
    else:
        budget_cap = weekly_budget if weekly_budget > 0 else monthly_budget

    output: list[tuple[_ScoredQueueRow, str, int, float]] = []
    spent = 0.0
    for row in rows:
        cover = float(row.issue.cover_price or 4.99)
        qty = 2 if row.priority_score >= 85 else 1
        cost = round(cover * qty, 2)
        status = BUY_QUEUE_ITEM_BUY if row.priority_score >= 72 else BUY_QUEUE_ITEM_NEW
        if row.priority_score < 55:
            status = BUY_QUEUE_ITEM_WATCH

        if budget_cap > 0 and spent + cost > budget_cap:
            status = BUY_QUEUE_ITEM_WATCH
            row = _ScoredQueueRow(
                issue=row.issue,
                series=row.series,
                priority_score=round(row.priority_score * 0.92, 2),
                recommendation_score=row.recommendation_score,
                demand_score=row.demand_score,
                velocity_score=row.velocity_score,
                spec_score=row.spec_score,
                user_preference_score=row.user_preference_score,
                buy_reason=f"{row.buy_reason}; budget_demoted",
                external_catalog_issue_id=row.external_catalog_issue_id,
                v2_priority=row.v2_priority,
            )
            qty = 1
            cost = round(cover * qty, 2)
        else:
            spent += cost

        output.append((row, status, qty, cost))
    return output


def build_buy_queue(
    session: Session,
    *,
    owner_user_id: int,
    horizon_days: int = 90,
) -> BuyQueueSnapshot:
    scored = _score_queue_rows(session, owner_user_id=owner_user_id, horizon_days=horizon_days)
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    budgeted = _apply_budget(
        scored,
        monthly_budget=float(budget.monthly_budget),
        weekly_budget=float(budget.weekly_budget),
        is_active=bool(budget.is_active),
    )

    today = date.today()
    snapshot = BuyQueueSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        total_items=len(budgeted),
        metadata_json={
            "horizon_days": horizon_days,
            "budget": {
                "monthly_budget": float(budget.monthly_budget),
                "weekly_budget": float(budget.weekly_budget),
                "is_active": bool(budget.is_active),
            },
            "archived": False,
        },
    )
    session.add(snapshot)
    session.flush()
    sid = int(snapshot.id or 0)

    for row, status, qty, cost in budgeted:
        issue = row.issue
        series = row.series
        session.add(
            BuyQueueItem(
                snapshot_id=sid,
                owner_user_id=owner_user_id,
                recommendation_id=None,
                release_issue_id=int(issue.id or 0),
                external_catalog_issue_id=row.external_catalog_issue_id,
                title=format_from_release(series=series, issue=issue),
                issue_number=str(issue.issue_number or ""),
                publisher=str(series.publisher or ""),
                priority_score=row.priority_score,
                recommendation_score=row.recommendation_score,
                demand_score=row.demand_score,
                velocity_score=row.velocity_score,
                spec_score=row.spec_score,
                buy_reason=row.buy_reason,
                quantity_recommended=qty,
                estimated_cost=cost,
                foc_date=issue.foc_date,
                release_date=issue.release_date,
                status=status,
            )
        )
    session.commit()
    session.refresh(snapshot)
    return snapshot


def rebuild_buy_queue(session: Session, *, owner_user_id: int, horizon_days: int = 90) -> BuyQueueSnapshot:
    return build_buy_queue(session, owner_user_id=owner_user_id, horizon_days=horizon_days)


def _is_archived(snapshot: BuyQueueSnapshot) -> bool:
    return bool((snapshot.metadata_json or {}).get("archived"))


def get_latest_buy_queue_snapshot(session: Session, *, owner_user_id: int) -> BuyQueueSnapshot | None:
    rows = session.exec(
        select(BuyQueueSnapshot)
        .where(BuyQueueSnapshot.owner_user_id == owner_user_id)
        .order_by(BuyQueueSnapshot.id.desc())
        .limit(20)
    ).all()
    for snap in rows:
        if not _is_archived(snap):
            return snap
    return None


def get_latest_buy_queue_snapshot_including_archived(session: Session, *, owner_user_id: int) -> BuyQueueSnapshot | None:
    return session.exec(
        select(BuyQueueSnapshot)
        .where(BuyQueueSnapshot.owner_user_id == owner_user_id)
        .order_by(BuyQueueSnapshot.id.desc())
    ).first()


def list_buy_queue_items(
    session: Session,
    *,
    snapshot_id: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[BuyQueueItem], int]:
    rows = session.exec(
        select(BuyQueueItem)
        .where(BuyQueueItem.snapshot_id == snapshot_id)
        .order_by(BuyQueueItem.priority_score.desc(), BuyQueueItem.id.asc())
    ).all()
    total = len(rows)
    return rows[offset : offset + limit], total


def archive_buy_queue_snapshot(session: Session, *, snapshot_id: int, owner_user_id: int) -> BuyQueueSnapshot:
    snap = session.get(BuyQueueSnapshot, snapshot_id)
    if snap is None or snap.owner_user_id != owner_user_id:
        raise ValueError("Buy queue snapshot not found")
    snap.metadata_json = {**(snap.metadata_json or {}), "archived": True, "archived_at": utc_now().isoformat()}
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def update_buy_queue_item_status(
    session: Session,
    *,
    item_id: int,
    owner_user_id: int,
    status: str,
) -> BuyQueueItem:
    from app.models.buy_queue_intelligence import BUY_QUEUE_ITEM_STATUSES

    status_u = status.strip().upper()
    if status_u not in BUY_QUEUE_ITEM_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    item = session.get(BuyQueueItem, item_id)
    if item is None or item.owner_user_id != owner_user_id:
        raise ValueError("Buy queue item not found")
    item.status = status_u
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
