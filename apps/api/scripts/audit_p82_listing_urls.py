"""Read-only audit of P82 marketplace acquisition listing URLs."""

from __future__ import annotations

import os
import sys
from collections import Counter

from sqlalchemy import inspect
from sqlmodel import Session, create_engine, select

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.services.p82_listing_url_safety import classify_p82_listing_url


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1

    engine = create_engine(database_url)
    inspector = inspect(engine)
    if not inspector.has_table("p82_marketplace_acquisition_opportunity"):
        print("Table p82_marketplace_acquisition_opportunity not found; nothing to audit.")
        return 0

    with Session(engine) as session:
        rows = list(
            session.exec(
                select(MarketplaceAcquisitionOpportunity).where(
                    MarketplaceAcquisitionOpportunity.status == "ACTIVE"
                )
            ).all()
        )

    total = len(rows)
    buckets = Counter(
        classify_p82_listing_url(
            listing_url=row.listing_url,
            external_listing_id=row.external_listing_id,
        )
        for row in rows
    )

    print("P82 active marketplace acquisition opportunity URL audit")
    print(f"total_active: {total}")
    print(f"missing_listing_url: {buckets.get('missing_url', 0)}")
    print(f"simulated_test_cert_external_id: {buckets.get('simulated_external_id', 0)}")
    print(f"generated_fake_ebay_looking_urls: {buckets.get('fake_ebay_generated', 0)}")
    print(f"ebay_urls_non_numeric_item_id: {buckets.get('ebay_non_numeric', 0)}")
    print(f"likely_safe_ebay_urls: {buckets.get('likely_safe_ebay', 0)}")
    print(f"non_ebay_https_urls: {buckets.get('non_ebay_https', 0)}")
    print(f"other_unsafe: {buckets.get('other_unsafe', 0)}")

    suspicious_buckets = {
        "missing_url",
        "simulated_external_id",
        "fake_ebay_generated",
        "ebay_non_numeric",
        "other_unsafe",
    }
    suspicious = [
        row
        for row in rows
        if classify_p82_listing_url(
            listing_url=row.listing_url,
            external_listing_id=row.external_listing_id,
        )
        in suspicious_buckets
    ]

    print("\nSample suspicious rows (up to 20):")
    for row in suspicious[:20]:
        print(
            f"  id={row.id} title={row.title!r} marketplace={row.marketplace!r} "
            f"external_listing_id={row.external_listing_id!r} listing_url={row.listing_url!r}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
