from __future__ import annotations

from datetime import date

from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_SOURCE_NAME,
    LocgListVariantRowStub,
)
from app.services.external_catalog.sync_service import (
    ensure_locg_source,
    find_locg_issue_by_comic_id,
    upsert_locg_list_variant_rows,
)


def test_variant_only_parent_gets_stub_from_variant_row(session) -> None:
    """Reprint rows often have no data-parent=0 list line; parent URL comes from variant href."""
    ensure_locg_source(session)
    assert find_locg_issue_by_comic_id(session, "3675864") is None
    variant = LocgListVariantRowStub(
        variant_comic_id="9351479",
        parent_comic_id="3675864",
        title="Absolute Batman #15 4th Printing Gabriele DellOtto Foil Virgin Variant",
        variant_name="Absolute Batman #15 4th Printing Gabriele DellOtto Foil Virgin Variant",
        publisher="DC Comics",
        source_url="https://leagueofcomicgeeks.com/comic/3675864/absolute-batman-15?variant=9351479",
        parent_source_url="https://leagueofcomicgeeks.com/comic/3675864/absolute-batman-15",
        cover_image_url=None,
        price=4.99,
        release_date=date(2026, 6, 24),
    )
    stats = upsert_locg_list_variant_rows(session, [variant], page_date=date(2026, 6, 24))
    assert stats.skipped_missing_parent == 0
    assert stats.persisted >= 1
    assert stats.parents_ensured_from_variant_rows >= 1
    assert find_locg_issue_by_comic_id(session, "3675864", source_name=LOCG_SOURCE_NAME) is not None
