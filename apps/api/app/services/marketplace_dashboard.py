from __future__ import annotations

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceCapability, MarketplaceCredential, MarketplaceDefinition
from app.schemas.marketplace_dashboard import (
    MarketplaceAccountHealthListResponse,
    MarketplaceAccountHealthRead,
    MarketplaceConnectorReadinessListResponse,
    MarketplaceConnectorReadinessRead,
    MarketplaceDashboardSummaryRead,
)
from app.services.marketplace_health import (
    HEALTH_STATUS_DISABLED,
    HEALTH_STATUS_FAILED,
    HEALTH_STATUS_HEALTHY,
    HEALTH_STATUS_WARNING,
    get_marketplace_health,
)
from app.services.marketplace_analytics import get_marketplace_analytics
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.marketplace_validation import validate_marketplace_platform

_IMPLEMENTATION_CONNECTOR_CODES = frozenset({"WHATNOT", "SHOPIFY"})


def _connector_health(*, enabled: bool, capability_count: int, implementation_ready: bool) -> str:
    if not implementation_ready:
        return HEALTH_STATUS_DISABLED
    if enabled and capability_count > 0:
        return HEALTH_STATUS_HEALTHY
    if capability_count > 0:
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_FAILED


def list_connector_readiness(session: Session, *, owner_id: int) -> MarketplaceConnectorReadinessListResponse:
    ensure_marketplace_definitions(session)
    definitions = session.exec(select(MarketplaceDefinition).order_by(MarketplaceDefinition.marketplace_code.asc())).all()
    capability_rows = session.exec(select(MarketplaceCapability)).all()
    caps_by_marketplace: dict[int, int] = {}
    for cap in capability_rows:
        marketplace_id = int(cap.marketplace_id or 0)
        caps_by_marketplace[marketplace_id] = caps_by_marketplace.get(marketplace_id, 0) + 1

    items = []
    for definition in definitions:
        marketplace_id = int(definition.id or 0)
        implementation_ready = definition.marketplace_code in _IMPLEMENTATION_CONNECTOR_CODES
        capability_count = caps_by_marketplace.get(marketplace_id, 0)
        health_status = _connector_health(
            enabled=bool(definition.enabled),
            capability_count=capability_count,
            implementation_ready=implementation_ready,
        )
        summary = (
            f"{definition.marketplace_code} connector is implementation-ready."
            if implementation_ready
            else f"{definition.marketplace_code} connector is reserved for future work."
        )
        items.append(
            MarketplaceConnectorReadinessRead(
                marketplace_id=marketplace_id,
                marketplace_code=definition.marketplace_code,
                marketplace_name=definition.marketplace_name,
                enabled=bool(definition.enabled),
                implementation_ready=implementation_ready,
                capability_count=capability_count,
                health_status=health_status,
                summary=summary,
            )
        )
    return MarketplaceConnectorReadinessListResponse(items=items, total_items=len(items))


def list_account_health(session: Session, *, owner_id: int) -> MarketplaceAccountHealthListResponse:
    ensure_marketplace_definitions(session)
    accounts = session.exec(
        select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_id).order_by(MarketplaceAccount.id.asc())
    ).all()
    definitions = {
        int(row.id or 0): row
        for row in session.exec(select(MarketplaceDefinition)).all()
    }
    credential_rows = session.exec(select(MarketplaceCredential)).all()
    creds_by_account = {int(row.account_id or 0) for row in credential_rows}

    items: list[MarketplaceAccountHealthRead] = []
    for account in accounts:
        account_id = int(account.id or 0)
        definition = definitions.get(int(account.marketplace_id or 0))
        credentials_present = account_id in creds_by_account
        if account.status != "ACTIVE":
            health_status = HEALTH_STATUS_DISABLED
        elif not credentials_present:
            health_status = HEALTH_STATUS_FAILED
        else:
            health_status = HEALTH_STATUS_HEALTHY
        items.append(
            MarketplaceAccountHealthRead(
                account_id=account_id,
                marketplace_id=int(account.marketplace_id or 0),
                marketplace_code=definition.marketplace_code if definition else "UNKNOWN",
                account_name=account.account_name,
                status=account.status,
                health_status=health_status,
                credentials_present=credentials_present,
                summary=f"{account.account_name} is {account.status.lower()} with credentials {'present' if credentials_present else 'missing'}.",
            )
        )
    return MarketplaceAccountHealthListResponse(items=items, total_items=len(items))


def get_marketplace_dashboard(session: Session, *, owner_id: int) -> MarketplaceDashboardSummaryRead:
    validation = validate_marketplace_platform(session, owner_id=owner_id)
    health = get_marketplace_health(session, owner_id=owner_id)
    analytics = get_marketplace_analytics(session, owner_id=owner_id)
    summary_cards = {
        "listings": analytics.marketplace_activity_counts.get("listings_total", 0),
        "publish_jobs": analytics.marketplace_activity_counts.get("publish_jobs_total", 0),
        "orders": analytics.marketplace_activity_counts.get("orders_total", 0),
        "reservations": analytics.marketplace_activity_counts.get("reservations_total", 0),
        "sync_plans": analytics.marketplace_activity_counts.get("sync_plans_total", 0),
    }
    return MarketplaceDashboardSummaryRead(
        validation_status=validation.overall_status,
        health_status=health.overall_status,
        platform_certified=validation.platform_certified,
        summary_cards=summary_cards,
        validation_checks=validation.checks,
        health_components=health.components,
    )
