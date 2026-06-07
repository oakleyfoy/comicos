"""P88-02 orchestrate live marketplace search for buy opportunities."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import MarketplaceSearchRun, utc_now
from app.schemas.p88_marketplace_live import MarketplaceSearchMarketplaceResponse
from app.services.marketplace.adapters.adapter_registry import get_marketplace_adapter
from app.services.marketplace.best_buy_notification_service import maybe_notify_best_buy
from app.services.marketplace.marketplace_listing_service import (
    sync_opportunity_best_listing,
    upsert_listing_from_search,
)
from app.services.marketplace.marketplace_opportunity_matcher import candidate_searches_for_opportunity


def run_marketplace_search_for_user(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_ids: list[int] | None = None,
    search_limit: int = 15,
    settings: Settings | None = None,
) -> MarketplaceSearchMarketplaceResponse:
    resolved = settings or get_settings()
    query = select(MarketplaceAcquisitionOpportunity).where(
        MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id
    )
    if opportunity_ids:
        query = query.where(MarketplaceAcquisitionOpportunity.id.in_(opportunity_ids))  # type: ignore[attr-defined]
    opportunities = session.exec(query).all()

    searches_run = 0
    listings_found = 0
    new_listings = 0
    updated_listings = 0
    failed_searches = 0
    errors: list[str] = []
    global_queries: set[str] = set()

    for opp in opportunities:
        for search_text in candidate_searches_for_opportunity(opp):
            key = search_text.lower()
            if key in global_queries:
                continue
            global_queries.add(key)
            searches_run += 1
            adapter = get_marketplace_adapter("EBAY")
            result = adapter.search(
                query=search_text,
                series=opp.series or None,
                issue_number=opp.issue or None,
                publisher=opp.publisher or None,
                limit=search_limit,
                settings=resolved,
            )
            if result.status == "NOT_SUPPORTED":
                failed_searches += 1
                errors.append(f"{search_text}: marketplace search not supported.")
                continue
            if result.status == "ERROR":
                failed_searches += 1
                errors.append(f"{search_text}: {result.error or 'search failed'}")
                continue
            results = list(result.listings)

            listings_found += len(results)
            for normalized in results:
                try:
                    _, created = upsert_listing_from_search(
                        session,
                        owner_user_id=owner_user_id,
                        opportunity_id=int(opp.id) if opp.id else None,
                        normalized=normalized,
                    )
                    if created:
                        new_listings += 1
                    else:
                        updated_listings += 1
                except ValueError:
                    continue
        sync_opportunity_best_listing(session, opportunity=opp)
        maybe_notify_best_buy(session, owner_user_id=owner_user_id, opportunity=opp)

    run = MarketplaceSearchRun(
        owner_user_id=owner_user_id,
        searches_run=searches_run,
        listings_found=listings_found,
        new_listings=new_listings,
        updated_listings=updated_listings,
        failed_searches=failed_searches,
        errors_json=errors[:50],
        created_at=utc_now(),
    )
    session.add(run)
    session.flush()

    return MarketplaceSearchMarketplaceResponse(
        listings_found=listings_found,
        new_listings=new_listings,
        updated_listings=updated_listings,
        failed_searches=failed_searches,
        searches_run=searches_run,
        errors=errors[:20],
    )
