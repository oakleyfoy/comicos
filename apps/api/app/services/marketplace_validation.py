from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceCapability, MarketplaceCredential, MarketplaceDefinition
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingMapping
from app.models.marketplace_publish import MarketplacePublishJob
from app.models.marketplace_sync import (
    MarketplaceInventoryAvailability,
    MarketplaceInventoryReservation,
    MarketplaceInventorySyncPlan,
    MarketplaceOrder,
)
from app.schemas.marketplace_dashboard import MarketplaceValidationCheckRead, MarketplaceValidationRead
from app.services.marketplace_seed import MARKETPLACE_SEED_DEFINITIONS, ensure_marketplace_definitions

PLATFORM_STATUS_PASS = "PASS"
PLATFORM_STATUS_WARNING = "WARNING"
PLATFORM_STATUS_FAIL = "FAIL"

_IMPLEMENTATION_CONNECTOR_CODES = frozenset({"WHATNOT", "SHOPIFY"})


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == PLATFORM_STATUS_FAIL for status in statuses):
        return PLATFORM_STATUS_FAIL
    if any(status == PLATFORM_STATUS_WARNING for status in statuses):
        return PLATFORM_STATUS_WARNING
    return PLATFORM_STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> MarketplaceValidationCheckRead:
    return MarketplaceValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_connectors(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    ensure_marketplace_definitions(session)
    rows = session.exec(select(MarketplaceDefinition).order_by(MarketplaceDefinition.marketplace_code.asc())).all()
    codes = {row.marketplace_code for row in rows}
    required_codes = {str(seed["marketplace_code"]) for seed in MARKETPLACE_SEED_DEFINITIONS}
    missing_codes = sorted(required_codes - codes)
    capability_rows = session.exec(select(MarketplaceCapability)).all()
    caps_by_marketplace: dict[int, set[str]] = {}
    for cap in capability_rows:
        caps_by_marketplace.setdefault(int(cap.marketplace_id or 0), set()).add(cap.capability_code)

    missing_capabilities: list[str] = []
    for seed in MARKETPLACE_SEED_DEFINITIONS:
        code = str(seed["marketplace_code"])
        definition = next((row for row in rows if row.marketplace_code == code), None)
        if definition is None:
            continue
        expected = {str(item[0]) for item in seed["capabilities"]}  # type: ignore[index]
        actual = caps_by_marketplace.get(int(definition.id or 0), set())
        if expected - actual:
            missing_capabilities.append(code)

    status = PLATFORM_STATUS_PASS
    if missing_codes or missing_capabilities:
        status = PLATFORM_STATUS_FAIL
    elif not rows:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="connectors",
        title="Connector Framework",
        status=status,
        summary=f"{len(rows)} marketplace definitions validated; {len(_IMPLEMENTATION_CONNECTOR_CODES)} live connectors expected.",
        details_json={
            "owner_id": owner_id,
            "marketplace_count": len(rows),
            "missing_marketplace_codes": missing_codes,
            "marketplaces_missing_capabilities": missing_capabilities,
            "implementation_connector_codes": sorted(_IMPLEMENTATION_CONNECTOR_CODES),
        },
    )


def validate_accounts(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    accounts = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .order_by(MarketplaceAccount.id.asc())
    ).all()
    credential_rows = session.exec(select(MarketplaceCredential)).all()
    creds_by_account = {int(row.account_id or 0) for row in credential_rows}
    active_without_credentials = [
        int(row.id or 0)
        for row in accounts
        if row.status == "ACTIVE" and int(row.id or 0) not in creds_by_account
    ]

    status = PLATFORM_STATUS_PASS
    if active_without_credentials:
        status = PLATFORM_STATUS_FAIL
    elif not accounts:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="accounts",
        title="Marketplace Accounts",
        status=status,
        summary=f"{len(accounts)} marketplace accounts checked for credential coverage.",
        details_json={
            "owner_id": owner_id,
            "account_count": len(accounts),
            "active_accounts_missing_credentials": active_without_credentials,
        },
    )


