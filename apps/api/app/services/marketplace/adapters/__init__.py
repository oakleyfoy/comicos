"""P88-04 marketplace adapters."""

from app.services.marketplace.adapters.adapter_registry import get_marketplace_adapter
from app.services.marketplace.adapters.base import (
    AdapterOperationResult,
    MarketplaceAdapter,
    UnifiedMarketplaceListing,
)

__all__ = [
    "AdapterOperationResult",
    "MarketplaceAdapter",
    "UnifiedMarketplaceListing",
    "get_marketplace_adapter",
]
