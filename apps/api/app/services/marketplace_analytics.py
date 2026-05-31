from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceExecution
from app.models.marketplace_listing import MarketplaceListing
from app.models.marketplace_publish import MarketplacePublishJob
from app.models.marketplace_sync import (
    MarketplaceInventoryReservation,
    MarketplaceInventorySyncPlan,
    MarketplaceOrder,
)
from app.schemas.marketplace_dashboard import MarketplaceAnalyticsRead

_IMPLEMENTATION_CONNECTOR_CODES = frozenset({"WHATNOT", "SHOPIFY"})


def _count_by_status(rows: list, *, attr: str = "status") -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = getattr(row, attr, None)
        if value is None:
            continue
        counter[str(value)] += 1
    return dict(sorted(counter.items()))


def get_marketplace_analytics(session: Session, *, owner_id: int) -> MarketplaceAnalyticsRead:
    listings = session.exec(select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_id)).all()
    publish_jobs = session.exec(
        select(MarketplacePublishJob).where(MarketplacePublishJob.owner_id == owner_id)
    ).all()
    orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.owner_id == owner_id)).all()
    reservations = session.exec(
        select(MarketplaceInventoryReservation).where(MarketplaceInventoryReservation.owner_id == owner_id)
    ).all()
    sync_plans = session.exec(
        select(MarketplaceInventorySyncPlan).where(MarketplaceInventorySyncPlan.owner_id == owner_id)
    ).all()
    accounts = session.exec(select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_id)).all()
    account_ids = {int(row.id or 0) for row in accounts}
    executions: list[MarketplaceExecution] = []
    if account_ids:
        executions = session.exec(
            select(MarketplaceExecution).where(MarketplaceExecution.account_id.in_(account_ids))  # type: ignore[attr-defined]
        ).all()

    execution_counts = Counter(row.execution_type for row in executions)
    activity_counts = {
        "listings_total": len(listings),
        "publish_jobs_total": len(publish_jobs),
        "orders_total": len(orders),
        "reservations_total": len(reservations),
        "sync_plans_total": len(sync_plans),
        "linked_accounts_total": len(accounts),
        "executions_total": len(executions),
        "whatnot_executions": sum(
            count for key, count in execution_counts.items() if key in {"PUBLISH", "IMPORT_ORDERS", "SYNC_INVENTORY"}
        ),
        "shopify_executions": sum(
            count for key, count in execution_counts.items() if key in {"PUBLISH", "ARCHIVE", "RESTORE", "IMPORT_ORDERS"}
        ),
        "implementation_connectors": len(_IMPLEMENTATION_CONNECTOR_CODES),
    }

    return MarketplaceAnalyticsRead(
        listings_by_status=_count_by_status(listings),
        publish_jobs_by_status=_count_by_status(publish_jobs),
        orders_by_status=_count_by_status(orders, attr="order_status"),
        reservations_by_status=_count_by_status(reservations),
        sync_plans_by_status=_count_by_status(sync_plans),
        marketplace_activity_counts=activity_counts,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
