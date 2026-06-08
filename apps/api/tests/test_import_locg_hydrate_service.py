from datetime import date

import pytest
from sqlmodel import Session

from app.models import User
from app.models.external_catalog import ExternalCatalogIssue
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.import_catalog_resolution_service import (
    catalog_match_fields_for_item,
    resolve_import_catalog_match,
)
from app.services.import_locg_hydrate_service import (
    hydrate_import_item_from_locg_calendar,
    import_locg_hydrate_request_scope,
    release_week_candidates,
)

TERMINAL_CALENDAR_HTML = """<!DOCTYPE html><html><body>
<script type="application/json" id="locg-release-calendar">
{
  "issues": [
    {
      "title": "Terminal #1",
      "publisher": "Image Comics",
      "release_date": "2026-07-22",
      "price": "4.99",
      "source_url": "/comic/900010/terminal-1",
      "cover_image_url": "https://cdn.example/terminal-cover.jpg",
      "variant_count": 2
    }
  ]
}
</script>
</body></html>
"""

TERMINAL_DETAIL_HTML = """<!DOCTYPE html><html><body>
<script type="application/json" id="locg-issue-data">
{
  "title": "Terminal #1",
  "publisher": "Image Comics",
  "series_name": "Terminal",
  "issue_number": "1",
  "release_date": "2026-07-22",
  "price": 4.99,
  "description": "SOLICITATION: Kirkman and Casey launch a new superhero epic.",
  "pull_count": 120,
  "cover_image_url": "https://cdn.example/terminal-cover.jpg",
  "source_url": "https://leagueofcomicgeeks.com/comic/900010/terminal-1"
}
</script>
</body></html>
"""


def _install_locg_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.import_locg_hydrate_service as hydrate_mod
    from app.services.external_catalog import sync_service as sync_mod

    def fake_calendar(page_date: date, *, client=None, html_override=None) -> str:
        return TERMINAL_CALENDAR_HTML

    def fake_detail(url: str, *, client=None) -> str:
        return TERMINAL_DETAIL_HTML

    monkeypatch.setattr(hydrate_mod, "fetch_release_date_page", fake_calendar)
    monkeypatch.setattr(sync_mod, "fetch_issue_detail_page", fake_detail)
    monkeypatch.setenv("IMPORT_LOCG_HYDRATE", "1")


def test_release_week_candidates_bounded_around_parsed_date() -> None:
    weeks = release_week_candidates(
        parsed_release_date=date(2026, 7, 22),
        today=date(2026, 6, 8),
    )
    assert weeks[0] == date(2026, 7, 22)
    assert date(2026, 7, 15) in weeks
    assert len(weeks) <= 6


def test_hydrate_disabled_is_no_op(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_LOCG_HYDRATE", "0")
    result = hydrate_import_item_from_locg_calendar(
        session,
        title="Terminal",
        issue_number="1",
    )
    assert result.attempted is False
    assert result.hydrated is False
    assert result.no_match_reason == "hydrate_disabled"


def test_hydrate_missing_title_or_issue_is_no_op(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_LOCG_HYDRATE", "1")
    assert hydrate_import_item_from_locg_calendar(session, title=None, issue_number="1").attempted is False
    assert hydrate_import_item_from_locg_calendar(session, title="Terminal", issue_number=None).attempted is False


def test_calendar_stub_triggers_detail_upsert(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_locg_mocks(monkeypatch)
    result = hydrate_import_item_from_locg_calendar(
        session,
        title="Terminal",
        issue_number="1",
        parsed_release_date=date(2026, 7, 22),
        today=date(2026, 6, 8),
    )
    assert result.hydrated is True
    assert result.matched_stub_title == "Terminal #1"
    assert result.external_issue_id is not None

    from sqlmodel import select

    row = session.exec(
        select(ExternalCatalogIssue).where(ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME)
    ).first()
    assert row is not None
    assert row.series_name == "Terminal"
    assert row.issue_number == "1"


def test_locg_calendar_failure_does_not_raise(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.import_locg_hydrate_service as hydrate_mod

    monkeypatch.setenv("IMPORT_LOCG_HYDRATE", "1")

    def boom(*args, **kwargs):
        raise ConnectionError("locg down")

    monkeypatch.setattr(hydrate_mod, "fetch_release_date_page", boom)
    result = hydrate_import_item_from_locg_calendar(
        session,
        title="Terminal",
        issue_number="1",
        parsed_release_date=date(2026, 7, 22),
    )
    assert result.hydrated is False
    assert result.no_match_reason == "no_matching_stub"


def test_duplicate_lines_skip_repeat_fetches(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.import_locg_hydrate_service as hydrate_mod

    _install_locg_mocks(monkeypatch)
    fetch_calls = {"n": 0}

    def counting_calendar(page_date: date, *, client=None, html_override=None) -> str:
        fetch_calls["n"] += 1
        return TERMINAL_CALENDAR_HTML

    monkeypatch.setattr(hydrate_mod, "fetch_release_date_page", counting_calendar)

    with import_locg_hydrate_request_scope() as cache:
        first = hydrate_import_item_from_locg_calendar(
            session,
            title="Terminal",
            issue_number="1",
            parsed_release_date=date(2026, 7, 22),
        )
        second = hydrate_import_item_from_locg_calendar(
            session,
            title="Terminal",
            issue_number="1",
            parsed_release_date=date(2026, 7, 22),
        )
        assert first.hydrated is True
        assert second.cached is True
        assert fetch_calls["n"] == 1
        assert cache.calendar_fetch_count == 1


def test_resolve_retries_after_hydrate_and_sets_source_signal(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="terminal-resolve@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    _install_locg_mocks(monkeypatch)

    with import_locg_hydrate_request_scope():
        resolution = resolve_import_catalog_match(
            session,
            owner_user_id=user.id,
            item={
                "publisher": "Image Comics",
                "title": "Terminal",
                "issue_number": "1",
                "parsed_release_date": "2026-07-22",
            },
        )

    assert resolution.matched is True
    assert resolution.diagnostics.get("locg_hydrated") is True
    fields = catalog_match_fields_for_item(resolution)
    assert fields["catalog_match_hydrated"] is True
    assert fields["catalog_match_catalog_source"] == "LOCG_LIVE_HYDRATED"
