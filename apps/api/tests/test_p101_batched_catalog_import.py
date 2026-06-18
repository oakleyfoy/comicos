from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p101_batched_catalog_import_service import (
    _ImportContext,
    _partition_records,
    _rebuild_snapshot_issue_id,
    _resolve_issue_id_for_snapshot_record,
)
from app.services.p97_catalog_snapshot_service import (
    CatalogSnapshotImportStats,
    _ImportProgress as P97Progress,
    build_issue_id_lookup_maps,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_issue_with_cv(session: Session, *, cv_id: str, snapshot_key: str) -> tuple[dict, _ImportContext]:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        name="X-Factor",
        normalized_name=normalize_series_name("X-Factor"),
        publisher_id=publisher.id,
        external_source_ids={"COMICVINE": {"1000": True}},
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id or 0),
        publisher_id=publisher.id,
        issue_number="1",
        normalized_issue_number=normalize_issue_number("1"),
        cover_date=date(2024, 1, 1),
        external_source_ids={"COMICVINE": {cv_id: True}, "_primary_source": "COMICVINE"},
    )
    session.add(issue)
    session.commit()

    issue_row = {
        "record_type": "issue",
        "snapshot_key": snapshot_key,
        "comicvine_issue_id": cv_id,
        "series_snapshot_key": "series-1",
        "payload": {"issue_number": "1", "normalized_issue_number": normalize_issue_number("1")},
    }
    series_row = {
        "record_type": "series",
        "snapshot_key": "series-1",
        "comicvine_volume_id": "1000",
        "publisher_snapshot_key": "pub-1",
        "payload": {"name": "X-Factor", "normalized_name": normalize_series_name("X-Factor")},
    }
    records = [
        {"record_type": "publisher", "snapshot_key": "pub-1", "payload": {"name": "Marvel"}},
        series_row,
        issue_row,
    ]
    publishers, series_rows, issue_rows, image_rows = _partition_records(records)
    ctx = _ImportContext(
        records=records,
        publishers=publishers,
        series_rows=series_rows,
        issue_rows=issue_rows,
        image_rows=image_rows,
        publisher_payload_by_key={"pub-1": {"name": "Marvel"}},
        snapshot_volume_ids={"1000"},
        snapshot_issue_cv_ids={cv_id},
        pub_by_norm={},
        pub_by_cv={},
        series_by_volume={},
        series_by_norm_pub={},
        issues_by_cv={},
        issues_by_series_number={},
        snapshot_publisher_id={},
        snapshot_series_id={"series-1": int(series.id or 0)},
        snapshot_issue_id={},
        issue_id_by_cv={},
        issue_id_by_series_number={},
        images_by_issue_url={},
        stats=CatalogSnapshotImportStats(),
    )
    return issue_row, ctx


def test_build_issue_id_lookup_maps_after_expire_all(session: Session) -> None:
    _, ctx = _seed_issue_with_cv(session, cv_id="900001", snapshot_key="issue-1")
    progress = P97Progress(verbose=False)
    by_cv, by_series_number = build_issue_id_lookup_maps(session, progress)
    assert by_cv["900001"] > 0
    assert any(k[1] == normalize_issue_number("1") for k in by_series_number)

    session.expire_all()
    resolved = _rebuild_snapshot_issue_id(
        ctx,
        through_offset=1,
        issue_id_by_cv=by_cv,
        issue_id_by_series_number=by_series_number,
    )
    assert resolved == 1
    assert ctx.snapshot_issue_id["issue-1"] == by_cv["900001"]


def test_rebuild_snapshot_issue_id_does_not_query_per_row(session: Session) -> None:
    issue_row, ctx = _seed_issue_with_cv(session, cv_id="900002", snapshot_key="issue-2")
    progress = P97Progress(verbose=False)
    by_cv, by_series_number = build_issue_id_lookup_maps(session, progress)
    session.expire_all()

    original_exec = session.exec

    def counting_exec(*args, **kwargs):
        statement = args[0] if args else None
        sql = str(getattr(statement, "text", statement) or statement)
        if "catalog_issue" in sql.lower() and "catalog_issue.id" not in sql.lower():
            pytest.fail(f"unexpected per-row catalog_issue ORM query during rebuild: {sql[:120]}")
        return original_exec(*args, **kwargs)

    with mock.patch.object(session, "exec", side_effect=counting_exec):
        count = _rebuild_snapshot_issue_id(
            ctx,
            through_offset=1,
            issue_id_by_cv=by_cv,
            issue_id_by_series_number=by_series_number,
        )
    assert count == 1
    assert ctx.snapshot_issue_id["issue-2"] == by_cv["900002"]

    resolved = _resolve_issue_id_for_snapshot_record(
        ctx,
        issue_row,
        issue_id_by_cv=by_cv,
        issue_id_by_series_number=by_series_number,
    )
    assert resolved == by_cv["900002"]
