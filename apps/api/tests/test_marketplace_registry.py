from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.marketplace import MarketplaceDefinition
from app.services.marketplace_registry import disable_marketplace, enable_marketplace, list_marketplaces, register_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions


def test_marketplace_registry_lists_seed_definitions_deterministically(client: TestClient) -> None:
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        listing = list_marketplaces(session, limit=20, offset=0)

        assert [row.marketplace_code for row in listing.items] == ["EBAY", "HIPCOMIC", "SHOPIFY", "WHATNOT"]
        assert all(row.enabled is False for row in listing.items)
        assert all(row.capabilities for row in listing.items)


def test_marketplace_registry_rejects_duplicate_codes(client: TestClient) -> None:
    with Session(get_engine()) as session:
        register_marketplace(
            session,
            marketplace_code="CUSTOM",
            marketplace_name="Custom Market",
            description="Test registry entry",
            capabilities=[("listing.publish", "Listing Publish")],
        )

        try:
            register_marketplace(session, marketplace_code="custom", marketplace_name="Duplicate Market")
        except HTTPException as exc:
            assert exc.status_code == 409
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected duplicate marketplace code rejection.")


def test_marketplace_registry_enable_disable_updates_state(client: TestClient) -> None:
    with Session(get_engine()) as session:
        created = register_marketplace(session, marketplace_code="DISABLE_ME", marketplace_name="Disable Me")
        enabled = enable_marketplace(session, marketplace_id=created.id)
        disabled = disable_marketplace(session, marketplace_id=created.id)

        row = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.id == created.id)).one()
        assert enabled.enabled is True
        assert disabled.enabled is False
        assert row.enabled is False
