from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(API_ROOT), str(API_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import P97ComicVineVolumeQueue  # noqa: E402
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget  # noqa: E402
import p97_volume_queue_watch as watch  # noqa: E402

NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add(session, volume_id, status, *, issues_created=0, issues_updated=0, last_imported_at=None, series=None):
    row = P97ComicVineVolumeQueue(
        comicvine_volume_id=volume_id,
        status=status,
        series_name=series,
        issues_created=issues_created,
        issues_updated=issues_updated,
        last_imported_at=last_imported_at,
    )
    session.add(row)
    session.commit()


def test_collect_watch_report_counts_and_budget(session: Session) -> None:
    _add(session, 1, "pending")
    _add(session, 2, "pending")
    _add(session, 3, "imported", issues_created=20, last_imported_at=NOW, series="Amazing Spider-Man")
    _add(session, 4, "failed")
    _add(session, 5, "throttled")

    budget = ComicVineRateBudget(session, max_requests_per_hour=120)
    for _ in range(7):
        budget.record_request(request_type="issue_import", now=NOW - timedelta(minutes=1))

    report = watch.collect_watch_report(session, max_requests_per_hour=120, now=NOW)
    assert report["queue_pending"] == 2
    assert report["queue_imported"] == 1
    assert report["queue_failed"] == 1
    assert report["queue_throttled"] == 1
    assert report["requests_last_hour"] == 7
    assert report["request_budget_remaining"] == 113
    assert report["issues_created_today"] == 20
    assert report["last_imported_volume_id"] == 3
    assert report["last_imported_series"] == "Amazing Spider-Man"
    assert report["remaining_to_150k"] >= 0
    assert report["remaining_to_200k"] >= 0


def test_collect_watch_report_reflects_420(session: Session) -> None:
    budget = ComicVineRateBudget(session, max_requests_per_hour=120, pause_hours_on_420=4)
    budget.record_420(now=NOW)
    report = watch.collect_watch_report(session, max_requests_per_hour=120, now=NOW)
    assert report["last_420_at"] is not None
    assert report["pause_until"] is not None


def test_report_is_json_serializable_and_has_required_fields(session: Session) -> None:
    report = watch.collect_watch_report(session, max_requests_per_hour=120, now=NOW)
    blob = json.dumps(report)
    for key in (
        "status",
        "queue_pending",
        "queue_imported",
        "queue_failed",
        "queue_throttled",
        "requests_last_hour",
        "request_budget_remaining",
        "last_420_at",
        "pause_until",
        "issues_created_today",
        "issues_per_api_request",
        "current_catalog_issues",
        "remaining_to_150k",
        "remaining_to_200k",
        "last_imported_volume_id",
        "last_imported_series",
    ):
        assert key in report
    assert isinstance(blob, str)


def test_format_table_shows_budget_and_420(session: Session) -> None:
    progress = {"status": "running", "issues_created_run": 30, "api_requests_run": 3, "eta_days_to_150k": 5.0}
    report = watch.collect_watch_report(session, max_requests_per_hour=120, progress=progress, now=NOW)
    table = watch.format_table(report)
    assert "P97 Known Good Volume Queue" in table
    assert "Budget remaining" in table
    assert "Last 420 at" in table
    assert "Issues / API request" in table
    # issues_per_api_request derived from run artifact = 30 / 3 = 10
    assert report["issues_per_api_request"] == 10.0
