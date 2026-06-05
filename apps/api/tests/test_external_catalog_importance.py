from __future__ import annotations

from pathlib import Path

import pytest

from app.services.external_catalog.importance_signals import (
    detect_importance_signals,
    is_first_issue_number,
    milestone_number,
    parse_ratio_from_text,
)
from app.services.external_catalog.league_of_comic_geeks import parse_issue_detail_page
from app.services.external_catalog.normalization import normalize_locg_issue

pytestmark = pytest.mark.usefixtures("client")

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "locg"


def test_detect_milestone_and_signals() -> None:
    importance = detect_importance_signals(
        title="Youngblood #100",
        series_name="Youngblood",
        issue_number="100",
        description="Anniversary edition with first appearance and tie-in to event.",
        story_summary="Homage cover celebrating 100 issues.",
        imprint="Image",
        universe="Image Universe",
    )
    assert importance["first_issue"] is False
    assert importance["milestone_issue_number"] == 100
    assert "anniversary" in importance["signals"]
    assert "first_appearance" in importance["signals"]
    assert "tiein_crossover_event" in importance["signals"]
    assert "homage" in importance["signals"]


def test_first_issue_detection() -> None:
    assert is_first_issue_number("1")
    assert is_first_issue_number(None, title="Spawn #1")


def test_parse_ratio_from_variant_name() -> None:
    assert parse_ratio_from_text("Rob Liefeld 1:25 Variant") == 25


def test_full_detail_fixture_normalization() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    raw = parse_issue_detail_page(html)
    norm = normalize_locg_issue(raw, source_name="LEAGUE_OF_COMIC_GEEKS")
    assert norm.description
    assert norm.story_summary
    assert norm.is_milestone_issue
    assert norm.milestone_issue_number == 100
    assert norm.cover_image_url
    assert norm.product_url
    assert len(norm.creators) >= 5
    roles = {c["role_display"] for c in norm.creators}
    assert "Writer" in roles
    assert "Colorist" in roles
    assert len(norm.variants) == 2
    assert norm.variants[1]["ratio_value"] == 25
    assert norm.variants[1]["variant_detail_url"]
