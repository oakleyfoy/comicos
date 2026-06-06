"""P81-02 personalized discovery, watchlists, alerts, and future pull list."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.p81_discovery import (
    P81DiscoveryAlert,
    P81DiscoveryOpportunity,
    P81DiscoveryWatchlist,
    P81FuturePullListItem,
    utc_now,
)
from app.models.release_intelligence import ReleaseIssue
from app.schemas.p81_discovery_personalization import (
    P81DiscoveryAlertListResponse,
    P81DiscoveryAlertRead,
    P81DiscoveryAlertUpdate,
    P81DiscoveryWatchlistCreate,
    P81DiscoveryWatchlistListResponse,
    P81DiscoveryWatchlistRead,
    P81DiscoveryWatchlistUpdate,
    P81FocOpportunityRead,
    P81FuturePullListItemRead,
    P81FuturePullListResponse,
    P81PersonalizedDiscoveryDashboardRead,
    P81PersonalizedDiscoveryListResponse,
    P81PersonalizedOpportunityRead,
)
from app.services.p77_personalization_engine import load_personalization_context, personalize_score, recommend_personalized_quantity
from app.services.p81_discovery_ingestion import ingest_discovery_opportunities
from app.services.p81_discovery_service import _published_rows, _to_read

_ALERT_TYPE_MAP = {
    "NEW_SERIES": "NEW_SERIES_ALERT",
    "NEW_1": "NEW_1_ALERT",
    "MILESTONE": "MILESTONE_ALERT",
    "CREATOR_PROJECT": "CREATOR_ALERT",
    "VARIANT_EXPANSION": "VARIANT_ALERT",
    "ANNIVERSARY": "MILESTONE_ALERT",
}


def _personalized_category(score: float) -> str:
    if score >= 90:
        return "MUST_BUY"
    if score >= 75:
        return "HIGH_PRIORITY"
    if score >= 50:
        return "WATCH"
    if score >= 30:
        return "LOW_PRIORITY"
    return "IGNORE"


def _alert_priority(score: float) -> str:
    if score >= 95:
        return "CRITICAL"
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "NORMAL"
    return "LOW"


def _recommendation_action(category: str) -> str:
    if category == "MUST_BUY":
        return "BUY"
    if category == "HIGH_PRIORITY":
        return "BUY"
    if category == "WATCH":
        return "WATCH"
    return "PASS"


def _watch_level(category: str) -> str:
    if category == "MUST_BUY":
        return "CRITICAL"
    if category == "HIGH_PRIORITY":
        return "HIGH"
    if category == "WATCH":
        return "NORMAL"
    return "LOW"


def personalize_opportunity_row(
    session: Session,
    *,
    owner_user_id: int,
    row: P81DiscoveryOpportunity,
    ctx=None,
) -> P81PersonalizedOpportunityRead:
    if ctx is None:
        ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    global_score = float(row.discovery_score)
    personalized, adj, _, _, adjustments, reasons = personalize_score(
        ctx,
        global_score=global_score,
        publisher=row.publisher,
        series_name=row.series_name,
        title=row.title,
        owned_copies=0,
        gap_completion=False,
        estimated_price=4.0,
    )
    personalized = round(min(110.0, global_score + adj), 1)
    category = _personalized_category(personalized)
    qty, _ = recommend_personalized_quantity(
        ctx,
        global_quantity=ctx.profile.default_copy_count,
        global_score=personalized,
        owned_copies=0,
        is_key_issue=row.opportunity_type in {"MILESTONE", "NEW_1"},
    )
    action = _recommendation_action(category)
    if action == "PASS":
        qty = 0
    return P81PersonalizedOpportunityRead(
        opportunity=_to_read(row),
        discovery_score=global_score,
        personalized_score=personalized,
        collector_adjustment=round(adj, 1),
        priority_category=category,  # type: ignore[arg-type]
        adjustments=adjustments,
        personalization_reasons=reasons[:6],
        recommendation_action=action,
        recommendation_quantity=qty,
        recommendation_score=personalized,
    )


def _sync_auto_watchlists(session: Session, *, owner_user_id: int) -> None:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    now = utc_now()
    specs: list[tuple[str, str]] = []
    for item in ctx.profile.publishers:
        specs.append(("PUBLISHER", item.label))
    for item in ctx.profile.characters:
        specs.append(("CHARACTER", item.label))
    for item in ctx.profile.creators:
        specs.append(("CREATOR", item.label))
    for goal in ctx.goals:
        if goal.title.strip():
            specs.append(("SERIES", goal.title.strip()))
    existing = {
        (r.watchlist_type, r.label.lower()): r
        for r in session.exec(select(P81DiscoveryWatchlist).where(P81DiscoveryWatchlist.owner_user_id == owner_user_id)).all()
    }
    for wtype, label in specs:
        key = (wtype, label.lower())
        row = existing.get(key)
        if row is None:
            session.add(
                P81DiscoveryWatchlist(
                    owner_user_id=owner_user_id,
                    watchlist_type=wtype,
                    label=label,
                    auto_managed=True,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        elif row.auto_managed:
            row.active = True
            row.updated_at = now
            session.add(row)


def _matches_watchlist(session: Session, *, owner_user_id: int, row: P81DiscoveryOpportunity) -> bool:
    hay = f"{row.publisher} {row.series_name} {row.title} {row.summary}".lower()
    creators = (row.creator_metadata_json or {}).get("creators") or []
    for c in creators:
        hay += f" {c}".lower()
    lists = session.exec(
        select(P81DiscoveryWatchlist).where(
            P81DiscoveryWatchlist.owner_user_id == owner_user_id,
            P81DiscoveryWatchlist.active == True,  # noqa: E712
        )
    ).all()
    for wl in lists:
        label = wl.label.lower()
        if label and label in hay:
            return True
    return False


def _sync_alerts(session: Session, *, owner_user_id: int, personalized: list[P81PersonalizedOpportunityRead]) -> None:
    now = utc_now()
    existing_opp_ids = set(
        session.exec(
            select(P81DiscoveryAlert.opportunity_id).where(
                P81DiscoveryAlert.owner_user_id == owner_user_id,
                P81DiscoveryAlert.status != "DISMISSED",
            )
        ).all()
    )
    for item in personalized:
        if item.personalized_score < 70 or item.priority_category in {"LOW_PRIORITY", "IGNORE"}:
            continue
        opp_id = item.opportunity.id
        if opp_id in existing_opp_ids:
            continue
        opp = item.opportunity
        alert_type = _ALERT_TYPE_MAP.get(opp.opportunity_type, "NEW_1_ALERT")
        for char in load_personalization_context(session, owner_user_id=owner_user_id).profile.characters:
            if char.label.lower() in item.opportunity.title.lower():
                alert_type = "CHARACTER_ALERT"
                break
        session.add(
            P81DiscoveryAlert(
                owner_user_id=owner_user_id,
                opportunity_id=opp_id,
                alert_type=alert_type,
                priority=_alert_priority(item.personalized_score),
                title=opp.title,
                message=f"Personalized score {item.personalized_score:.0f} — {item.recommendation_action}",
                status="ACTIVE",
                personalized_score=item.personalized_score,
                created_at=now,
                updated_at=now,
            )
        )
        existing_opp_ids.add(opp_id)


def _pipeline_status(session: Session, *, row: P81DiscoveryOpportunity, watching: bool) -> tuple[str, date | None]:
    foc: date | None = None
    if row.release_issue_id:
        issue = session.get(ReleaseIssue, row.release_issue_id)
        if issue:
            foc = issue.foc_date
    today = date.today()
    if foc and foc >= today:
        return "FOC", foc
    if row.release_date and row.release_date >= today:
        return "ANNOUNCED", foc
    if watching:
        return "WATCHING", foc
    return "DISCOVERED", foc


def _sync_future_pull(
    session: Session,
    *,
    owner_user_id: int,
    personalized: list[P81PersonalizedOpportunityRead],
) -> None:
    now = utc_now()
    existing = {
        int(r.opportunity_id): r
        for r in session.exec(select(P81FuturePullListItem).where(P81FuturePullListItem.owner_user_id == owner_user_id)).all()
    }
    for item in personalized:
        if item.priority_category in {"IGNORE", "LOW_PRIORITY"}:
            continue
        row = session.get(P81DiscoveryOpportunity, item.opportunity.id)
        if row is None:
            continue
        watching = _matches_watchlist(session, owner_user_id=owner_user_id, row=row)
        pipeline, foc = _pipeline_status(session, row=row, watching=watching)
        pull = existing.get(item.opportunity.id)
        if pull is None:
            pull = P81FuturePullListItem(
                owner_user_id=owner_user_id,
                opportunity_id=item.opportunity.id,
                title=row.title,
                series_name=row.series_name,
                issue_number=row.issue_number,
                created_at=now,
            )
        pull.title = row.title
        pull.series_name = row.series_name
        pull.issue_number = row.issue_number
        pull.pipeline_status = pipeline
        pull.watch_level = _watch_level(item.priority_category)
        pull.recommendation_action = item.recommendation_action
        pull.recommendation_quantity = item.recommendation_quantity
        pull.personalized_score = item.personalized_score
        pull.priority_category = item.priority_category
        pull.release_date = row.release_date
        pull.foc_date = foc
        pull.updated_at = now
        session.add(pull)


def refresh_personalized_discovery(session: Session, *, owner_user_id: int, ingest: bool = True) -> list[P81PersonalizedOpportunityRead]:
    if ingest:
        ingest_discovery_opportunities(session, owner_user_id=owner_user_id)
    _sync_auto_watchlists(session, owner_user_id=owner_user_id)
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    rows = _published_rows(session, owner_user_id=owner_user_id)
    personalized = [personalize_opportunity_row(session, owner_user_id=owner_user_id, row=r, ctx=ctx) for r in rows]
    personalized.sort(key=lambda x: x.personalized_score, reverse=True)
    _sync_alerts(session, owner_user_id=owner_user_id, personalized=personalized)
    _sync_future_pull(session, owner_user_id=owner_user_id, personalized=personalized)
    session.flush()
    return personalized


def list_personalized_discovery(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
) -> P81PersonalizedDiscoveryListResponse:
    items = refresh_personalized_discovery(session, owner_user_id=owner_user_id) if refresh else []
    if not refresh:
        ctx = load_personalization_context(session, owner_user_id=owner_user_id)
        rows = _published_rows(session, owner_user_id=owner_user_id)
        items = [personalize_opportunity_row(session, owner_user_id=owner_user_id, row=r, ctx=ctx) for r in rows]
        items.sort(key=lambda x: x.personalized_score, reverse=True)
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page = items[off : off + lim]
    return P81PersonalizedDiscoveryListResponse(items=page, total_items=len(items), limit=lim, offset=off)


def build_personalized_discovery_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    refresh: bool = True,
) -> P81PersonalizedDiscoveryDashboardRead:
    items = refresh_personalized_discovery(session, owner_user_id=owner_user_id, ingest=refresh)
    must_buy = [i for i in items if i.priority_category == "MUST_BUY"][:20]
    high = [i for i in items if i.priority_category == "HIGH_PRIORITY"][:20]
    watch = [i for i in items if i.priority_category == "WATCH"][:20]
    pull_rows = list(
        session.exec(
            select(P81FuturePullListItem)
            .where(P81FuturePullListItem.owner_user_id == owner_user_id)
            .order_by(P81FuturePullListItem.personalized_score.desc(), P81FuturePullListItem.id.desc())
            .limit(30)
        ).all()
    )
    future_pull = [
        P81FuturePullListItemRead(
            id=int(p.id or 0),
            opportunity_id=int(p.opportunity_id),
            title=p.title,
            series_name=p.series_name,
            issue_number=p.issue_number,
            pipeline_status=p.pipeline_status,
            watch_level=p.watch_level,
            recommendation_action=p.recommendation_action,
            recommendation_quantity=int(p.recommendation_quantity),
            personalized_score=float(p.personalized_score),
            priority_category=p.priority_category,  # type: ignore[arg-type]
            release_date=p.release_date,
            foc_date=p.foc_date,
            updated_at=p.updated_at,
        )
        for p in pull_rows
    ]
    watchlists = list_watchlists(session, owner_user_id=owner_user_id).items
    alerts = list_alerts(session, owner_user_id=owner_user_id, status="ACTIVE", limit=20, offset=0).items
    today = date.today()
    horizon = today + timedelta(days=45)
    upcoming_foc: list[P81FocOpportunityRead] = []
    for item in items:
        pull = next((p for p in pull_rows if int(p.opportunity_id) == item.opportunity.id), None)
        if pull and pull.foc_date and today <= pull.foc_date <= horizon:
            upcoming_foc.append(
                P81FocOpportunityRead(
                    opportunity_id=item.opportunity.id,
                    title=item.opportunity.title,
                    foc_date=pull.foc_date,
                    release_date=item.opportunity.release_date,
                    personalized_score=item.personalized_score,
                )
            )
    upcoming_foc.sort(key=lambda x: x.foc_date)
    return P81PersonalizedDiscoveryDashboardRead(
        must_buy=must_buy,
        high_priority=high,
        watch=watch,
        future_pull_list=future_pull,
        watchlists=watchlists,
        active_alerts=alerts,
        upcoming_foc=upcoming_foc[:15],
        counts={
            "must_buy": len(must_buy),
            "high_priority": len(high),
            "watch": len(watch),
            "future_pull": len(future_pull),
            "active_alerts": len(alerts),
            "upcoming_foc": len(upcoming_foc),
        },
    )


def list_watchlists(session: Session, *, owner_user_id: int) -> P81DiscoveryWatchlistListResponse:
    rows = list(
        session.exec(
            select(P81DiscoveryWatchlist)
            .where(P81DiscoveryWatchlist.owner_user_id == owner_user_id)
            .order_by(P81DiscoveryWatchlist.watchlist_type, P81DiscoveryWatchlist.label)
        ).all()
    )
    items = [
        P81DiscoveryWatchlistRead(
            id=int(r.id or 0),
            watchlist_type=r.watchlist_type,  # type: ignore[arg-type]
            label=r.label,
            auto_managed=r.auto_managed,
            active=r.active,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return P81DiscoveryWatchlistListResponse(items=items, total_items=len(items))


def create_watchlist(
    session: Session,
    *,
    owner_user_id: int,
    payload: P81DiscoveryWatchlistCreate,
) -> P81DiscoveryWatchlistRead:
    now = utc_now()
    row = P81DiscoveryWatchlist(
        owner_user_id=owner_user_id,
        watchlist_type=payload.watchlist_type,
        label=payload.label.strip(),
        auto_managed=False,
        active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return P81DiscoveryWatchlistRead(
        id=int(row.id or 0),
        watchlist_type=row.watchlist_type,  # type: ignore[arg-type]
        label=row.label,
        auto_managed=row.auto_managed,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def update_watchlist(
    session: Session,
    *,
    owner_user_id: int,
    watchlist_id: int,
    payload: P81DiscoveryWatchlistUpdate,
) -> P81DiscoveryWatchlistRead:
    row = session.get(P81DiscoveryWatchlist, watchlist_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return P81DiscoveryWatchlistRead(
        id=int(row.id or 0),
        watchlist_type=row.watchlist_type,  # type: ignore[arg-type]
        label=row.label,
        auto_managed=row.auto_managed,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_alerts(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> P81DiscoveryAlertListResponse:
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    stmt = select(P81DiscoveryAlert).where(P81DiscoveryAlert.owner_user_id == owner_user_id)
    if status:
        stmt = stmt.where(P81DiscoveryAlert.status == status.strip().upper())
    rows = list(session.exec(stmt.order_by(P81DiscoveryAlert.personalized_score.desc(), P81DiscoveryAlert.id.desc())).all())
    page = rows[off : off + lim]
    items = [
        P81DiscoveryAlertRead(
            id=int(r.id or 0),
            opportunity_id=int(r.opportunity_id),
            alert_type=r.alert_type,
            priority=r.priority,  # type: ignore[arg-type]
            title=r.title,
            message=r.message,
            status=r.status,
            personalized_score=float(r.personalized_score),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in page
    ]
    return P81DiscoveryAlertListResponse(items=items, total_items=len(rows), limit=lim, offset=off)


def update_alert(
    session: Session,
    *,
    owner_user_id: int,
    alert_id: int,
    payload: P81DiscoveryAlertUpdate,
) -> P81DiscoveryAlertRead:
    row = session.get(P81DiscoveryAlert, alert_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if payload.status is not None:
        row.status = payload.status
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return P81DiscoveryAlertRead(
        id=int(row.id or 0),
        opportunity_id=int(row.opportunity_id),
        alert_type=row.alert_type,
        priority=row.priority,  # type: ignore[arg-type]
        title=row.title,
        message=row.message,
        status=row.status,
        personalized_score=float(row.personalized_score),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_future_pull_list(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
) -> P81FuturePullListResponse:
    if refresh:
        refresh_personalized_discovery(session, owner_user_id=owner_user_id)
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    rows = list(
        session.exec(
            select(P81FuturePullListItem)
            .where(P81FuturePullListItem.owner_user_id == owner_user_id)
            .order_by(P81FuturePullListItem.personalized_score.desc(), P81FuturePullListItem.id.desc())
        ).all()
    )
    page = rows[off : off + lim]
    items = [
        P81FuturePullListItemRead(
            id=int(p.id or 0),
            opportunity_id=int(p.opportunity_id),
            title=p.title,
            series_name=p.series_name,
            issue_number=p.issue_number,
            pipeline_status=p.pipeline_status,
            watch_level=p.watch_level,
            recommendation_action=p.recommendation_action,
            recommendation_quantity=int(p.recommendation_quantity),
            personalized_score=float(p.personalized_score),
            priority_category=p.priority_category,  # type: ignore[arg-type]
            release_date=p.release_date,
            foc_date=p.foc_date,
            updated_at=p.updated_at,
        )
        for p in page
    ]
    return P81FuturePullListResponse(items=items, total_items=len(rows), limit=lim, offset=off)
