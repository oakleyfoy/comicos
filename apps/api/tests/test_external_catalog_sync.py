from __future__ import annotations

import pytest
from datetime import date

pytestmark = pytest.mark.usefixtures("client")
from pathlib import Path

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogCreator, ExternalCatalogIssue, ExternalCatalogVariant
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME, parse_issue_detail_page
from app.services.external_catalog.normalization import normalize_locg_issue
from app.services.external_catalog.sync_service import (
    backfill_calendar,
    refresh_upcoming_signals,
    upsert_creators,
    upsert_external_issue,
    upsert_variants,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "locg"


def _load_detail(name: str) -> dict:
    html = (FIXTURES / name).read_text(encoding="utf-8")
    return parse_issue_detail_page(html)


def test_upsert_idempotent(session: Session) -> None:
    raw = _load_detail("issue_detail_sample.html")
    raw["source_url"] = "https://leagueofcomicgeeks.com/comic/900001/youngblood-100"
    norm = normalize_locg_issue(raw, source_name=LOCG_SOURCE_NAME)
    row1, created1, _ = upsert_external_issue(session, norm)
    row2, created2, updated2 = upsert_external_issue(session, norm)
    assert created1 is True
    assert created2 is False
    assert row1.id == row2.id
    assert updated2 is False

    norm.pull_count = 900
    row3, _, updated3 = upsert_external_issue(session, norm, overwrite_nulls_only=True)
    assert updated3 is True
    assert row3.pull_count == 900

    variants_created, _ = upsert_variants(session, row3, norm.variants)
    variants_created_2, variants_updated_2 = upsert_variants(session, row3, norm.variants)
    assert variants_created >= 1
    assert variants_created_2 == 0 and variants_updated_2 == 0

    creators_created = upsert_creators(session, row3, norm.creators)
    creators_created_2 = upsert_creators(session, row3, norm.creators)
    assert creators_created >= 5
    assert creators_created_2 == 0

    variant_rows = session.exec(
        select(ExternalCatalogVariant).where(ExternalCatalogVariant.external_issue_id == int(row3.id or 0))
    ).all()
    creator_rows = session.exec(
        select(ExternalCatalogCreator).where(ExternalCatalogCreator.external_issue_id == int(row3.id or 0))
    ).all()
    assert variant_rows
    assert creator_rows
    assert row3.cover_image_url
    assert row3.thumbnail_url
    assert row3.high_resolution_image_url
    assert row3.is_milestone_issue
    assert row3.importance_signals_json


def test_backfill_dry_run_with_fixture_dates(session: Session, monkeypatch) -> None:
    calendar_html = (FIXTURES / "release_calendar_sample.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8")

    def fake_calendar(page_date, **kwargs):
        return calendar_html

    def fake_detail(url, **kwargs):
        return detail_html

    monkeypatch.setattr(
        "app.services.external_catalog.sync_service.fetch_release_date_page",
        fake_calendar,
    )
    monkeypatch.setattr(
        "app.services.external_catalog.sync_service.fetch_issue_detail_page",
        fake_detail,
    )
    monkeypatch.setattr(
        "app.services.external_catalog.sync_service.discover_available_release_dates",
        lambda *a, **k: [date(2026, 6, 10)],
    )

    summary = backfill_calendar(
        session,
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 10),
        dry_run=False,
        max_detail_pages_override=10,
        discover_dates=[date(2026, 6, 10)],
        delay_seconds=0,
    )
    assert summary["issues_created"] >= 1
    rows = session.exec(select(ExternalCatalogIssue)).all()
    assert rows


def test_refresh_updates_mutable_fields(session: Session, monkeypatch) -> None:
    raw = _load_detail("issue_detail_sample.html")
    raw["source_url"] = "https://leagueofcomicgeeks.com/comic/900001/youngblood-100"
    raw["release_date"] = date.today()
    norm = normalize_locg_issue(raw, source_name=LOCG_SOURCE_NAME)
    norm.pull_count = 10
    row, _, _ = upsert_external_issue(session, norm)

    html_999 = (FIXTURES / "issue_detail_sample.html").read_text(encoding="utf-8").replace("842", "999")

    monkeypatch.setattr(
        "app.services.external_catalog.sync_service.fetch_issue_detail_page",
        lambda url, **kwargs: html_999,
    )

    summary = refresh_upcoming_signals(
        session,
        days_forward=365,
        max_detail_pages=5,
        delay_seconds=0,
    )
    assert summary["issues_updated"] >= 1
    refreshed = session.get(ExternalCatalogIssue, row.id)
    assert refreshed is not None
    assert refreshed.pull_count == 999
