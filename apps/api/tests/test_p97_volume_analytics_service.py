from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.models.catalog_p97 import P97ComicVineVolumeQueue  # noqa: E402
from app.services import p97_volume_analytics_service as analytics  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _queue(
    session: Session,
    volume_id: int,
    *,
    status: str = "pending",
    publisher: str | None = None,
    series: str | None = None,
    created: int = 0,
    updated: int = 0,
    requests: int = 0,
) -> None:
    session.add(
        P97ComicVineVolumeQueue(
            comicvine_volume_id=volume_id,
            status=status,
            publisher=publisher,
            series_name=series,
            issues_created=created,
            issues_updated=updated,
            api_requests_used=requests,
        )
    )
    session.commit()


def _catalog_issues(session: Session, count: int) -> None:
    pub = CatalogPublisher(name="Test Pub", normalized_name="test pub")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(name="Test Series", normalized_name="test series", publisher_id=pub.id)
    session.add(series)
    session.commit()
    session.refresh(series)
    for i in range(count):
        num = str(i + 1)
        session.add(
            CatalogIssue(
                series_id=series.id,
                issue_number=num,
                normalized_issue_number=num,
            )
        )
    session.commit()


def test_volume_summary_counts_and_averages(session: Session) -> None:
    _queue(session, 1, status="imported", publisher="Marvel", created=100, updated=10, requests=10)
    _queue(session, 2, status="imported", publisher="Marvel", created=50, updated=5, requests=5)
    _queue(session, 3, status="pending", publisher="Marvel")
    _queue(session, 4, status="pending", publisher="DC")
    _queue(session, 5, status="failed")
    _catalog_issues(session, 3)

    summary = analytics.get_volume_summary(session)
    assert summary.total_volumes == 5
    assert summary.imported_volumes == 2
    assert summary.pending_volumes == 2
    assert summary.failed_volumes == 1
    assert summary.issues_created == 150
    assert summary.issues_updated == 15
    assert summary.avg_issues_per_volume == pytest.approx(75.0)
    assert summary.avg_issues_per_request == pytest.approx(10.0)
    assert summary.current_catalog_size == 3
    # Marvel avg 75; pending Marvel + DC each get 75 → 150 remaining
    assert summary.projected_remaining_issues == 150
    assert summary.projected_final_catalog_size == 153


def test_top_created_and_updated_sorting(session: Session) -> None:
    _queue(session, 10, status="imported", series="Spawn", created=358, updated=1)
    _queue(session, 11, status="imported", series="Invincible", created=144, updated=50)
    _queue(session, 12, status="imported", series="Low", created=10, updated=200)
    _queue(session, 13, status="pending", series="Pending", created=999, updated=999)

    top_created = analytics.get_top_created_volumes(session, limit=10)
    assert [r.volume_id for r in top_created] == [10, 11, 12]
    assert top_created[0].issues_per_request == 0.0

    top_updated = analytics.get_top_updated_volumes(session, limit=10)
    assert [r.volume_id for r in top_updated] == [12, 11, 10]


def test_publisher_yields_aggregate(session: Session) -> None:
    _queue(session, 1, status="imported", publisher="Marvel", created=40, updated=4, requests=4)
    _queue(session, 2, status="imported", publisher="Marvel", created=60, updated=6, requests=6)
    _queue(session, 3, status="imported", publisher="DC", created=30, updated=3, requests=10)

    rows = analytics.get_publisher_yields(session)
    assert [r.publisher for r in rows] == ["Marvel", "DC"]
    assert rows[0].volume_count == 2
    assert rows[0].issues_created == 100
    assert rows[0].avg_issues_per_volume == pytest.approx(50.0)
    assert rows[0].avg_created_per_volume == pytest.approx(50.0)
    assert rows[0].avg_requests_per_volume == pytest.approx(5.0)
    assert rows[0].avg_issues_per_request == pytest.approx(10.0)


def test_remaining_forecast_uses_publisher_then_global_average(session: Session) -> None:
    _queue(session, 1, status="imported", publisher="Marvel", created=20, requests=2)
    _queue(session, 2, status="imported", publisher="Marvel", created=40, requests=4)
    _queue(session, 3, status="pending", publisher="Marvel", series="Marvel Pending")
    _queue(session, 4, status="pending", publisher="Image", series="Image Pending")

    forecast = analytics.get_remaining_queue_forecast(session)
    by_id = {row.volume_id: row for row in forecast}
    assert by_id[3].estimated_remaining_issues == 30
    assert by_id[4].estimated_remaining_issues == 30

    projection = analytics.get_projected_final_catalog_size(session)
    assert projection.projected_remaining_issues == 60
