"""P88-04 best buy notification hooks."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.services.collector_notification_service import _upsert_notification
from app.services.marketplace.best_buy_service import recommend_best_buy
from app.services.marketplace.marketplace_listing_service import listing_summary_for_opportunity
from app.services.marketplace.marketplace_registry import marketplace_display_name

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE_BEST_BUY = "BEST_BUY_FOUND"


def maybe_notify_best_buy(
    session: Session,
    *,
    owner_user_id: int,
    opportunity: MarketplaceAcquisitionOpportunity,
) -> None:
    try:
        assert opportunity.id is not None
        summary = listing_summary_for_opportunity(
            session,
            owner_user_id=owner_user_id,
            opportunity_id=int(opportunity.id),
        )
        if not summary.get("has_verified_listings"):
            return
        marketplace = summary.get("best_marketplace") or summary.get("listing_marketplace")
        if not marketplace:
            return
        display = summary.get("best_marketplace_name") or marketplace_display_name(str(marketplace))
        title = opportunity.title or f"{opportunity.series} #{opportunity.issue}".strip()
        price = summary.get("best_active_price")
        message = f"{title} found cheaper on {display}."
        if price is not None:
            message = f"{title} found on {display} for ${float(price):.2f}."
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type=NOTIFICATION_TYPE_BEST_BUY,
            priority="NORMAL",
            title=message,
            message=summary.get("best_buy_reason") or "Lowest total cost available.",
            action_url=f"/marketplace-opportunity/{opportunity.id}",
            related_entity_type="buy_opportunity",
            related_entity_id=int(opportunity.id),
            reasons=[f"marketplace={marketplace}"],
        )
    except Exception:  # noqa: BLE001
        logger.debug("BEST_BUY_FOUND notification skipped", exc_info=True)
