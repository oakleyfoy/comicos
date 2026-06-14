from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.comicvine_catalog_importer import ComicVineCatalogImporter


def _job_stub(*, offset: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        cursor={"offset": offset},
        total_created=0,
        total_updated=0,
        total_skipped=0,
        total_failed=0,
        total_seen=0,
    )


def _volume_row(volume_id: int, *, publisher: str = "Marvel Comics", name: str | None = None) -> dict:
    return {
        "id": volume_id,
        "name": name or f"Series {volume_id}",
        "start_year": 2020,
        "publisher": {"name": publisher},
    }


@pytest.fixture
def importer() -> ComicVineCatalogImporter:
    imp = ComicVineCatalogImporter(api_key="test-key", dry_run=True)
    imp._get = MagicMock()  # noqa: SLF001 — pagination tests stub page fetcher instead
    return imp


def test_limit_250_fetches_three_pages_at_offsets_0_100_200(monkeypatch: pytest.MonkeyPatch, importer: ComicVineCatalogImporter) -> None:
    calls: list[dict] = []

    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        calls.append({"offset": offset, "page_limit": page_limit})
        n = min(page_limit, 100)
        return {"results": [_volume_row(offset + i) for i in range(n)]}

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    session = MagicMock()
    stats = importer.import_volumes(session, offset=0, limit=250, publisher_filter=None, strict_publisher=False)

    assert stats.api_pages_fetched == 3
    assert stats.total_candidates_seen == 250
    assert stats.final_offset == 250
    assert [c["offset"] for c in calls] == [0, 100, 200]
    assert calls[0]["page_limit"] == 100
    assert calls[1]["page_limit"] == 100
    assert calls[2]["page_limit"] == 50


def test_final_offset_advances_by_rows_fetched_not_requested_limit(
    monkeypatch: pytest.MonkeyPatch, importer: ComicVineCatalogImporter
) -> None:
    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        if offset == 0:
            return {"results": [_volume_row(i) for i in range(100)]}
        if offset == 100:
            return {"results": [_volume_row(100 + i) for i in range(40)]}
        return {"results": []}

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    session = MagicMock()
    stats = importer.import_volumes(session, offset=0, limit=250)

    assert stats.api_pages_fetched == 2
    assert stats.total_candidates_seen == 140
    assert stats.final_offset == 140


def test_strict_publisher_skips_still_count_as_candidates_seen(
    monkeypatch: pytest.MonkeyPatch, importer: ComicVineCatalogImporter
) -> None:
    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        return {
            "results": [
                _volume_row(1, publisher="Dark Horse Comics"),
                _volume_row(2, publisher="Totally Other Publisher"),
            ]
        }

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    session = MagicMock()
    stats = importer.import_volumes(
        session,
        offset=0,
        limit=10,
        publisher_filter="Dark Horse",
        strict_publisher=True,
    )

    assert stats.total_candidates_seen == 2
    assert stats.skipped_non_matching_publisher == 1
    assert stats.accepted_volumes == 1


def test_resume_starts_at_saved_final_offset(monkeypatch: pytest.MonkeyPatch, importer: ComicVineCatalogImporter) -> None:
    seen_offsets: list[int] = []

    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        seen_offsets.append(offset)
        return {"results": [_volume_row(offset + i) for i in range(min(page_limit, 5))]}

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    job = _job_stub(offset=140)
    session = MagicMock()

    stats = importer.import_volumes(
        session,
        offset=140,
        limit=20,
        job=job,
        cursor_scope={"publisher_filter": None},
    )

    assert seen_offsets == [140]
    assert stats.final_offset == 145
    assert stats.total_candidates_seen == 5


def test_cursor_updated_per_page_with_actual_offset(monkeypatch: pytest.MonkeyPatch, importer: ComicVineCatalogImporter) -> None:
    cursor_writes: list[int] = []

    def fake_update_cursor(session, job, payload):  # noqa: ANN001
        cursor_writes.append(int(payload["offset"]))

    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        if offset == 0:
            return {"results": [_volume_row(i) for i in range(100)]}
        return {"results": [_volume_row(100 + i) for i in range(40)]}

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    monkeypatch.setattr("app.services.comicvine_catalog_importer.update_cursor", fake_update_cursor)
    job = _job_stub(offset=0)
    session = MagicMock()

    importer.import_volumes(session, offset=0, limit=250, job=job, cursor_scope={})

    assert cursor_writes == [100, 140]
