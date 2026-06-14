from __future__ import annotations

from unittest.mock import MagicMock

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint
from app.services.catalog_bulk_enrichment_selection import (
    count_ready_covers,
    select_ready_covers_needing_fingerprint,
)


def test_count_ready_covers_zero_when_db_reports_zero() -> None:
    session = MagicMock()
    session.exec.return_value.one.return_value = 0
    assert count_ready_covers(session) == 0


def test_select_ready_covers_missing_fingerprint_filters_no_local_file(monkeypatch) -> None:
    session = MagicMock()
    ready = CatalogImage(
        id=1,
        source="COMICVINE",
        image_type="cover",
        download_status="ready",
        local_path="/missing/on/disk.bin",
    )
    session.exec.return_value.all.return_value = [ready]
    monkeypatch.setattr(
        "app.services.catalog_bulk_enrichment_selection.resolve_catalog_image_local_path",
        lambda _session, _image: None,
    )
    assert select_ready_covers_needing_fingerprint(session, limit=10) == []


def test_select_ready_covers_with_valid_fingerprint_excluded_by_query(monkeypatch) -> None:
    """Rows returned from SQL already exclude valid fingerprints; local path must resolve."""
    session = MagicMock()
    ready = CatalogImage(
        id=2,
        source="COMICVINE",
        image_type="cover",
        download_status="ready",
        local_path="/covers/2.bin",
    )
    session.exec.return_value.all.return_value = [ready]
    monkeypatch.setattr(
        "app.services.catalog_bulk_enrichment_selection.resolve_catalog_image_local_path",
        lambda _session, _image: __import__("pathlib").Path("/covers/2.bin"),
    )
    selected = select_ready_covers_needing_fingerprint(session, limit=10)
    assert len(selected) == 1
    assert int(selected[0].id or 0) == 2


def test_missing_only_selection_does_not_pass_after_image_id(monkeypatch) -> None:
    from app.services import catalog_bulk_fingerprint_service as fp_service

    session = MagicMock()
    captured: dict = {}

    def _fake_select(session, *, limit, after_image_id=None):
        captured["after_image_id"] = after_image_id
        return []

    monkeypatch.setattr(fp_service, "count_ready_covers", lambda _s: 100)
    monkeypatch.setattr(fp_service, "count_missing_fingerprints", lambda _s: 10)
    monkeypatch.setattr(fp_service, "select_ready_covers_needing_fingerprint", _fake_select)
    monkeypatch.setattr(fp_service, "resume_latest_job", lambda *a, **k: None)
    monkeypatch.setattr(fp_service, "start_job", lambda *a, **k: MagicMock(id=1, cursor={}, status="running"))
    class _Summary:
        total_seen = 0
        total_updated = 0
        total_failed = 0

    monkeypatch.setattr(fp_service, "complete_job", lambda s, j: _Summary())
    monkeypatch.setattr(fp_service, "fingerprint_coverage", lambda _s: {"downloaded_covers": 100, "fingerprint_count": 90, "coverage_pct": 90.0})
    monkeypatch.setattr(fp_service, "_flush", lambda *a, **k: None)
    monkeypatch.setattr(fp_service, "select", MagicMock())
    session.exec.return_value.all.return_value = []

    fp_service.run_bulk_fingerprints(session, missing_only=True, limit=500, resume=True)
    assert captured.get("after_image_id") is None


def test_valid_fingerprint_row_has_hashes() -> None:
    row = CatalogImageFingerprint(image_id=1, phash="1", dhash="0", ahash="1")
    assert bool(row.phash or row.dhash or row.ahash)
