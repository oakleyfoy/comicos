"""Regression tests for P97 ComicVine import resilience to dropped DB connections.

A transient database network drop used to crash the whole overnight import with a
masked ``PendingRollbackError`` (the failure handler touched the rolled-back session).
The importer now detects connection loss, rolls back, and retries the page.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import InterfaceError, OperationalError

from app.services import comicvine_catalog_importer as importer_module
from app.services.comicvine_catalog_importer import (
    ComicVineCatalogImporter,
    _is_db_connection_error,
)


def test_is_db_connection_error_detects_interface_and_message() -> None:
    assert _is_db_connection_error(InterfaceError("stmt", {}, Exception("network error")))
    assert _is_db_connection_error(OperationalError("stmt", {}, Exception("server closed")))
    assert _is_db_connection_error(Exception("pg8000 network error"))
    # Plain data errors are not treated as connection loss.
    assert not _is_db_connection_error(ValueError("bad issue number"))


def test_import_volumes_retries_page_after_connection_drop(monkeypatch: pytest.MonkeyPatch) -> None:
    page = [
        {"id": 1, "name": "Alpha", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
        {"id": 2, "name": "Beta", "publisher": {"name": "DC Comics"}, "resource_type": "volume"},
    ]

    def fake_fetch(self, *, offset, page_limit, publisher_filter, series_name):  # noqa: ANN001
        return {"results": page if offset == 0 else []}

    attempts = {"n": 0}

    def flaky_process(self, session, stats, row, *, publisher_filter, strict_publisher, job, min_start_year=None):  # noqa: ANN001
        # First time we touch the first row of the page, simulate a dropped connection.
        if attempts["n"] == 0 and row["id"] == 1:
            attempts["n"] += 1
            raise InterfaceError("UPDATE ...", {}, Exception("network error"))
        stats.total_candidates_seen += 0  # counted by caller
        stats.accepted_volumes += 1

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    monkeypatch.setattr(ComicVineCatalogImporter, "_process_volume_row", flaky_process)
    monkeypatch.setattr(importer_module, "publisher_distribution_for_series", lambda *a, **k: {})
    monkeypatch.setattr(importer_module.time, "sleep", lambda *_a, **_k: None)

    rollbacks = {"n": 0}
    session = SimpleNamespace(
        rollback=lambda: rollbacks.__setitem__("n", rollbacks["n"] + 1),
        commit=lambda: None,
    )

    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)
    stats = importer.import_volumes(session, offset=0, limit=2, job=None)

    assert rollbacks["n"] == 1, "should roll back once on the dropped connection"
    assert attempts["n"] == 1, "the row should only fail the connection once"
    assert stats.accepted_volumes == 2, "page should be fully reprocessed after retry"


def test_import_volumes_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    page = [{"id": 1, "name": "Alpha", "publisher": {"name": "DC Comics"}, "resource_type": "volume"}]

    def fake_fetch(self, *, offset, page_limit, publisher_filter, series_name):  # noqa: ANN001
        return {"results": page if offset == 0 else []}

    def always_drops(self, session, stats, row, *, publisher_filter, strict_publisher, job, min_start_year=None):  # noqa: ANN001
        raise OperationalError("UPDATE ...", {}, Exception("connection reset"))

    monkeypatch.setattr(ComicVineCatalogImporter, "_fetch_volume_page", fake_fetch)
    monkeypatch.setattr(ComicVineCatalogImporter, "_process_volume_row", always_drops)
    monkeypatch.setattr(importer_module, "publisher_distribution_for_series", lambda *a, **k: {})
    monkeypatch.setattr(importer_module.time, "sleep", lambda *_a, **_k: None)

    session = SimpleNamespace(rollback=lambda: None, commit=lambda: None)
    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)

    # Should abort gracefully (resumable), not raise.
    stats = importer.import_volumes(session, offset=0, limit=1, job=None)
    assert any("db_connection_lost" in f for f in stats.failures)
    assert stats.final_offset == 0, "cursor must not advance past the failing page"
