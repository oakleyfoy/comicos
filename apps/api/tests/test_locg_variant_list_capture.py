from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("client")

from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.locg_browser import parse_list_variant_rows
from app.services.external_catalog.locg_live_html import list_variant_row_to_upsert_dict
from app.services.external_catalog.normalization import normalize_locg_issue
from app.services.external_catalog.sync_service import (
    ensure_locg_source,
    upsert_external_issue,
    upsert_locg_list_variant_rows,
)

CAPTURE_LIST = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "locg_browser_capture"
    / "2026-06-10"
    / "list_page.html"
)


@pytest.mark.skipif(not CAPTURE_LIST.is_file(), reason="captured list_page.html not present")
def test_parse_list_variant_rows_from_capture() -> None:
    html = CAPTURE_LIST.read_text(encoding="utf-8")
    rows = parse_list_variant_rows(html, page_date=date(2026, 6, 10))
    assert len(rows) >= 100
    sample = rows[0]
    assert "?variant=" in sample.source_url
    assert sample.parent_comic_id != "0"
    assert sample.variant_comic_id
    norm = list_variant_row_to_upsert_dict(sample)
    assert norm.get("variant_detail_url") == sample.source_url


def test_upsert_list_variants_links_to_parent(session) -> None:
    ensure_locg_source(session)
    parent_url = "https://leagueofcomicgeeks.com/comic/5802211/absolute-catwoman-1"
    norm = normalize_locg_issue(
        {
            "source_name": LOCG_SOURCE_NAME,
            "source_url": parent_url,
            "title": "Absolute Catwoman #1",
            "publisher": "DC Comics",
            "release_date": date(2026, 6, 10),
        },
        source_name=LOCG_SOURCE_NAME,
    )
    parent_row, _, _ = upsert_external_issue(session, norm, overwrite_nulls_only=True)
    from app.services.external_catalog.league_of_comic_geeks import LocgListVariantRowStub

    variant = LocgListVariantRowStub(
        variant_comic_id="8366971",
        parent_comic_id="5802211",
        title="Absolute Catwoman #1",
        variant_name="616 Comics Ed Benes Foil Virgin Variant",
        publisher="DC Comics",
        source_url="https://leagueofcomicgeeks.com/comic/5802211/absolute-catwoman-1?variant=8366971",
        parent_source_url=parent_url,
        cover_image_url="https://example.com/v.jpg",
        price=4.99,
        release_date=date(2026, 6, 10),
    )
    stats = upsert_locg_list_variant_rows(session, [variant])
    assert stats.persisted >= 1
