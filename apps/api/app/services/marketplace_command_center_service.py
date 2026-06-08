"""P88-05 Marketplace Command Center aggregation (cached DB only, no live search)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.models.p88_marketplace_monitoring import MarketplaceAlert, MarketplaceSavedSearch
from app.schemas.p88_marketplace_command_center import (
    BestDealTodayRead,
    CollectionGapFeedRead,
    MarketplaceActivityItemRead,
    MarketplaceCommandCenterBriefingSummaryRead,
    MarketplaceCommandCenterKpiRead,
    MarketplaceCommandCenterQuickActionRead,
    MarketplaceCommandCenterRead,
    PriceDropRead,
    TopRecommendationRead,
    UpcomingReleaseBuyRead,
    WatchlistMatchRead,
)
from app.services.collection_gaps import list_collection_gaps
from app.services.marketplace.marketplace_registry import marketplace_display_name
from app.services.marketplace_acquisition_service import list_acquisition_opportunities
from app.services.p81_discovery_personalization_service import list_future_pull_list


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _upside_percent(price: float, fmv: float) -> float | None:
    if price <= 0 or fmv <= 0 or fmv <= price:
        return None
    return round((fmv - price) / price * 100.0, 1)


def _gap_reason(gap_type: str, rationale: str) -> str:
    mapping = {
        "MISSING_ISSUE": "Missing issue",
        "RUN_GAP": "Run completion",
        "KEY_MISSING": "Key issue gap",
        "MILESTONE_MISSING": "Milestone gap",
    }
    base = mapping.get(gap_type, "Collection gap")
    if rationale.strip():
        return f"{base}: {rationale.strip()[:160]}"
    return base


def _future_recommendation_label(action: str, category: str) -> str:
    action = (action or "").upper()
    category = (category or "").upper()
    if action == "BUY" or category in {"MUST_BUY", "HIGH_PRIORITY"}:
        return "Strong Buy"
    if category == "WATCH":
        return "Watch"
    if "SPEC" in category:
        return "Spec Buy"
    return "Watch"


def _quick_actions() -> list[MarketplaceCommandCenterQuickActionRead]:
    return [
        MarketplaceCommandCenterQuickActionRead(
            label="Run Marketplace Monitoring",
            route="/marketplace-monitoring",
            action_type="RUN_MONITORING",
        ),
        MarketplaceCommandCenterQuickActionRead(
            label="View Buy Opportunities",
            route="/buy-opportunities",
            action_type="VIEW_BUY_OPPORTUNITIES",
        ),
        MarketplaceCommandCenterQuickActionRead(
            label="View Marketplace Alerts",
            route="/marketplace-monitoring",
            action_type="VIEW_ALERTS",
        ),
        MarketplaceCommandCenterQuickActionRead(
            label="View Saved Searches",
            route="/marketplace-monitoring",
            action_type="VIEW_SAVED_SEARCHES",
        ),
        MarketplaceCommandCenterQuickActionRead(
            label="Review Collection Gaps",
            route="/collection-gaps",
            action_type="VIEW_COLLECTION_GAPS",
        ),
    ]


def _count_kpis(session: Session, *, owner_user_id: int) -> MarketplaceCommandCenterKpiRead:
    active_opportunities = int(
        session.exec(
            select(func.count())
            .select_from(MarketplaceAcquisitionOpportunity)
            .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
        ).one()
        or 0
    )
    marketplace_alerts = int(
        session.exec(
            select(func.count())
            .select_from(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.status == "NEW")
        ).one()
        or 0
    )
    price_drops = int(
        session.exec(
            select(func.count())
            .select_from(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.alert_type == "PRICE_DROP")
            .where(MarketplaceAlert.status == "NEW")
        ).one()
        or 0
    )
    if price_drops == 0:
        price_drops = int(
            session.exec(
                select(func.count())
                .select_from(P88MarketplaceListing)
                .where(P88MarketplaceListing.owner_user_id == owner_user_id)
                .where(P88MarketplaceListing.is_active.is_(True))
                .where(P88MarketplaceListing.previous_price.isnot(None))
                .where(P88MarketplaceListing.previous_price > P88MarketplaceListing.price)
            ).one()
            or 0
        )
    watchlist_matches = int(
        session.exec(
            select(func.count())
            .select_from(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.alert_type.in_(("WATCHLIST_MATCH", "NEW_LISTING")))  # type: ignore[attr-defined]
            .where(MarketplaceAlert.status == "NEW")
        ).one()
        or 0
    )
    gaps, _ = list_collection_gaps(session, owner_user_id=owner_user_id, limit=500, offset=0)
    future = list_future_pull_list(session, owner_user_id=owner_user_id, limit=200, offset=0, refresh=False)
    return MarketplaceCommandCenterKpiRead(
        active_opportunities=active_opportunities,
        marketplace_alerts=marketplace_alerts,
        price_drops=price_drops,
        watchlist_matches=watchlist_matches,
        collection_gaps=len(gaps),
        upcoming_releases=future.total_items,
    )


def _best_deal_action_for_opportunity(o) -> tuple[bool, str, str, float, str | None, str | None]:
    verified = getattr(o, "best_verified_listing", None)
    has_verified = bool(getattr(o, "has_verified_listings", False) and verified and verified.listing_url)
    if has_verified and verified:
        url = str(verified.listing_url)
        price = float(verified.total_cost if verified.total_cost is not None else verified.price)
        mp = verified.marketplace_name or verified.marketplace
        return True, url, "MARKETPLACE_LISTING", price, verified.marketplace, mp
    opp_id = int(getattr(o, "id", 0) or 0)
    title = (getattr(o, "title", None) or "").strip()
    if title:
        from urllib.parse import quote

        return False, f"/buy-opportunities?search={quote(title)}", "MARKETPLACE_SEARCH", float(
            o.best_active_price if o.best_active_price is not None else o.asking_price
        ), getattr(o, "best_marketplace", None) or getattr(o, "listing_marketplace", None) or getattr(o, "marketplace", None), getattr(
            o, "best_marketplace_name", None
        )
    return (
        False,
        f"/marketplace-opportunity/{opp_id}",
        "OPPORTUNITY_DETAIL",
        float(o.best_active_price if o.best_active_price is not None else o.asking_price),
        getattr(o, "best_marketplace", None) or getattr(o, "listing_marketplace", None) or getattr(o, "marketplace", None),
        getattr(o, "best_marketplace_name", None),
    )


def _build_best_deals(opportunities) -> list[BestDealTodayRead]:
    candidates = [
        o
        for o in opportunities
        if o.recommendation in {"STRONG_BUY", "GOOD_BUY", "WATCH"} and o.status == "ACTIVE"
    ]

    def sort_key(o) -> tuple[int, float, float]:
        has_v = bool(getattr(o, "has_verified_listings", False) and getattr(o, "best_verified_listing", None))
        _, _, _, price, _, _ = _best_deal_action_for_opportunity(o)
        upside = _upside_percent(price, float(o.estimated_fmv)) or 0.0
        return (-1 if has_v else 0, -float(o.opportunity_score), -upside)

    candidates.sort(key=sort_key)
    deals: list[BestDealTodayRead] = []
    for o in candidates[:10]:
        has_verified, action_url, action_type, price, marketplace, marketplace_name = _best_deal_action_for_opportunity(o)
        if not marketplace_name and marketplace:
            marketplace_name = marketplace_display_name(str(marketplace))
        deals.append(
            BestDealTodayRead(
                opportunity_id=o.id,
                title=o.title or f"{o.series} #{o.issue}".strip(),
                marketplace=marketplace,
                marketplace_name=marketplace_name or (marketplace_display_name(str(marketplace)) if marketplace else None),
                price=round(price, 2),
                fmv=round(float(o.estimated_fmv), 2),
                upside_percent=_upside_percent(price, float(o.estimated_fmv)),
                savings_vs_highest=o.savings_vs_highest,
                opportunity_score=float(o.opportunity_score),
                recommendation=o.recommendation,
                has_verified_listing=has_verified,
                action_url=action_url,
                action_url_type=action_type,
            )
        )
    return deals


def _build_price_drops(session: Session, *, owner_user_id: int) -> list[PriceDropRead]:
    rows = session.exec(
        select(P88MarketplaceListing)
        .where(P88MarketplaceListing.owner_user_id == owner_user_id)
        .where(P88MarketplaceListing.is_active.is_(True))
        .where(P88MarketplaceListing.health_status == "ACTIVE")
        .where(P88MarketplaceListing.previous_price.isnot(None))
        .where(P88MarketplaceListing.previous_price > P88MarketplaceListing.price)
        .order_by(P88MarketplaceListing.updated_at.desc())
        .limit(20)
    ).all()
    drops: list[PriceDropRead] = []
    for row in rows:
        old = float(row.previous_price or 0)
        new = float(row.price)
        if old <= new or old <= 0:
            continue
        drop_pct = round((old - new) / old * 100.0, 1)
        drops.append(
            PriceDropRead(
                opportunity_id=row.opportunity_id,
                listing_id=int(row.id or 0),
                title=row.title or "Listing",
                marketplace=row.marketplace,
                marketplace_name=row.marketplace_name or marketplace_display_name(row.marketplace),
                old_price=round(old, 2),
                new_price=round(new, 2),
                drop_percent=drop_pct,
            )
        )
    drops.sort(key=lambda item: item.drop_percent, reverse=True)
    return drops[:10]


def _build_watchlist_matches(session: Session, *, owner_user_id: int) -> list[WatchlistMatchRead]:
    alerts = session.exec(
        select(MarketplaceAlert)
        .where(MarketplaceAlert.owner_user_id == owner_user_id)
        .where(MarketplaceAlert.alert_type.in_(("WATCHLIST_MATCH", "NEW_LISTING", "PRICE_DROP")))  # type: ignore[attr-defined]
        .order_by(MarketplaceAlert.created_at.desc())
        .limit(30)
    ).all()
    if not alerts:
        return []
    search_ids = {a.saved_search_id for a in alerts if a.saved_search_id}
    searches: dict[int, MarketplaceSavedSearch] = {}
    if search_ids:
        for search in session.exec(
            select(MarketplaceSavedSearch).where(MarketplaceSavedSearch.id.in_(search_ids))  # type: ignore[attr-defined]
        ).all():
            if search.id is not None:
                searches[int(search.id)] = search
    listing_ids = {a.listing_id for a in alerts if a.listing_id}
    listings: dict[int, P88MarketplaceListing] = {}
    if listing_ids:
        for listing in session.exec(
            select(P88MarketplaceListing).where(P88MarketplaceListing.id.in_(listing_ids))  # type: ignore[attr-defined]
        ).all():
            if listing.id is not None:
                listings[int(listing.id)] = listing
    matches: list[WatchlistMatchRead] = []
    for alert in alerts[:10]:
        listing = listings.get(int(alert.listing_id or 0)) if alert.listing_id else None
        search = searches.get(int(alert.saved_search_id or 0)) if alert.saved_search_id else None
        marketplace = listing.marketplace if listing else None
        matches.append(
            WatchlistMatchRead(
                alert_id=int(alert.id or 0),
                saved_search_name=search.name if search else "Saved search",
                title=alert.title,
                marketplace=marketplace,
                marketplace_name=marketplace_display_name(marketplace) if marketplace else None,
                price=float(listing.price + listing.shipping_cost) if listing else None,
                message=alert.message,
                alert_type=alert.alert_type,
            )
        )
    return matches


def _build_upcoming(future_items) -> list[UpcomingReleaseBuyRead]:
    rows: list[UpcomingReleaseBuyRead] = []
    for item in future_items[:10]:
        rows.append(
            UpcomingReleaseBuyRead(
                item_id=item.id,
                title=item.title,
                release_date=item.release_date,
                foc_date=item.foc_date,
                recommendation=_future_recommendation_label(
                    item.recommendation_action,
                    item.priority_category,
                ),
                personalized_score=float(item.personalized_score),
            )
        )
    return rows


def _build_top_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    opportunities,
) -> list[TopRecommendationRead]:
    ranked = sorted(opportunities, key=lambda o: -float(o.opportunity_score))[:10]
    listing_ids = [o.best_listing_id for o in ranked if o.best_listing_id]
    images: dict[int, str] = {}
    if listing_ids:
        for row in session.exec(
            select(P88MarketplaceListing).where(P88MarketplaceListing.id.in_(listing_ids))  # type: ignore[attr-defined]
        ).all():
            if row.id is not None:
                images[int(row.id)] = row.image_url or ""
    recs: list[TopRecommendationRead] = []
    for o in ranked:
        price = o.best_active_price if o.best_active_price is not None else o.asking_price
        reasons = list(o.reasons or [])
        recs.append(
            TopRecommendationRead(
                opportunity_id=o.id,
                title=o.title or f"{o.series} #{o.issue}".strip(),
                cover_image_url=images.get(int(o.best_listing_id or 0), ""),
                score=float(o.opportunity_score),
                reason_summary=reasons[0] if reasons else "ComicOS buy recommendation",
                best_marketplace_name=o.best_marketplace_name
                or (marketplace_display_name(str(o.listing_marketplace)) if o.listing_marketplace else None),
                best_price=round(float(price), 2) if price is not None else None,
                recommendation=o.recommendation,
            )
        )
    return recs


def _build_activity(alerts: list[MarketplaceAlert]) -> list[MarketplaceActivityItemRead]:
    return [
        MarketplaceActivityItemRead(
            activity_type=row.alert_type,
            title=row.title,
            message=row.message,
            created_at=row.created_at,
        )
        for row in alerts[:12]
    ]


def build_marketplace_command_center_briefing_summary(
    dashboard: MarketplaceCommandCenterRead,
) -> MarketplaceCommandCenterBriefingSummaryRead:
    best_deal = dashboard.best_deals_today[0].title if dashboard.best_deals_today else None
    largest_drop = dashboard.price_drops[0].title if dashboard.price_drops else None
    top_rec = dashboard.top_recommendations[0].title if dashboard.top_recommendations else None
    watch = dashboard.watchlist_matches[0].title if dashboard.watchlist_matches else None
    return MarketplaceCommandCenterBriefingSummaryRead(
        best_deal_title=best_deal,
        largest_price_drop_title=largest_drop,
        top_recommendation_title=top_rec,
        watchlist_match_title=watch,
    )


def build_marketplace_command_center(session: Session, *, owner_user_id: int) -> MarketplaceCommandCenterRead:
    kpis = _count_kpis(session, owner_user_id=owner_user_id)
    opportunities = list_acquisition_opportunities(
        session,
        owner_user_id=owner_user_id,
        limit=120,
        offset=0,
        refresh=False,
    ).items
    future = list_future_pull_list(session, owner_user_id=owner_user_id, limit=30, offset=0, refresh=False)
    gaps, _ = list_collection_gaps(session, owner_user_id=owner_user_id, limit=10, offset=0)
    gap_feed = [
        CollectionGapFeedRead(
            gap_id=g.id,
            title=f"{g.series_name} #{g.issue_number}".strip(),
            reason=_gap_reason(g.gap_type, g.rationale),
            gap_type=g.gap_type,
            priority=g.priority,
        )
        for g in gaps
    ]
    recent_alerts = list(
        session.exec(
            select(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .order_by(MarketplaceAlert.created_at.desc())
            .limit(12)
        ).all()
    )
    dashboard = MarketplaceCommandCenterRead(
        kpis=kpis,
        best_deals_today=_build_best_deals(opportunities),
        price_drops=_build_price_drops(session, owner_user_id=owner_user_id),
        collection_gaps=gap_feed,
        watchlist_matches=_build_watchlist_matches(session, owner_user_id=owner_user_id),
        upcoming_releases=_build_upcoming(future.items),
        top_recommendations=_build_top_recommendations(
            session,
            owner_user_id=owner_user_id,
            opportunities=opportunities,
        ),
        marketplace_activity=_build_activity(recent_alerts),
        quick_actions=_quick_actions(),
        generated_at=_utc_now(),
    )
    dashboard.briefing_summary = build_marketplace_command_center_briefing_summary(dashboard)
    return dashboard


def build_marketplace_command_center_briefing_section(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, str | None]:
    """Lightweight briefing hook (single aggregation pass)."""
    body = build_marketplace_command_center(session, owner_user_id=owner_user_id)
    summary = body.briefing_summary
    return {
        "best_deal": summary.best_deal_title,
        "largest_price_drop": summary.largest_price_drop_title,
        "top_recommendation": summary.top_recommendation_title,
        "watchlist_match": summary.watchlist_match_title,
    }
