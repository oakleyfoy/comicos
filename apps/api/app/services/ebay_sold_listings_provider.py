"""P68-02 eBay sold listings adapter skeleton (no live scrape)."""

from __future__ import annotations

from datetime import date

from app.models.market_pricing_engine import PROVIDER_EBAY_SOLD, P68MarketPriceObservation, utc_now
from app.services.p68_feature_flags import p68_ebay_provider_enabled

# Deterministic fixture for tests / dev when flag enabled.
EBAY_FIXTURE_ROWS = [
    {
        "title": "Amazing Spider-Man",
        "publisher": "Marvel",
        "issue_number": "300",
        "variant_label": "Newsstand",
        "total_price": 425.0,
        "raw_or_graded": "raw",
    }
]


class EbaySoldListingsProvider:
    def fetch(
        self,
        *,
        owner_user_id: int,
        search_query: str,
        publisher: str = "",
        issue_number: str = "",
        variant_label: str = "",
        grade: str | None = None,
        raw_or_graded: str = "raw",
    ) -> list[P68MarketPriceObservation]:
        if not p68_ebay_provider_enabled():
            return []
        rows: list[P68MarketPriceObservation] = []
        for fix in EBAY_FIXTURE_ROWS:
            if publisher and fix["publisher"].lower() != publisher.lower():
                continue
            if issue_number and fix["issue_number"] != issue_number:
                continue
            rows.append(
                P68MarketPriceObservation(
                    owner_user_id=owner_user_id,
                    provider=PROVIDER_EBAY_SOLD,
                    observed_at=utc_now(),
                    sale_date=date.today(),
                    title=fix["title"],
                    publisher=fix["publisher"],
                    issue_number=fix["issue_number"],
                    variant_label=fix.get("variant_label"),
                    raw_or_graded=fix.get("raw_or_graded", raw_or_graded),
                    grade=grade,
                    sold_price=float(fix["total_price"]),
                    total_price=float(fix["total_price"]),
                    confidence=0.55,
                    metadata_json={"fixture": True, "search_query": search_query},
                )
            )
        return rows
