"""P62-05 Auto Watchlists."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.collector_intelligence import AUTO_WL_TYPES, AutoWatchlist, AutoWatchlistItem, utc_now
from app.models.demand_intelligence import TREND_RISING
from app.models.pull_list import PullList
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_v3_scoring_context import build_recommendation_v3_scoring_context
from app.services.spec_opportunity_service import get_latest_spec_snapshot, list_spec_opportunity_rows


def _next_epoch(session: Session, *, owner_user_id: int, watchlist_type: str) -> int:
    row = session.exec(
        select(AutoWatchlist)
        .where(AutoWatchlist.owner_user_id == owner_user_id, AutoWatchlist.watchlist_type == watchlist_type)
        .order_by(AutoWatchlist.generation_epoch.desc())
    ).first()
    return int((row.generation_epoch if row else 0) + 1)


def _mark_stale_archived(session: Session, *, owner_user_id: int, watchlist_type: str) -> None:
    rows = session.exec(
        select(AutoWatchlist).where(
            AutoWatchlist.owner_user_id == owner_user_id,
            AutoWatchlist.watchlist_type == watchlist_type,
        )
    ).all()
    for row in rows:
        if not (row.metadata_json or {}).get("archived"):
            row.metadata_json = {**(row.metadata_json or {}), "archived": True, "archived_at": utc_now().isoformat()}
            session.add(row)


def _build_one(
    session: Session,
    *,
    owner_user_id: int,
    watchlist_type: str,
    items: list[tuple[int | None, str, str]],
) -> AutoWatchlist:
    _mark_stale_archived(session, owner_user_id=owner_user_id, watchlist_type=watchlist_type)
    epoch = _next_epoch(session, owner_user_id=owner_user_id, watchlist_type=watchlist_type)
    wl = AutoWatchlist(
        owner_user_id=owner_user_id,
        watchlist_type=watchlist_type,
        generation_epoch=epoch,
        item_count=len(items),
        metadata_json={"archived": False},
    )
    session.add(wl)
    session.flush()
    wid = int(wl.id or 0)
    for rid, title, reason in items:
        session.add(
            AutoWatchlistItem(
                watchlist_id=wid,
                owner_user_id=owner_user_id,
                release_issue_id=rid,
                title=title,
                inclusion_reason=reason,
                metadata_json={"watchlist_type": watchlist_type},
            )
        )
    session.refresh(wl)
    return wl


def build_auto_watchlists(session: Session, *, owner_user_id: int) -> list[AutoWatchlist]:
    today = date.today()
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    issue_ids = [int(i.id or 0) for i, _ in rows if i.id]
    v3_ctx = build_recommendation_v3_scoring_context(session, owner_user_id=owner_user_id, issue_ids=issue_ids)

    spec_rows, _ = list_spec_opportunity_rows(session, owner_user_id=owner_user_id, limit=50, offset=0)
    spec_issue_ids = {int(r.release_issue_id) for r in spec_rows}

    pull_pubs = Counter(
        p.publisher.lower()
        for p in session.exec(select(PullList).where(PullList.owner_user_id == owner_user_id)).all()
        if p.status == "ACTIVE"
    )
    top_publishers = {p for p, _ in pull_pubs.most_common(3)}

    built: list[AutoWatchlist] = []
    type_items: dict[str, list[tuple[int | None, str, str]]] = {t: [] for t in AUTO_WL_TYPES}

    for issue, series in rows:
        iid = int(issue.id or 0)
        title = issue.title or f"{series.series_name} #{issue.issue_number}"
        blob = f"{series.series_name} {issue.title}".lower()
        vel = v3_ctx.velocity_for_issue(iid)
        foc_days = (issue.foc_date - today).days if issue.foc_date else None

        if vel and vel.trend_label == TREND_RISING and vel.velocity_score >= 65:
            type_items["AUTO_DEMAND_RISING"].append((iid, title, "rising_velocity"))
        if iid in spec_issue_ids:
            type_items["AUTO_SPEC_TOP"].append((iid, title, "spec_opportunity_top"))
        if foc_days is not None and 0 <= foc_days <= 7:
            type_items["AUTO_FOC_THIS_WEEK"].append((iid, title, f"foc_in_{foc_days}d"))
        if foc_days is not None and 0 <= foc_days <= 30:
            type_items["AUTO_FOC_NEXT_30_DAYS"].append((iid, title, f"foc_in_{foc_days}d"))
        if "batman" in blob:
            type_items["AUTO_BATMAN"].append((iid, title, "franchise_match"))
        if "spider-man" in blob or "spiderman" in blob:
            type_items["AUTO_SPIDER_MAN"].append((iid, title, "franchise_match"))
        if series.publisher.lower() == "image":
            type_items["AUTO_IMAGE"].append((iid, title, "publisher_image"))
        if series.publisher.lower() not in {"marvel", "dc comics", "image", "dark horse comics"}:
            if float(vel.velocity_score if vel else 50) >= 60:
                type_items["AUTO_INDIE_BREAKOUT"].append((iid, title, "indie_demand"))
        if series.publisher.lower() in top_publishers:
            type_items["AUTO_PUBLISHER_FOLLOWING"].append((iid, title, "publisher_following"))
        if ":" in series.series_name:
            type_items["AUTO_CREATOR_FOLLOWING"].append((iid, title, "creator_series_pattern"))

    for wl_type, items in type_items.items():
        dedup: dict[int | None, tuple[int | None, str, str]] = {}
        for entry in items:
            dedup[entry[0]] = entry
        unique = list(dedup.values())[:50]
        if not unique:
            continue
        built.append(_build_one(session, owner_user_id=owner_user_id, watchlist_type=wl_type, items=unique))

    session.commit()
    return built


def refresh_auto_watchlists(session: Session, *, owner_user_id: int) -> list[AutoWatchlist]:
    today = date.today()
    stale_cutoff = today - timedelta(days=1)
    rows = session.exec(
        select(AutoWatchlistItem, ReleaseIssue)
        .join(ReleaseIssue, AutoWatchlistItem.release_issue_id == ReleaseIssue.id, isouter=True)
        .where(AutoWatchlistItem.owner_user_id == owner_user_id)
    ).all()
    for item, issue in rows:
        if issue and issue.release_date and issue.release_date < stale_cutoff:
            item.inclusion_reason = f"{item.inclusion_reason}; stale_removed"
            item.metadata_json = {**(item.metadata_json or {}), "stale": True}
            session.add(item)
    session.flush()
    return build_auto_watchlists(session, owner_user_id=owner_user_id)


def get_latest_watchlists(session: Session, *, owner_user_id: int) -> list[AutoWatchlist]:
    latest: dict[str, AutoWatchlist] = {}
    rows = session.exec(select(AutoWatchlist).where(AutoWatchlist.owner_user_id == owner_user_id)).all()
    for row in rows:
        if (row.metadata_json or {}).get("archived"):
            continue
        prev = latest.get(row.watchlist_type)
        if prev is None or row.generation_epoch > prev.generation_epoch:
            latest[row.watchlist_type] = row
    return list(latest.values())


def list_watchlist_items(session: Session, *, watchlist_id: int) -> list[AutoWatchlistItem]:
    return list(
        session.exec(
            select(AutoWatchlistItem)
            .where(AutoWatchlistItem.watchlist_id == watchlist_id)
            .order_by(AutoWatchlistItem.id.asc())
        ).all()
    )
