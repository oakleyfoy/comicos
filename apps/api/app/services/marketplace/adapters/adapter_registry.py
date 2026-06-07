"""Resolve marketplace code to adapter instance."""

from __future__ import annotations

from app.services.marketplace.adapters.base import MarketplaceAdapter
from app.services.marketplace.adapters.ebay_adapter import EbayMarketplaceAdapter
from app.services.marketplace.adapters.shell_adapter import ShellMarketplaceAdapter
from app.services.marketplace.marketplace_registry import MARKETPLACE_REGISTRY, MarketplaceCode

_ADAPTERS: dict[str, MarketplaceAdapter] = {
    "EBAY": EbayMarketplaceAdapter(),
}


def get_marketplace_adapter(code: str) -> MarketplaceAdapter:
    key = str(code).strip().upper()
    if key in _ADAPTERS:
        return _ADAPTERS[key]
    if key in MARKETPLACE_REGISTRY and key not in ("OTHER", "WHATNOT"):
        shell = ShellMarketplaceAdapter(key)
        _ADAPTERS[key] = shell
        return shell
    return ShellMarketplaceAdapter("OTHER")
