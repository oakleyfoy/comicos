from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingImageCreate
from app.services.marketplace_listing_images import add_listing_image, list_listing_images, remove_listing_image, set_primary_image
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_marketplace_listing_images_primary_selection_is_deterministic(client: TestClient) -> None:
    register_and_login(client, "listing-image-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "listing-image-owner@example.com")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Image Listing",
                listing_description="Testing images",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="9.99",
                currency="USD",
                quantity=1,
            ),
        )
        first = add_listing_image(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingImageCreate(
                image_url="https://example.com/cover-a.jpg",
                image_type="COVER",
                sort_order=0,
            ),
        )
        second = add_listing_image(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingImageCreate(
                image_url="https://example.com/cover-b.jpg",
                image_type="BACK",
                sort_order=1,
                is_primary=True,
            ),
        )
        images = list_listing_images(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            limit=20,
            offset=0,
        )

        assert first.is_primary is True
        assert second.is_primary is True
        assert images.items[0].id == second.id
        assert images.items[0].is_primary is True

        set_primary_image(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id, image_id=first.id)
        remove_listing_image(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id, image_id=first.id)
        remaining = list_listing_images(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            limit=20,
            offset=0,
        )
        assert len(remaining.items) == 1
        assert remaining.items[0].id == second.id
        assert remaining.items[0].is_primary is True
