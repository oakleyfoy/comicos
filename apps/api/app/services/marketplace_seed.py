from __future__ import annotations

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceCapability, MarketplaceDefinition

MARKETPLACE_SEED_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "marketplace_code": "EBAY",
        "marketplace_name": "eBay",
        "description": "Reserved connector framework entry for future eBay integrations.",
        "enabled": False,
        "capabilities": (
            ("inventory.sync", "Inventory Sync"),
            ("listing.publish", "Listing Publish"),
            ("listing.update", "Listing Update"),
            ("order.import", "Order Import"),
        ),
    },
    {
        "marketplace_code": "HIPCOMIC",
        "marketplace_name": "HipComic",
        "description": "Reserved connector framework entry for future HipComic integrations.",
        "enabled": False,
        "capabilities": (
            ("inventory.sync", "Inventory Sync"),
            ("listing.publish", "Listing Publish"),
            ("listing.update", "Listing Update"),
            ("order.import", "Order Import"),
        ),
    },
    {
        "marketplace_code": "SHOPIFY",
        "marketplace_name": "Shopify",
        "description": "Reserved connector framework entry for future Shopify integrations.",
        "enabled": False,
        "capabilities": (
            ("inventory.sync", "Inventory Sync"),
            ("listing.publish", "Listing Publish"),
            ("listing.update", "Listing Update"),
            ("listing.archive", "Listing Archive"),
            ("listing.restore", "Listing Restore"),
            ("order.import", "Order Import"),
        ),
    },
    {
        "marketplace_code": "WHATNOT",
        "marketplace_name": "Whatnot",
        "description": "Reserved connector framework entry for future Whatnot integrations.",
        "enabled": False,
        "capabilities": (
            ("inventory.sync", "Inventory Sync"),
            ("listing.publish", "Listing Publish"),
            ("listing.update", "Listing Update"),
            ("listing.pause", "Listing Pause"),
            ("listing.resume", "Listing Resume"),
            ("order.import", "Order Import"),
        ),
    },
)


def ensure_marketplace_definitions(session: Session) -> None:
    existing = {
        row.marketplace_code: row
        for row in session.exec(select(MarketplaceDefinition)).all()
    }
    created_any = False
    for seed in MARKETPLACE_SEED_DEFINITIONS:
        code = str(seed["marketplace_code"])
        row = existing.get(code)
        if row is None:
            row = MarketplaceDefinition(
                marketplace_code=code,
                marketplace_name=str(seed["marketplace_name"]),
                description=str(seed["description"]),
                enabled=bool(seed["enabled"]),
            )
            session.add(row)
            session.flush()
            existing[code] = row
            created_any = True
        existing_caps = {
            capability.capability_code
            for capability in session.exec(
                select(MarketplaceCapability).where(MarketplaceCapability.marketplace_id == int(row.id or 0))
            ).all()
        }
        for capability_code, capability_name in seed["capabilities"]:
            if capability_code in existing_caps:
                continue
            session.add(
                MarketplaceCapability(
                    marketplace_id=int(row.id or 0),
                    capability_code=str(capability_code),
                    capability_name=str(capability_name),
                )
            )
            created_any = True
    if created_any:
        session.commit()
