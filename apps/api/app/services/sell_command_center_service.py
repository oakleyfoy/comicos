"""P89-05 Sell Command Center — cached/stored aggregates only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.p89_listing_draft import P89ListingDraft
from app.models.p89_managed_listing import P89ManagedListing
from app.models.p89_sell_candidate import P89SellCandidate
from app.schemas.p89_sell_command_center import (
    SellCommandCenterActionRead,
    SellCommandCenterActiveListingRead,
    SellCommandCenterBriefingSummaryRead,
    SellCommandCenterCandidateRead,
    SellCommandCenterDraftRead,
    SellCommandCenterKpiRead,
    SellCommandCenterProfitSummaryRead,
    SellCommandCenterQuickActionRead,
    SellCommandCenterRead,
    SellCommandCenterSoldRead,
    SellCommandCenterStaleRead,
)
from app.services.listing_draft_service import count_drafts_awaiting_review
from app.services.listing_management_service import build_portfolio_listing_summary
from app.services.storage_copy_meta import copy_display_meta

STALE_LISTING_DAYS = 30
STALE_DRAFT_DAYS = 30
SOLD_RECENT_DAYS = 30
_SECTION_LIMIT = 8


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _month_start(now: datetime | None = None) -> datetime:
    n = now or _utc_now()
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _comic_title(session: Session, *, copy: InventoryCopy | None, fallback: str = "") -> str:
    if copy is None:
        return fallback or "Comic"
    meta = copy_display_meta(session, copy=copy)
    return str(meta.get("display_title") or fallback or "Comic")


def _active_candidates(session: Session, *, owner_user_id: int) -> list[P89SellCandidate]:
    return list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
        ).all()
    )


def _count_rec(session: Session, *, owner_user_id: int, recommendation: str) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
            .where(P89SellCandidate.recommendation == recommendation)
        ).one()
        or 0
    )


def _pricing_hint(session: Session, *, owner_user_id: int, copy: InventoryCopy | None) -> tuple[float | None, str | None]:
    if copy is None:
        return None, None
    from app.services.p89_market_pricing_service import lookup_latest_snapshot

    meta = copy_display_meta(session, copy=copy)
    snap = lookup_latest_snapshot(
        session,
        owner_user_id=owner_user_id,
        series=str(meta.get("series_name") or ""),
        issue_number=str(meta.get("issue_number") or ""),
        variant=str(meta.get("variant_label") or ""),
    )
    if snap is None:
        fmv = float(copy.current_fmv or 0)
        return (round(fmv, 2) if fmv > 0 else None), None
    return float(snap.market_price), snap.trend_direction


def _candidate_read(
    session: Session,
    *,
    owner_user_id: int,
    row: P89SellCandidate,
    cta_label: str,
) -> SellCommandCenterCandidateRead:
    copy = session.get(InventoryCopy, row.inventory_copy_id)
    title = _comic_title(session, copy=copy)
    market_price, trend = _pricing_hint(session, owner_user_id=owner_user_id, copy=copy)
    upside = None
    if row.recommendation == "GRADE_FIRST" and market_price is not None:
        upside = round(max(0.0, float(row.estimated_sale_value) - market_price), 2)
    return SellCommandCenterCandidateRead(
        sell_candidate_id=int(row.id or 0),
        inventory_copy_id=int(row.inventory_copy_id),
        comic_title=title,
        recommendation=row.recommendation,
        sell_score=float(row.sell_score),
        hold_score=float(row.hold_score),
        grade_first_score=float(row.grade_first_score),
        estimated_sale_value=float(row.estimated_sale_value),
        estimated_profit=float(row.estimated_profit),
        potential_upside=upside,
        confidence=row.confidence,
        reason_summary=row.reason_summary,
        market_price=market_price,
        trend_direction=trend,
        cta_label=cta_label,
        cta_route="/sell-candidates",
    )


def _kpis(session: Session, *, owner_user_id: int, portfolio: dict) -> SellCommandCenterKpiRead:
    sell_now = _count_rec(session, owner_user_id=owner_user_id, recommendation="SELL_NOW")
    grade_first = _count_rec(session, owner_user_id=owner_user_id, recommendation="GRADE_FIRST")
    drafts = count_drafts_awaiting_review(session, owner_user_id=owner_user_id)
    active_listings = int(portfolio.get("active_listings_count") or 0)
    sold_month = int(portfolio.get("sold_this_month_count") or 0)
    realized = float(portfolio.get("sold_this_month_net_profit") or 0)
    pipeline = round(
        sum(
            float(r.estimated_profit)
            for r in _active_candidates(session, owner_user_id=owner_user_id)
            if r.recommendation == "SELL_NOW"
        ),
        2,
    )
    return SellCommandCenterKpiRead(
        sell_now_count=sell_now,
        grade_first_count=grade_first,
        drafts_awaiting_review=drafts,
        active_listings=active_listings,
        sold_this_month=sold_month,
        estimated_net_profit=round(realized + pipeline, 2),
    )


def _profit_summary(session: Session, *, owner_user_id: int) -> SellCommandCenterProfitSummaryRead:
    start = _month_start()
    rows = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "SOLD")
            .where(P89ManagedListing.sold_at >= start)
        ).all()
    )
    gross = round(sum(float(r.sale_price or 0) + float(r.shipping_charged or 0) for r in rows), 2)
    fees = round(sum(float(r.marketplace_fees or 0) for r in rows), 2)
    ship = round(sum(float(r.shipping_cost or 0) for r in rows), 2)
    net_vals = [float(r.net_profit) for r in rows if r.net_profit is not None]
    net = round(sum(net_vals), 2)
    count = len(rows)
    avg = round(net / count, 2) if count and net_vals else 0.0
    return SellCommandCenterProfitSummaryRead(
        gross_sales=gross,
        fees=fees,
        shipping_costs=ship,
        net_profit=net,
        average_profit_per_sale=avg,
        sold_count=count,
    )


def _quick_actions() -> list[SellCommandCenterQuickActionRead]:
    return [
        SellCommandCenterQuickActionRead(
            label="Generate Sell Candidates",
            route="/sell-candidates",
            action_type="GENERATE_SELL_CANDIDATES",
        ),
        SellCommandCenterQuickActionRead(
            label="Run Market Pricing",
            route="/market-pricing",
            action_type="RUN_MARKET_PRICING",
        ),
        SellCommandCenterQuickActionRead(
            label="Review Listing Drafts",
            route="/listing-drafts",
            action_type="LISTING_DRAFTS",
        ),
        SellCommandCenterQuickActionRead(
            label="Open Listing Management",
            route="/listing-management",
            action_type="LISTING_MANAGEMENT",
        ),
        SellCommandCenterQuickActionRead(
            label="Open Sell Candidates",
            route="/sell-candidates",
            action_type="SELL_CANDIDATES",
        ),
        SellCommandCenterQuickActionRead(
            label="Open Market Pricing",
            route="/market-pricing",
            action_type="MARKET_PRICING",
        ),
    ]


def _build_daily_actions(
    *,
    sell_now: list[SellCommandCenterCandidateRead],
    grade_first: list[SellCommandCenterCandidateRead],
    drafts: list[SellCommandCenterDraftRead],
    active: list[SellCommandCenterActiveListingRead],
    stale: list[SellCommandCenterStaleRead],
) -> list[SellCommandCenterActionRead]:
    actions: list[SellCommandCenterActionRead] = []
    if sell_now:
        profit = sum(c.estimated_profit for c in sell_now[:3])
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title=f"Review {min(len(sell_now), 3)} SELL NOW candidates",
                detail=f"Top opportunities with about ${profit:.0f} estimated profit.",
                action_label="Review Sell Candidates",
                route="/sell-candidates",
                urgency_score=100.0 + profit,
            )
        )
    if grade_first:
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title=f"Grade {min(len(grade_first), 2)} books before selling",
                detail="Grade-first paths may unlock higher sale value.",
                action_label="Review Grade First",
                route="/sell-candidates",
                urgency_score=80.0 + sum(c.potential_upside or 0 for c in grade_first[:2]),
            )
        )
    if drafts:
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title=f"Review {min(len(drafts), 4)} listing drafts",
                detail="Copy-ready drafts waiting for your review.",
                action_label="Review Drafts",
                route="/listing-drafts",
                urgency_score=70.0 + len(drafts) * 2,
            )
        )
    needs_review = [a for a in active if a.needs_review]
    if needs_review:
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title=f"Reprice or refresh {len(needs_review)} stale active listings",
                detail="Listings listed longer than the review threshold.",
                action_label="Manage Listings",
                route=f"/listing-management/{needs_review[0].listing_id}",
                urgency_score=65.0 + len(needs_review) * 3,
            )
        )
    if stale:
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title=f"Review {min(len(stale), 3)} expired or stale listings",
                detail="Archive, re-list, or mark sold to keep your seller queue clean.",
                action_label="Review Listing",
                route=stale[0].cta_route,
                urgency_score=60.0 + len(stale),
            )
        )
    if not sell_now and active:
        actions.append(
            SellCommandCenterActionRead(
                rank=0,
                title="Mark an active listing sold or expired",
                detail="Keep managed listings aligned with marketplace reality.",
                action_label="Open Listing Management",
                route="/listing-management",
                urgency_score=55.0,
            )
        )
    actions.sort(key=lambda a: a.urgency_score, reverse=True)
    for idx, action in enumerate(actions, start=1):
        actions[idx - 1] = action.model_copy(update={"rank": idx})
    return actions[:6]


def build_sell_command_center_briefing_summary(dashboard: SellCommandCenterRead) -> SellCommandCenterBriefingSummaryRead:
    top_sell = dashboard.sell_now[0].comic_title if dashboard.sell_now else None
    top_grade = dashboard.grade_first[0].comic_title if dashboard.grade_first else None
    return SellCommandCenterBriefingSummaryRead(
        top_sell_candidate=top_sell,
        top_grade_first_candidate=top_grade,
        drafts_awaiting_review=dashboard.kpis.drafts_awaiting_review,
        active_listings=dashboard.kpis.active_listings,
        sold_this_month=dashboard.kpis.sold_this_month,
        net_profit_this_month=dashboard.profit_summary.net_profit,
    )


def build_sell_command_center(session: Session, *, owner_user_id: int) -> SellCommandCenterRead:
    now = _utc_now()
    portfolio = build_portfolio_listing_summary(session, owner_user_id=owner_user_id)
    kpis = _kpis(session, owner_user_id=owner_user_id, portfolio=portfolio)
    candidates = _active_candidates(session, owner_user_id=owner_user_id)

    sell_now_rows = sorted(
        [c for c in candidates if c.recommendation == "SELL_NOW"],
        key=lambda r: (float(r.sell_score), float(r.estimated_profit)),
        reverse=True,
    )[:_SECTION_LIMIT]
    grade_rows = sorted(
        [c for c in candidates if c.recommendation == "GRADE_FIRST"],
        key=lambda r: (float(r.grade_first_score), float(r.estimated_sale_value)),
        reverse=True,
    )[:_SECTION_LIMIT]
    hold_monitor_rows = sorted(
        [c for c in candidates if c.recommendation in {"HOLD", "MONITOR"}],
        key=lambda r: float(r.estimated_sale_value),
        reverse=True,
    )[:_SECTION_LIMIT]

    sell_now = [_candidate_read(session, owner_user_id=owner_user_id, row=r, cta_label="Review Sell Candidate") for r in sell_now_rows]
    grade_first = [
        _candidate_read(session, owner_user_id=owner_user_id, row=r, cta_label="Review Grading Candidate") for r in grade_rows
    ]
    hold_or_monitor = [
        _candidate_read(session, owner_user_id=owner_user_id, row=r, cta_label="Review Recommendation") for r in hold_monitor_rows
    ]

    draft_rows = list(
        session.exec(
            select(P89ListingDraft)
            .where(P89ListingDraft.owner_user_id == owner_user_id)
            .where(P89ListingDraft.status == "DRAFT")
            .order_by(P89ListingDraft.created_at.desc())
            .limit(_SECTION_LIMIT)
        ).all()
    )
    drafts_needing_review = []
    for d in draft_rows:
        copy = session.get(InventoryCopy, d.inventory_copy_id)
        drafts_needing_review.append(
            SellCommandCenterDraftRead(
                draft_id=int(d.id or 0),
                comic_title=_comic_title(session, copy=copy, fallback=d.title),
                marketplace=d.marketplace,
                suggested_price=d.suggested_price,
                created_at=d.created_at,
                cta_route=f"/listing-drafts/{int(d.id or 0)}",
            )
        )

    active_rows = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "ACTIVE")
            .order_by(P89ManagedListing.listed_at.desc())
            .limit(_SECTION_LIMIT)
        ).all()
    )
    active_listings = []
    for row in active_rows:
        copy = session.get(InventoryCopy, row.inventory_copy_id)
        listed = row.listed_at
        days = None
        needs_review = False
        if listed is not None:
            if listed.tzinfo is None:
                listed = listed.replace(tzinfo=timezone.utc)
            days = max(0, (now - listed).days)
            needs_review = days >= STALE_LISTING_DAYS
        active_listings.append(
            SellCommandCenterActiveListingRead(
                listing_id=int(row.id or 0),
                comic_title=_comic_title(session, copy=copy, fallback=row.title),
                marketplace=row.marketplace,
                asking_price=row.asking_price,
                minimum_price=row.minimum_price,
                listed_at=row.listed_at,
                days_listed=days,
                needs_review=needs_review,
                cta_route=f"/listing-management/{int(row.id or 0)}",
            )
        )

    sold_cutoff = now - timedelta(days=SOLD_RECENT_DAYS)
    sold_rows = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "SOLD")
            .where(P89ManagedListing.sold_at >= sold_cutoff)
            .order_by(P89ManagedListing.sold_at.desc())
            .limit(_SECTION_LIMIT)
        ).all()
    )
    sold_recently = []
    for row in sold_rows:
        copy = session.get(InventoryCopy, row.inventory_copy_id)
        sold_recently.append(
            SellCommandCenterSoldRead(
                listing_id=int(row.id or 0),
                comic_title=_comic_title(session, copy=copy, fallback=row.title),
                sale_price=row.sale_price,
                net_profit=row.net_profit,
                profit_known=row.net_profit is not None,
                sold_at=row.sold_at,
                cta_route=f"/listing-management/{int(row.id or 0)}",
            )
        )

    expired_or_stale: list[SellCommandCenterStaleRead] = []
    expired_rows = list(
        session.exec(
            select(P89ManagedListing)
            .where(P89ManagedListing.owner_user_id == owner_user_id)
            .where(P89ManagedListing.status == "EXPIRED")
            .order_by(P89ManagedListing.updated_at.desc())
            .limit(_SECTION_LIMIT)
        ).all()
    )
    for row in expired_rows:
        copy = session.get(InventoryCopy, row.inventory_copy_id)
        expired_or_stale.append(
            SellCommandCenterStaleRead(
                listing_id=int(row.id or 0),
                comic_title=_comic_title(session, copy=copy, fallback=row.title),
                status="EXPIRED",
                marketplace=row.marketplace,
                reason="Listing expired — review or archive.",
                cta_route=f"/listing-management/{int(row.id or 0)}",
            )
        )
    for row in active_rows:
        copy = session.get(InventoryCopy, row.inventory_copy_id)
        listed = row.listed_at
        if listed is None:
            continue
        if listed.tzinfo is None:
            listed = listed.replace(tzinfo=timezone.utc)
        if (now - listed).days >= STALE_LISTING_DAYS:
            expired_or_stale.append(
                SellCommandCenterStaleRead(
                    listing_id=int(row.id or 0),
                    comic_title=_comic_title(session, copy=copy, fallback=row.title),
                    status="ACTIVE",
                    marketplace=row.marketplace,
                    reason=f"Active listing older than {STALE_LISTING_DAYS} days.",
                    cta_route=f"/listing-management/{int(row.id or 0)}",
                )
            )
    draft_stale_cutoff = now - timedelta(days=STALE_DRAFT_DAYS)
    for d in draft_rows:
        created = d.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created <= draft_stale_cutoff:
            copy = session.get(InventoryCopy, d.inventory_copy_id)
            expired_or_stale.append(
                SellCommandCenterStaleRead(
                    draft_id=int(d.id or 0),
                    comic_title=_comic_title(session, copy=copy, fallback=d.title),
                    status="DRAFT",
                    marketplace=d.marketplace,
                    reason=f"Draft older than {STALE_DRAFT_DAYS} days.",
                    cta_route=f"/listing-drafts/{int(d.id or 0)}",
                )
            )

    profit_summary = _profit_summary(session, owner_user_id=owner_user_id)
    daily_actions = _build_daily_actions(
        sell_now=sell_now,
        grade_first=grade_first,
        drafts=drafts_needing_review,
        active=active_listings,
        stale=expired_or_stale,
    )
    dashboard = SellCommandCenterRead(
        kpis=kpis,
        daily_actions=daily_actions,
        sell_now=sell_now,
        grade_first=grade_first,
        hold_or_monitor=hold_or_monitor,
        drafts_needing_review=drafts_needing_review,
        active_listings=active_listings,
        sold_recently=sold_recently,
        expired_or_stale=expired_or_stale[:_SECTION_LIMIT],
        profit_summary=profit_summary,
        quick_actions=_quick_actions(),
        generated_at=now,
    )
    dashboard.briefing_summary = build_sell_command_center_briefing_summary(dashboard)
    return dashboard


def build_sell_command_center_briefing_section(session: Session, *, owner_user_id: int) -> dict:
    dash = build_sell_command_center(session, owner_user_id=owner_user_id)
    summary = dash.briefing_summary
    return {
        "top_sell_candidate": summary.top_sell_candidate,
        "top_grade_first_candidate": summary.top_grade_first_candidate,
        "drafts_awaiting_review": summary.drafts_awaiting_review,
        "active_listings": summary.active_listings,
        "sold_this_month": summary.sold_this_month,
        "net_profit_this_month": summary.net_profit_this_month,
    }
