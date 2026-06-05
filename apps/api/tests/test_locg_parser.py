from __future__ import annotations

from datetime import date
from pathlib import Path

from app.services.external_catalog.league_of_comic_geeks import (
    parse_issue_detail_page,
    parse_release_date_page,
)
from app.services.external_catalog.normalization import normalize_locg_issue

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "locg"


def test_parse_release_date_page_sample() -> None:
    html = (FIXTURES / "release_calendar_sample.html").read_text(encoding="utf-8")
    stubs = parse_release_date_page(html, page_date=date(2026, 6, 10))
    assert len(stubs) >= 2
    titles = {s.title for s in stubs}
    assert "Youngblood #100" in titles
    assert any(s.source_url.endswith("youngblood-100") or "900001" in s.source_url for s in stubs)


def test_parse_issue_detail_page_sample() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    detail = parse_issue_detail_page(html)
    assert detail["title"] == "Youngblood #100"
    assert detail["pull_count"] == 842
    assert detail["want_count"] == 1205
    assert detail.get("creator_credits") or detail.get("creators")
    assert len(detail["variants"]) >= 2
    assert detail.get("cover_image_url")
    assert detail.get("thumbnail_url")
    assert detail.get("high_resolution_image_url")


def test_detail_includes_solicitation_and_creators() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    detail = parse_issue_detail_page(html)
    assert "SOLICITATION" in (detail.get("description") or "")
    assert detail.get("story_summary")
    assert detail.get("creator_credits") or detail.get("creators")


def test_normalize_requires_cover_image_urls() -> None:
    from app.services.external_catalog.normalization import normalize_locg_issue

    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    from app.services.external_catalog.league_of_comic_geeks import parse_issue_detail_page

    norm = normalize_locg_issue(parse_issue_detail_page(html), source_name="LEAGUE_OF_COMIC_GEEKS")
    assert norm.cover_image_url
    assert norm.thumbnail_url
    assert norm.high_resolution_image_url


def test_normalize_locg_issue() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    raw = parse_issue_detail_page(html)
    norm = normalize_locg_issue(raw, source_name="LEAGUE_OF_COMIC_GEEKS")
    assert norm.issue_number == "100"
    assert norm.pull_count == 842
    assert norm.publisher == "Image Comics"
