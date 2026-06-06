"""P74-01 release monitoring, dashboards, and watchlist activity."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.release_event_history import (
    P74_CHANGE_NEW_VARIANT,
    P74_EVENT_DISCOVERED,
    P74_EVENT_VARIANT_ADDED,
    P74ReleaseChangeRecord,
    P74ReleaseEventHistory,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_monitoring_snapshot import (
    P74ReleaseChangeSnapshot,
    P74ReleaseMonitoringSnapshot,
    P74VariantMonitoringSnapshot,
)
from app.models.release_watchlist import ReleaseWatchlist, ReleaseWatchlistItem
from app.schemas.release_monitoring import (
    P74DiscoveryHighlightRead,
    P74ReleaseChangeRead,
    P74ReleaseEventRead,
    P74ReleaseMonitoringDashboardRead,
    P74UpcomingReleaseRowRead,
    P74UpcomingReleasesRead,
    P74VariantChangeRead,
    P74WatchlistActivityRead,
)


def _variant_count(session: Session, issue_id: int) -> int:
    return len(session.exec(select(ReleaseVariant.id).where(ReleaseVariant.issue_id == issue_id)).all())


def _window_for_release(release_date: date | None, *, today: date) -> str | None:
    if release_date is None:
        return None
    delta = (release_date - today).days
    if delta < 0:
        return None
    if delta <= 7:
        return "THIS_WEEK"
    if delta <= 14:
        return "NEXT_WEEK"
    if delta <= 30:
        return "NEXT_30_DAYS"
    if delta <= 90:
        return "NEXT_90_DAYS"
    return None


def build_upcoming_releases(session: Session, *, owner_user_id: int) -> P74UpcomingReleasesRead:
    today = date.today()
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc().nulls_last(), ReleaseIssue.id.asc())
    ).all()

    buckets: dict[str, list[P74UpcomingReleaseRowRead]] = {
        "THIS_WEEK": [],
        "NEXT_WEEK": [],
        "NEXT_30_DAYS": [],
        "NEXT_90_DAYS": [],
    }
    for issue, series in rows:
        window = _window_for_release(issue.release_date, today=today)
        if window is None:
            continue
        row = P74UpcomingReleaseRowRead(
            issue_id=int(issue.id or 0),
            publisher=series.publisher,
            series_name=series.series_name,
            issue_number=issue.issue_number,
            title=issue.title,
            release_date=issue.release_date,
            variant_count=_variant_count(session, int(issue.id or 0)),
            window=window,
        )
        buckets[window].append(row)
        if window == "NEXT_WEEK" and issue.release_date and (issue.release_date - today).days <= 30:
            if not any(r.issue_id == row.issue_id for r in buckets["NEXT_30_DAYS"]):
                buckets["NEXT_30_DAYS"].append(row)
        if window in {"THIS_WEEK", "NEXT_WEEK", "NEXT_30_DAYS"} and issue.release_date:
            if (issue.release_date - today).days <= 90 and not any(
                r.issue_id == row.issue_id for r in buckets["NEXT_90_DAYS"]
            ):
                buckets["NEXT_90_DAYS"].append(row)

    return P74UpcomingReleasesRead(
        this_week=buckets["THIS_WEEK"],
        next_week=buckets["NEXT_WEEK"],
        next_30_days=buckets["NEXT_30_DAYS"],
        next_90_days=buckets["NEXT_90_DAYS"],
    )


def list_recent_changes(
    session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[P74ReleaseChangeRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = list(
        session.exec(
            select(P74ReleaseChangeRecord)
            .where(P74ReleaseChangeRecord.owner_user_id == owner_user_id)
            .order_by(P74ReleaseChangeRecord.detected_at.desc(), P74ReleaseChangeRecord.id.desc())
        ).all()
    )
    page = rows[offset : offset + limit]
    return [P74ReleaseChangeRead.model_validate(r) for r in page], len(rows)


def list_event_history(
    session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0
) -> tuple[list[P74ReleaseEventRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = list(
        session.exec(
            select(P74ReleaseEventHistory)
            .where(P74ReleaseEventHistory.owner_user_id == owner_user_id)
            .order_by(P74ReleaseEventHistory.created_at.desc(), P74ReleaseEventHistory.id.desc())
        ).all()
    )
    page = rows[offset : offset + limit]
    return [P74ReleaseEventRead.model_validate(r) for r in page], len(rows)


def _discovery_highlights(session: Session, *, owner_user_id: int) -> list[P74DiscoveryHighlightRead]:
    today = date.today()
    horizon = today + timedelta(days=90)
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_date.is_not(None))
        .where(ReleaseIssue.release_date >= today)
        .where(ReleaseIssue.release_date <= horizon)
    ).all()
    highlights: list[P74DiscoveryHighlightRead] = []
    for issue, series in issues:
        num = issue.issue_number.strip().lstrip("#")
        if num == "1":
            highlights.append(
                P74DiscoveryHighlightRead(
                    category="NEW_NUMBER_ONE",
                    issue_id=int(issue.id or 0),
                    publisher=series.publisher,
                    series_name=series.series_name,
                    issue_number=issue.issue_number,
                    release_date=issue.release_date,
                )
            )
        if series.series_type.upper() in {"ONGOING", "NEW"} and num == "1":
            highlights.append(
                P74DiscoveryHighlightRead(
                    category="NEW_SERIES",
                    issue_id=int(issue.id or 0),
                    publisher=series.publisher,
                    series_name=series.series_name,
                    issue_number=issue.issue_number,
                    release_date=issue.release_date,
                )
            )
    signals = session.exec(
        select(ReleaseKeySignal, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, ReleaseKeySignal.issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseKeySignal.owner_user_id == owner_user_id)
        .order_by(ReleaseKeySignal.created_at.desc())
        .limit(20)
    ).all()
    for signal, issue, series in signals:
        cat = signal.signal_type
        if cat not in {"NEW_NUMBER_ONE", "VARIANT_OPPORTUNITY", "KEY_ISSUE"}:
            continue
        highlights.append(
            P74DiscoveryHighlightRead(
                category=cat,
                issue_id=int(issue.id or 0),
                publisher=series.publisher,
                series_name=series.series_name,
                issue_number=issue.issue_number,
                release_date=issue.release_date,
            )
        )
    return highlights[:25]


def _variant_changes(session: Session, *, owner_user_id: int, limit: int = 20) -> list[P74VariantChangeRead]:
    rows = session.exec(
        select(P74ReleaseChangeRecord)
        .where(P74ReleaseChangeRecord.owner_user_id == owner_user_id)
        .where(P74ReleaseChangeRecord.change_type == P74_CHANGE_NEW_VARIANT)
        .order_by(P74ReleaseChangeRecord.detected_at.desc(), P74ReleaseChangeRecord.id.desc())
        .limit(limit)
    ).all()
    out: list[P74VariantChangeRead] = []
    for row in rows:
        after = row.after_json or {}
        out.append(
            P74VariantChangeRead(
                change_id=int(row.id or 0),
                issue_id=row.issue_id,
                variant_id=row.variant_id,
                variant_name=str(after.get("variant_name") or ""),
                change_type=row.change_type,
                detected_at=row.detected_at,
                late_added=bool(after.get("late_added")),
            )
        )
    return out


def _issue_matches_watchlist_item(
    issue: ReleaseIssue,
    series: ReleaseSeries,
    item: ReleaseWatchlistItem,
) -> bool:
    if item.series_name and item.series_name.lower() in series.series_name.lower():
        return True
    if item.publisher and item.publisher.lower() == series.publisher.lower():
        return True
    if item.keyword and item.keyword.lower() in (issue.title or "").lower():
        return True
    if item.character_name and item.character_name.lower() in (issue.title or "").lower():
        return True
    if item.creator_name and item.creator_name.lower() in (issue.title or "").lower():
        return True
    return False


def build_watchlist_monitoring(session: Session, *, owner_user_id: int) -> list[P74WatchlistActivityRead]:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    watchlists = session.exec(
        select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ).all()
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    events = list(
        session.exec(
            select(P74ReleaseEventHistory)
            .where(P74ReleaseEventHistory.owner_user_id == owner_user_id)
            .where(P74ReleaseEventHistory.created_at >= since)
            .order_by(P74ReleaseEventHistory.created_at.desc())
        ).all()
    )
    activity: list[P74WatchlistActivityRead] = []
    for wl in watchlists:
        items = session.exec(
            select(ReleaseWatchlistItem).where(ReleaseWatchlistItem.watchlist_id == int(wl.id or 0))
        ).all()
        matched_issue_ids: set[int] = set()
        for issue, series in issues:
            if any(_issue_matches_watchlist_item(issue, series, it) for it in items):
                matched_issue_ids.add(int(issue.id or 0))
        related = [e for e in events if e.issue_id in matched_issue_ids or not matched_issue_ids]
        if items:
            related = [e for e in events if e.issue_id in matched_issue_ids]
        activity.append(
            P74WatchlistActivityRead(
                watchlist_id=int(wl.id or 0),
                watchlist_name=wl.watchlist_name,
                watchlist_type=wl.watchlist_type,
                changes_since_review=len(related),
                recent_events=[P74ReleaseEventRead.model_validate(e) for e in related[:5]],
            )
        )
    return activity


def persist_monitoring_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    upcoming: P74UpcomingReleasesRead,
) -> P74ReleaseMonitoringSnapshot:
    mon = P74ReleaseMonitoringSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        upcoming_total=sum(
            len(x)
            for x in (
                upcoming.this_week,
                upcoming.next_week,
                upcoming.next_30_days,
                upcoming.next_90_days,
            )
        ),
        this_week_count=len(upcoming.this_week),
        next_week_count=len(upcoming.next_week),
        next_30_days_count=len(upcoming.next_30_days),
        next_90_days_count=len(upcoming.next_90_days),
        windows_json={
            "this_week": [r.model_dump(mode="json") for r in upcoming.this_week[:50]],
            "next_week": [r.model_dump(mode="json") for r in upcoming.next_week[:50]],
        },
    )
    session.add(mon)
    session.flush()

    changes, _ = list_recent_changes(session, owner_user_id=owner_user_id, limit=500, offset=0)
    discoveries = sum(1 for c in changes if c.change_type == "NEW_ISSUE")
    removals = sum(1 for c in changes if c.change_type == "REMOVED")
    session.add(
        P74ReleaseChangeSnapshot(
            owner_user_id=owner_user_id,
            monitoring_snapshot_id=int(mon.id or 0),
            changes_total=len(changes),
            discoveries_total=discoveries,
            removals_total=removals,
            summary_json={"recent": [c.model_dump(mode="json") for c in changes[:20]]},
        )
    )
    variant_rows = _variant_changes(session, owner_user_id=owner_user_id, limit=200)
    session.add(
        P74VariantMonitoringSnapshot(
            owner_user_id=owner_user_id,
            monitoring_snapshot_id=int(mon.id or 0),
            variants_added=len(variant_rows),
            ratio_variants_added=sum(1 for v in variant_rows if "ratio" in v.variant_name.lower() or v.late_added),
            incentive_variants_added=sum(1 for v in variant_rows if "incentive" in v.variant_name.lower()),
            late_variants_added=sum(1 for v in variant_rows if v.late_added),
        )
    )
    session.commit()
    session.refresh(mon)
    return mon


def build_release_monitoring_dashboard(
    session: Session, *, owner_user_id: int, persist: bool = True
) -> P74ReleaseMonitoringDashboardRead:
    upcoming = build_upcoming_releases(session, owner_user_id=owner_user_id)
    snap_id = 0
    generated_at = datetime.now(timezone.utc)
    if persist:
        mon = persist_monitoring_snapshots(session, owner_user_id=owner_user_id, upcoming=upcoming)
        snap_id = int(mon.id or 0)
        generated_at = mon.generated_at
        upcoming.snapshot_id = snap_id
    changes, _ = list_recent_changes(session, owner_user_id=owner_user_id, limit=15, offset=0)
    return P74ReleaseMonitoringDashboardRead(
        snapshot_id=snap_id,
        generated_at=generated_at,
        upcoming=upcoming,
        recent_changes=changes,
        new_number_ones=_discovery_highlights(session, owner_user_id=owner_user_id),
        variant_changes=_variant_changes(session, owner_user_id=owner_user_id),
        watchlist_activity=build_watchlist_monitoring(session, owner_user_id=owner_user_id),
    )
