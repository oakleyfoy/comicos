from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.catalog_master import CatalogSeries
from app.services.comicvine_catalog_importer import (
    ComicVineCatalogImporter,
    ComicVineImportStats,
    comicvine_accepted_volume_metrics,
    dedupe_catalog_series_ids_for_issue_import,
)


def _series(catalog_id: int, comicvine_volume_id: str) -> CatalogSeries:
    return CatalogSeries(
        id=catalog_id,
        name=f"Series {catalog_id}",
        normalized_name=f"series {catalog_id}",
        publisher_id=1,
        external_source_ids={"COMICVINE": {comicvine_volume_id: True}},
    )


def test_comicvine_accepted_volume_metrics_duplicates() -> None:
    raw, unique, removed = comicvine_accepted_volume_metrics(["773", "773", "78849", "773", "78849"])
    assert raw == 5
    assert unique == 2
    assert removed == 3


def test_dedupe_catalog_series_ids_for_issue_import() -> None:
    session = MagicMock()
    session.get.side_effect = lambda _model, catalog_id: {
        1: _series(1, "773"),
        2: _series(2, "773"),
        3: _series(3, "78849"),
        4: _series(4, "39879"),
    }.get(catalog_id)

    unique, removed = dedupe_catalog_series_ids_for_issue_import(session, [1, 2, 3, 1, 3, 4])
    assert unique == [1, 3, 4]
    assert removed == 3


def test_issue_import_calls_import_once_per_unique_volume_id(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.get.side_effect = lambda _model, catalog_id: {
        10: _series(10, "773"),
        11: _series(11, "773"),
        12: _series(12, "78849"),
    }.get(catalog_id)
    session.commit = MagicMock()

    volume_calls: list[str] = []

    def fake_import_issues(self, session, *, volume_id, catalog_series_id, limit=50, job=None, offset=0):  # noqa: ANN001
        volume_calls.append(volume_id)
        return ComicVineImportStats()

    monkeypatch.setattr(ComicVineCatalogImporter, "import_issues_for_volume", fake_import_issues)
    monkeypatch.setattr(
        "app.services.comicvine_catalog_importer.start_job",
        lambda *a, **k: SimpleNamespace(id=99),
    )
    monkeypatch.setattr("app.services.comicvine_catalog_importer.complete_job", lambda *a, **k: None)

    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)
    stats = importer._run_issue_import_phase(  # noqa: SLF001
        session,
        series_ids=[10, 11, 12, 10, 11],
        publisher_filter=None,
        series_name="Superman",
        strict_publisher=False,
        parent_volume_job_id=1,
    )

    assert volume_calls == ["773", "78849"]
    assert stats.issue_imports_started == 2
    assert stats.issue_imports_completed == 2
    assert stats.issue_import_volumes_attempted == 2


def test_superman_duplicate_volume_search_issue_job_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate Superman search accepting duplicate ComicVine volume rows; issue phase must finish."""
    session = MagicMock()
    session.commit = MagicMock()

    catalog_by_volume = {
        "773": _series(101, "773"),
        "78849": _series(102, "78849"),
        "39879": _series(103, "39879"),
        "60429": _series(104, "60429"),
        "149415": _series(105, "149415"),
    }

    def get_side_effect(model, obj_id):  # noqa: ANN001
        if model is CatalogSeries:
            return next((s for s in catalog_by_volume.values() if s.id == obj_id), None)
        return None

    session.get.side_effect = get_side_effect

    volume_calls: list[str] = []

    def fake_fetch(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict:
        rows = [
            {"id": 773, "name": "Superman", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 773, "name": "Superman", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 78849, "name": "Superman (1987)", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 78849, "name": "Superman (1987)", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 39879, "name": "Superman: Man of Steel", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 60429, "name": "Superman/Batman", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
            {"id": 149415, "name": "Superman: Action Comics", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
        ]
        start = offset
        end = min(start + page_limit, len(rows))
        chunk = rows[start:end]
        return {"results": chunk}

    def fake_process(self, session, stats, row, *, publisher_filter, strict_publisher, job, min_start_year=None):  # noqa: ANN001
        stats.total_candidates_seen += 1
        stats.accepted_volumes += 1
        vid = str(row["id"])
        stats.accepted_comicvine_volume_ids.append(vid)
        series = catalog_by_volume[vid]
        stats.imported_series_ids.append(int(series.id or 0))

    def fake_import_issues(self, session, *, volume_id, catalog_series_id, limit=50, job=None, offset=0):  # noqa: ANN001
        volume_calls.append(volume_id)
        return ComicVineImportStats(processed=1)

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    monkeypatch.setattr(ComicVineCatalogImporter, "_process_volume_row", fake_process)
    monkeypatch.setattr(ComicVineCatalogImporter, "import_issues_for_volume", fake_import_issues)
    monkeypatch.setattr(ComicVineCatalogImporter, "initialize_or_explain", lambda self: None)
    monkeypatch.setattr(
        "app.services.comicvine_catalog_importer.start_job",
        lambda *a, **k: SimpleNamespace(id=108, cursor={}),
    )
    monkeypatch.setattr("app.services.comicvine_catalog_importer.complete_job", lambda *a, **k: None)
    monkeypatch.setattr("app.services.comicvine_catalog_importer.update_cursor", lambda *a, **k: None)
    monkeypatch.setattr("app.services.comicvine_catalog_importer.fail_job", lambda *a, **k: None)
    monkeypatch.setattr("app.services.comicvine_catalog_importer.resume_scoped_job", lambda *a, **k: None)

    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)
    stats = importer.run_bulk_import(
        session,
        limit=250,
        series_name="Superman",
        import_issues=True,
    )

    assert stats.issue_import_ran is True
    assert stats.accepted_volumes_raw == 7
    assert stats.accepted_volumes_unique == 5
    assert stats.duplicate_volumes_removed == 2
    assert stats.issue_imports_started == 5
    assert stats.issue_imports_completed == 5
    assert volume_calls == ["773", "78849", "39879", "60429", "149415"]
    assert len(volume_calls) == len(set(volume_calls))
