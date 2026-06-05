from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("client")
from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue
from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_SOURCE_NAME,
    LocgListIssueStub,
    merge_detail_into_seed,
    parse_release_date_page,
    stub_to_detail_seed,
)
from app.services.external_catalog.locg_browser import (
    build_merged_issue_dict,
    calendar_url_slash_format,
    parse_detail_page_html,
    parse_list_page_html,
)
from app.services.external_catalog.sync_service import (
    should_skip_browser_resume,
    upsert_external_issue,
)
from app.services.external_catalog.normalization import normalize_locg_issue

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "locg"


def test_calendar_url_slash_format() -> None:
    assert calendar_url_slash_format(date(2026, 6, 10)) == (
        "https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10"
    )


def test_parse_list_page_issue_links() -> None:
    html = (FIXTURES / "release_calendar_sample.html").read_text(encoding="utf-8")
    stubs = parse_list_page_html(html, page_date=date(2026, 6, 10))
    assert len(stubs) >= 2
    urls = {s.source_url for s in stubs}
    assert any("/comic/900001/" in u for u in urls)


def test_parse_live_list_page() -> None:
    html = (FIXTURES / "release_calendar_live_sample.html").read_text(encoding="utf-8")
    stubs = parse_list_page_html(html, page_date=date(2026, 6, 10))
    assert len(stubs) == 1
    assert stubs[0].title == "Absolute Catwoman #1"
    assert stubs[0].publisher == "DC Comics"
    assert stubs[0].variant_count == 52


def test_parse_live_detail_page() -> None:
    html = (FIXTURES / "issue_detail_live_sample.html").read_text(encoding="utf-8")
    detail = parse_detail_page_html(html)
    assert detail.get("pull_count") == 20093
    assert detail.get("want_count") == 2137
    assert detail.get("upc")
    assert detail.get("distributor_sku") == "MAR260330"
    assert len(detail.get("variants") or []) >= 1
    assert len(detail.get("creators") or []) >= 1
    assert len(detail.get("characters") or []) >= 1


def test_parse_detail_rich_fields() -> None:
    html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    detail = parse_detail_page_html(html)
    assert detail.get("pull_count") == 842
    assert detail.get("want_count") == 1205
    assert detail.get("foc_date")
    assert detail.get("cover_image_url")
    assert len(detail.get("variants") or []) >= 2
    assert detail.get("creator_credits") or detail.get("creators")


def test_detail_overrides_list_fallback() -> None:
    list_html = (FIXTURES / "release_calendar_sample.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    stubs = parse_list_page_html(list_html, page_date=date(2026, 6, 10))
    stub = next(s for s in stubs if "900001" in s.source_url)
    stub = LocgListIssueStub(
        title="List Title Wrong",
        publisher="",
        release_date=date(2026, 1, 1),
        price=1.0,
        source_url=stub.source_url,
        cover_image_url=None,
        variant_count=1,
        foc_date=None,
    )
    merged = build_merged_issue_dict(stub, detail_html)
    assert merged["title"] == "Youngblood #100"
    assert merged["publisher"] == "Image Comics"
    assert merged["pull_count"] == 842


def test_upsert_idempotent_browser_path(session: Session) -> None:
    detail_html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    merged = parse_detail_page_html(detail_html)
    merged["source_url"] = "https://leagueofcomicgeeks.com/comic/900001/youngblood-100"
    norm = normalize_locg_issue(merged, source_name=LOCG_SOURCE_NAME)
    row1, c1, _ = upsert_external_issue(session, norm)
    row2, c2, u2 = upsert_external_issue(session, norm)
    assert c1 is True
    assert c2 is False
    assert u2 is False
    assert row1.id == row2.id


def test_resume_skips_captured_issue(session: Session) -> None:
    detail_html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")
    merged = parse_detail_page_html(detail_html)
    url = "https://leagueofcomicgeeks.com/comic/900099/resume-skip"
    merged["source_url"] = url
    norm = normalize_locg_issue(merged, source_name=LOCG_SOURCE_NAME)
    upsert_external_issue(session, norm)
    assert should_skip_browser_resume(session, source_url=url, refresh_existing=False) is True
    assert should_skip_browser_resume(session, source_url=url, refresh_existing=True) is False


def test_capture_script_no_recommendation_rebuild() -> None:
    text = (Path(__file__).resolve().parents[1] / "scripts" / "capture_locg_date_details_browser.py").read_text(
        encoding="utf-8"
    )
    assert "cross_system" not in text
    assert "generate_unified" not in text
    assert "recommendation_ranking" not in text
    assert "compute_recommendation_decision" not in text


def test_merge_preserves_detail_when_list_empty() -> None:
    seed = stub_to_detail_seed(
        LocgListIssueStub(
            title="X",
            publisher="Marvel",
            release_date=date(2026, 6, 10),
            price=None,
            source_url="https://leagueofcomicgeeks.com/comic/1/x",
            cover_image_url=None,
            variant_count=None,
            foc_date=None,
        )
    )
    detail = {"title": "Detail Title", "pull_count": 10, "description": "Full text"}
    merged = merge_detail_into_seed(seed, detail)
    assert merged["title"] == "Detail Title"
    assert merged["pull_count"] == 10
    assert merged["publisher"] == "Marvel"
