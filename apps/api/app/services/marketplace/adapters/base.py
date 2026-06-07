"""P88-04 marketplace adapter interface (no scraping)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.core.config import Settings
from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing

AdapterOperationStatus = Literal["OK", "NOT_SUPPORTED", "ERROR"]

AvailabilityStatus = Literal["ACTIVE", "OUT_OF_STOCK", "ENDED", "UNKNOWN"]
ListingConfidence = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True)
class AdapterOperationResult:
    status: AdapterOperationStatus
    listings: tuple[NormalizedMarketplaceListing, ...] = ()
    listing: NormalizedMarketplaceListing | None = None
    error: str | None = None


@dataclass(frozen=True)
class UnifiedMarketplaceListing:
    """Shared listing shape returned by adapters after normalize()."""

    marketplace: str
    marketplace_name: str
    item_id: str
    title: str
    url: str
    price: float
    shipping: float
    overall_cost: float
    condition: str
    seller: str
    listing_type: str
    end_time: datetime | None
    image_url: str
    availability_status: AvailabilityStatus = "UNKNOWN"
    listing_confidence: ListingConfidence = "LOW"
    currency: str = "USD"


class MarketplaceAdapter(ABC):
    marketplace_code: str

    @abstractmethod
    def search(
        self,
        *,
        query: str,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        limit: int = 15,
        settings: Settings | None = None,
    ) -> AdapterOperationResult:
        raise NotImplementedError

    @abstractmethod
    def lookup(
        self,
        *,
        item_id: str,
        settings: Settings | None = None,
    ) -> AdapterOperationResult:
        raise NotImplementedError

    @abstractmethod
    def refresh(
        self,
        *,
        item_id: str,
        settings: Settings | None = None,
    ) -> AdapterOperationResult:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, listing: NormalizedMarketplaceListing) -> UnifiedMarketplaceListing:
        raise NotImplementedError


def not_supported_result(*, error: str | None = None) -> AdapterOperationResult:
    return AdapterOperationResult(status="NOT_SUPPORTED", error=error or "Marketplace adapter not supported yet.")