def validate_listings(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    listings = session.exec(select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_id)).all()
    listing_ids = [int(row.id or 0) for row in listings]
    if listing_ids:
        mappings = session.exec(
            select(MarketplaceListingMapping).where(MarketplaceListingMapping.listing_id.in_(listing_ids))  # type: ignore[attr-defined]
        ).all()
    else:
        mappings = []
    mapped_listing_ids = {row.listing_id for row in mappings if row.external_listing_id}
    published_ready = [row for row in listings if row.status in {"PUBLISHED", "READY_TO_PUBLISH"}]
    published_without_mapping = sorted(
        int(row.id or 0)
        for row in published_ready
        if int(row.id or 0) not in mapped_listing_ids
    )

    status = PLATFORM_STATUS_PASS
    if published_without_mapping:
        status = PLATFORM_STATUS_WARNING
    elif not listings:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="listings",
        title="Canonical Listings",
        status=status,
        summary=f"{len(listings)} listings validated against {len(mappings)} marketplace mappings.",
        details_json={
            "owner_id": owner_id,
            "listing_count": len(listings),
            "mapping_count": len(mappings),
            "published_ready_without_external_mapping": published_without_mapping,
        },
    )


def validate_publish_engine(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    jobs = session.exec(select(MarketplacePublishJob).where(MarketplacePublishJob.owner_id == owner_id)).all()
    status_counts = Counter(row.status for row in jobs)
    failed_jobs = status_counts.get("FAILED", 0)

    status = PLATFORM_STATUS_PASS
    if failed_jobs > 0:
        status = PLATFORM_STATUS_WARNING
    elif not jobs:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="publish_engine",
        title="Publish Engine",
        status=status,
        summary=f"{len(jobs)} publish jobs reviewed; {failed_jobs} failed jobs detected.",
        details_json={
            "owner_id": owner_id,
            "publish_job_count": len(jobs),
            "publish_jobs_by_status": dict(status_counts),
        },
    )


def validate_inventory_sync(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    availability_rows = session.exec(
        select(MarketplaceInventoryAvailability).where(MarketplaceInventoryAvailability.owner_id == owner_id)
    ).all()
    negative_available = [
        int(row.id or 0) for row in availability_rows if int(row.available_quantity) < 0
    ]
    plans = session.exec(
        select(MarketplaceInventorySyncPlan).where(MarketplaceInventorySyncPlan.owner_id == owner_id)
    ).all()
    failed_plans = sum(1 for row in plans if row.status == "FAILED")

    status = PLATFORM_STATUS_PASS
    if negative_available:
        status = PLATFORM_STATUS_FAIL
    elif failed_plans > 0:
        status = PLATFORM_STATUS_WARNING
    elif not availability_rows and not plans:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="inventory_sync",
        title="Inventory Sync",
        status=status,
        summary=f"{len(availability_rows)} availability rows and {len(plans)} sync plans validated.",
        details_json={
            "owner_id": owner_id,
            "availability_count": len(availability_rows),
            "negative_available_row_ids": negative_available,
            "sync_plan_count": len(plans),
            "failed_sync_plan_count": failed_plans,
        },
    )


def validate_order_import(session: Session, *, owner_id: int) -> MarketplaceValidationCheckRead:
    orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.owner_id == owner_id)).all()
    duplicate_keys: list[str] = []
    seen: set[tuple[int | None, str]] = set()
    for order in orders:
        if not order.external_order_id:
            continue
        key = (order.marketplace_account_id, order.external_order_id)
        if key in seen:
            duplicate_keys.append(f"{order.marketplace_account_id}:{order.external_order_id}")
        seen.add(key)

    status = PLATFORM_STATUS_PASS
    if duplicate_keys:
        status = PLATFORM_STATUS_FAIL
    elif not orders:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="order_import",
        title="Order Import",
        status=status,
        summary=f"{len(orders)} marketplace orders checked for duplicate external identifiers.",
        details_json={
            "owner_id": owner_id,
            "order_count": len(orders),
            "duplicate_external_order_keys": sorted(set(duplicate_keys)),
        },
    )


def validate_marketplace_platform(session: Session, *, owner_id: int) -> MarketplaceValidationRead:
    checks = [
        validate_connectors(session, owner_id=owner_id),
        validate_accounts(session, owner_id=owner_id),
        validate_listings(session, owner_id=owner_id),
        validate_publish_engine(session, owner_id=owner_id),
        validate_inventory_sync(session, owner_id=owner_id),
        validate_order_import(session, owner_id=owner_id),
    ]
    overall = _aggregate_status([check.status for check in checks])
    return MarketplaceValidationRead(
        overall_status=overall,
        platform_certified=overall == PLATFORM_STATUS_PASS,
        checks=checks,
    )
