from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceDefinition:
    marketplace_key: str
    display_name: str
    status: str
    capability_flags: tuple[str, ...]


_MARKETPLACE_DEFINITIONS: tuple[MarketplaceDefinition, ...] = (
    MarketplaceDefinition(
        marketplace_key="ebay",
        display_name="eBay",
        status="supported",
        capability_flags=(
            "account_connect",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "listing_sync_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
    MarketplaceDefinition(
        marketplace_key="whatnot",
        display_name="Whatnot",
        status="supported",
        capability_flags=(
            "account_connect",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "livestream_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
    MarketplaceDefinition(
        marketplace_key="shopify",
        display_name="Shopify",
        status="supported",
        capability_flags=(
            "account_connect",
            "catalog_sync_contract_reserved",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
)

_MARKETPLACE_BY_KEY = {definition.marketplace_key: definition for definition in _MARKETPLACE_DEFINITIONS}


def list_marketplace_definitions() -> tuple[MarketplaceDefinition, ...]:
    return _MARKETPLACE_DEFINITIONS


def get_marketplace_definition(marketplace_key: str) -> MarketplaceDefinition | None:
    return _MARKETPLACE_BY_KEY.get(marketplace_key.strip().lower())
