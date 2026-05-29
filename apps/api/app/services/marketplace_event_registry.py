from __future__ import annotations

from dataclasses import dataclass


EVENT_CATEGORY_LISTING = "listing"
EVENT_CATEGORY_ORDER = "order"
EVENT_CATEGORY_OFFER = "offer"
EVENT_CATEGORY_INVENTORY = "inventory"
EVENT_CATEGORY_ACCOUNT = "account"


@dataclass(frozen=True)
class MarketplaceEventDefinition:
    event_type: str
    display_name: str
    category_key: str
    status: str = "active"
    capability_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketplaceEventCategory:
    category_key: str
    display_name: str
    event_types: tuple[str, ...]


_EVENT_DEFINITIONS = (
    MarketplaceEventDefinition("listing_created", "Listing created", EVENT_CATEGORY_LISTING, capability_flags=("listing",)),
    MarketplaceEventDefinition("listing_updated", "Listing updated", EVENT_CATEGORY_LISTING, capability_flags=("listing",)),
    MarketplaceEventDefinition("listing_removed", "Listing removed", EVENT_CATEGORY_LISTING, capability_flags=("listing",)),
    MarketplaceEventDefinition("order_created", "Order created", EVENT_CATEGORY_ORDER, capability_flags=("order",)),
    MarketplaceEventDefinition("order_updated", "Order updated", EVENT_CATEGORY_ORDER, capability_flags=("order",)),
    MarketplaceEventDefinition("order_cancelled", "Order cancelled", EVENT_CATEGORY_ORDER, capability_flags=("order",)),
    MarketplaceEventDefinition("offer_received", "Offer received", EVENT_CATEGORY_OFFER, capability_flags=("offer",)),
    MarketplaceEventDefinition("offer_updated", "Offer updated", EVENT_CATEGORY_OFFER, capability_flags=("offer",)),
    MarketplaceEventDefinition("inventory_changed", "Inventory changed", EVENT_CATEGORY_INVENTORY, capability_flags=("inventory",)),
    MarketplaceEventDefinition(
        "account_status_changed",
        "Account status changed",
        EVENT_CATEGORY_ACCOUNT,
        capability_flags=("account",),
    ),
)

_EVENT_CATEGORIES = (
    MarketplaceEventCategory(
        EVENT_CATEGORY_LISTING,
        "Listing Events",
        ("listing_created", "listing_updated", "listing_removed"),
    ),
    MarketplaceEventCategory(
        EVENT_CATEGORY_ORDER,
        "Order Events",
        ("order_created", "order_updated", "order_cancelled"),
    ),
    MarketplaceEventCategory(
        EVENT_CATEGORY_OFFER,
        "Offer Events",
        ("offer_received", "offer_updated"),
    ),
    MarketplaceEventCategory(
        EVENT_CATEGORY_INVENTORY,
        "Inventory Events",
        ("inventory_changed",),
    ),
    MarketplaceEventCategory(
        EVENT_CATEGORY_ACCOUNT,
        "Account Events",
        ("account_status_changed",),
    ),
)


def list_marketplace_event_definitions() -> list[MarketplaceEventDefinition]:
    return list(_EVENT_DEFINITIONS)


def list_marketplace_event_categories() -> list[MarketplaceEventCategory]:
    return list(_EVENT_CATEGORIES)


def get_marketplace_event_definition(event_type: str) -> MarketplaceEventDefinition | None:
    normalized = event_type.strip().lower()
    return next((definition for definition in _EVENT_DEFINITIONS if definition.event_type == normalized), None)


def list_marketplace_event_types() -> list[str]:
    return [definition.event_type for definition in _EVENT_DEFINITIONS]
