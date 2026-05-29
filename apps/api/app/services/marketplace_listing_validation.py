from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session

from app.models import InventoryCopy, MarketplaceAccount, MarketplaceListingDraft
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.organization_inventory_access import validate_org_inventory_membership

LISTING_STATUS_DRAFT = "draft"
LISTING_STATUS_READY = "ready"
LISTING_STATUS_ARCHIVED = "archived"
LISTING_STATUSES = {LISTING_STATUS_DRAFT, LISTING_STATUS_READY, LISTING_STATUS_ARCHIVED}
LISTING_STATUSES_MUTABLE = {LISTING_STATUS_DRAFT, LISTING_STATUS_READY}

VALIDATION_STATUS_PENDING = "pending"
VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_INVALID = "invalid"


@dataclass(frozen=True)
class ListingValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ListingValidationResult:
    validation_status: str
    errors: tuple[ListingValidationError, ...]


def _error(code: str, message: str) -> ListingValidationError:
    return ListingValidationError(code=code, message=message)


def resolve_listing_validation_errors(errors: tuple[ListingValidationError, ...]) -> list[ListingValidationError]:
    return sorted(errors, key=lambda row: (row.code, row.message))


def validate_marketplace_account_listing_access(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int,
) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    if account.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Marketplace account is outside organization scope.")
    if account.account_status != ACCOUNT_STATUS_CONNECTED:
        return account
    return account


def validate_inventory_listing_eligibility(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> InventoryCopy:
    return validate_org_inventory_membership(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
    )


def validate_listing_draft(
    session: Session,
    *,
    organization_id: int,
    draft: MarketplaceListingDraft,
    marketplace_account: MarketplaceAccount | None = None,
    inventory: InventoryCopy | None = None,
) -> ListingValidationResult:
    errors: list[ListingValidationError] = []

    if draft.organization_id != organization_id:
        errors.append(_error("organization_mismatch", "Listing draft organization does not match request scope."))

    account = marketplace_account
    if account is None:
        account = session.get(MarketplaceAccount, draft.marketplace_account_id)
    if account is None:
        errors.append(_error("marketplace_account_not_found", "Marketplace account is missing."))
    elif account.organization_id != organization_id:
        errors.append(_error("marketplace_account_out_of_scope", "Marketplace account is outside organization scope."))
    elif account.account_status != ACCOUNT_STATUS_CONNECTED:
        errors.append(_error("marketplace_account_disconnected", "Marketplace account must be connected for listings."))

    inv = inventory
    if inv is None:
        inv = session.get(InventoryCopy, draft.inventory_item_id)
    if inv is None:
        errors.append(_error("inventory_not_found", "Inventory item is missing."))
    else:
        try:
            validate_org_inventory_membership(
                session,
                organization_id=organization_id,
                inventory_item_id=int(draft.inventory_item_id),
            )
        except HTTPException:
            errors.append(_error("inventory_out_of_scope", "Inventory item is outside organization scope."))

    title = (draft.listing_title or "").strip()
    if not title:
        errors.append(_error("listing_title_required", "Listing title is required."))

    if draft.listing_price is None:
        errors.append(_error("listing_price_required", "Listing price is required."))
    elif draft.listing_price < Decimal("0"):
        errors.append(_error("listing_price_invalid", "Listing price must be zero or greater."))

    currency = (draft.listing_currency or "").strip().upper()
    if not currency:
        errors.append(_error("listing_currency_required", "Listing currency is required."))

    if draft.listing_quantity < 1:
        errors.append(_error("listing_quantity_invalid", "Listing quantity must be at least one."))

    if draft.listing_status == LISTING_STATUS_ARCHIVED:
        errors.append(_error("listing_status_archived", "Archived listing drafts cannot be published or projected."))
    elif draft.listing_status not in LISTING_STATUSES:
        errors.append(_error("listing_status_invalid", "Listing status is not supported."))

    ordered = tuple(resolve_listing_validation_errors(tuple(errors)))
    if ordered:
        return ListingValidationResult(validation_status=VALIDATION_STATUS_INVALID, errors=ordered)
    if draft.listing_status == LISTING_STATUS_READY:
        return ListingValidationResult(validation_status=VALIDATION_STATUS_VALID, errors=tuple())
    return ListingValidationResult(validation_status=VALIDATION_STATUS_PENDING, errors=tuple())
