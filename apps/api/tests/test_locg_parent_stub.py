from __future__ import annotations

from app.services.external_catalog.locg_parent_stub import (
    comic_id_from_locg_url,
    derive_parent_title_from_variant_title,
)


def test_derive_parent_title_from_reprint_variant() -> None:
    title = "Absolute Batman #15 4th Printing Gabriele DellOtto Foil Virgin Variant"
    assert derive_parent_title_from_variant_title(title) == "Absolute Batman #15"


def test_comic_id_from_parent_url() -> None:
    url = "https://leagueofcomicgeeks.com/comic/3675864/absolute-batman-15"
    assert comic_id_from_locg_url(url) == "3675864"
