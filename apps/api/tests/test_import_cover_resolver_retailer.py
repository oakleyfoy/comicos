from __future__ import annotations

from app.schemas.ai import ParseOrderResponse
from app.services.import_cover_resolver import apply_import_cover_to_parse_order


def _payload(**item_overrides: object) -> ParseOrderResponse:
    item = {
        "publisher": "Dark Horse",
        "title": "Shaolin Cowboy Staying A.I. Live",
        "issue_number": "1",
        "cover_name": "Cover A",
        "variant_type": "Cover A",
        "cover_artist": "Geof Darrow",
        "raw_item_price": "4.99",
        "cover_image_url": "https://example.com/catalog.jpg",
        "cover_image_source": "external_catalog_variant",
    }
    item.update(item_overrides)
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown Comics",
            "items": [item],
        }
    )


def test_retailer_match_wins_over_catalog_image(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.import_cover_resolver.enrich_item_with_midtown_lookup",
        lambda item, limit=10: {
            "retailer_lookup_status": "matched",
            "retailer_lookup_score": 92,
            "retailer_product_url": "https://www.midtowncomics.com/product/1",
            "retailer_cover_url": "https://cdn.example.com/midtown-a.jpg",
            "retailer_lookup_enrichment": {
                "matched": True,
                "possible_match": False,
                "retailer": "Midtown Comics",
                "checked_at": "2026-06-09T11:00:00+00:00",
                "selected_candidate": {
                    "retailer": "Midtown Comics",
                    "product_title": "Shaolin Cowboy Staying A.I. Live #1 Cover A",
                    "product_url": "https://www.midtowncomics.com/product/1",
                    "image_url": "https://cdn.example.com/midtown-a.jpg",
                    "thumbnail_url": "https://cdn.example.com/midtown-a.jpg",
                    "publisher": "Dark Horse",
                    "series_title": "Shaolin Cowboy Staying A.I. Live",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "variant_type": "Cover A",
                    "cover_artist": "Geof Darrow",
                    "release_date": "2026-01-01",
                    "price": "4.99",
                    "sku": "SKU-A",
                    "source_confidence": 0.92,
                    "raw_score_reasons": ["title_exact"],
                },
            },
        },
    )
    result = apply_import_cover_to_parse_order(_payload(), session=None, owner_user_id=41, draft_import_id=1)
    item = result.items[0]
    assert item.cover_image_url == "https://cdn.example.com/midtown-a.jpg"
    assert item.cover_thumbnail_url == "https://cdn.example.com/midtown-a.jpg"
    assert item.cover_source == "RETAILER"
    assert item.cover_image_source == "midtown_product"
    assert item.has_cover_image is True


def test_placeholder_is_safe_when_no_match(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.import_cover_resolver.enrich_item_with_midtown_lookup",
        lambda item, limit=10: {},
    )
    result = apply_import_cover_to_parse_order(
        _payload(cover_image_url=None, cover_thumbnail_url=None, cover_image_source=None),
        session=None,
        owner_user_id=41,
        draft_import_id=1,
    )
    item = result.items[0]
    assert item.cover_source is None
    assert item.has_cover_image in (None, False)
    assert item.cover_image_url is None
