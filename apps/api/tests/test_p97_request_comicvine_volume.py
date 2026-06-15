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

from app.models.catalog_p97 import P97VolumeIssueImportQueue  # noqa: E402
from app.services.p97_manual_volume_request_service import (  # noqa: E402
    VolumeSearchCandidate,
    enqueue_manual_volume_request,
    publisher_filter_matches,
    search_comicvine_volumes_for_request,
)
from app.services.p97_volume_issue_import_queue_service import (  # noqa: E402
    STATUS_PENDING,
    STATUS_RUNNING,
    build_volume_issue_import_queue,
    get_top_queued_volumes,
)
from app.services.p97_volume_issue_queue_priority import (  # noqa: E402
    TIER_0_MANUAL,
    TIER_1_CORE,
    MANUAL_REQUEST_PRIORITY_SCORE,
    compute_manual_request_priority,
    compute_volume_import_priority,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class FakeDiscoveryClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def fetch_volume_search_page(self, *, query, offset, limit, field_list=None):
        del query, offset, limit, field_list
        return {"results": self.rows}


def test_search_returns_candidate_volumes() -> None:
    client = FakeDiscoveryClient(
        [
            {
                "id": "4050-999",
                "resource_type": "volume",
                "name": "Absolute Batman",
                "publisher": {"name": "DC Comics"},
                "start_year": 2024,
                "count_of_issues": 12,
                "site_detail_url": "https://comicvine.gamespot.com/absolute-batman/4050-999/",
            },
            {
                "id": "4050-100",
                "resource_type": "volume",
                "name": "Other",
                "publisher": {"name": "Marvel"},
                "start_year": 2020,
                "count_of_issues": 5,
            },
        ]
    )
    results = search_comicvine_volumes_for_request(
        client,  # type: ignore[arg-type]
        query="Absolute Batman",
        publisher="DC Comics",
    )
    assert len(results) == 1
    assert results[0] == VolumeSearchCandidate(
        volume_id=999,
        name="Absolute Batman",
        publisher="DC Comics",
        start_year=2024,
        count_of_issues=12,
        site_detail_url="https://comicvine.gamespot.com/absolute-batman/4050-999/",
    )


def test_publisher_filter_matches_dc_variants() -> None:
    assert publisher_filter_matches("DC Comics", "DC")
    assert publisher_filter_matches("DC", "DC Comics")
    assert not publisher_filter_matches("Marvel", "DC Comics")


def test_manual_request_creates_tier_0_queue_row(session: Session) -> None:
    result = enqueue_manual_volume_request(
        session,
        volume_id=12345,
        notes="scanner testing",
        urgent=False,
        volume_payload={
            "volume_id": 12345,
            "name": "Absolute Batman",
            "publisher": "DC Comics",
            "start_year": 2024,
            "count_of_issues": 12,
        },
    )
    row = result.queue_row
    assert row.launch_priority_tier == TIER_0_MANUAL
    assert row.priority_score == MANUAL_REQUEST_PRIORITY_SCORE
    assert row.status == STATUS_PENDING
    assert row.request_notes == "scanner testing"


def test_manual_request_outranks_normal_queue(session: Session) -> None:
    normal_score = compute_volume_import_priority(
        missing_issue_count=5000,
        count_of_issues=5000,
        coverage_percent=0.0,
        publisher="Marvel",
        name="Amazing Spider-Man",
    ).priority_score
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=1,
            name="Amazing Spider-Man",
            publisher="Marvel",
            count_of_issues=5000,
            existing_issue_count=0,
            missing_issue_count=5000,
            coverage_percent=0.0,
            priority_score=normal_score,
            launch_priority_tier=TIER_1_CORE,
            status=STATUS_PENDING,
        )
    )
    session.commit()

    enqueue_manual_volume_request(
        session,
        volume_id=999,
        urgent=True,
        volume_payload={
            "volume_id": 999,
            "name": "Absolute Batman",
            "publisher": "DC Comics",
            "count_of_issues": 12,
        },
    )
    top = get_top_queued_volumes(session, limit=2)
    assert top[0].comicvine_volume_id == 999
    assert top[0].launch_priority_tier == TIER_0_MANUAL
    assert top[0].priority_score > top[1].priority_score


def test_build_queue_preserves_manual_tier_and_running(session: Session) -> None:
    from app.models.catalog_p97 import ComicVineVolumeUniverse
    from datetime import datetime, timezone

    session.add(
        ComicVineVolumeUniverse(
            volume_id=500,
            name="Absolute Batman",
            publisher="DC Comics",
            count_of_issues=12,
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=500,
            name="Absolute Batman",
            publisher="DC Comics",
            count_of_issues=12,
            existing_issue_count=0,
            missing_issue_count=12,
            coverage_percent=0.0,
            priority_score=MANUAL_REQUEST_PRIORITY_SCORE,
            launch_priority_tier=TIER_0_MANUAL,
            request_notes="keep",
            status=STATUS_RUNNING,
            started_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    from sqlmodel import select

    build_volume_issue_import_queue(session)
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 500
        )
    ).one()
    assert row.launch_priority_tier == TIER_0_MANUAL
    assert row.priority_score == MANUAL_REQUEST_PRIORITY_SCORE
    assert row.status == STATUS_RUNNING
    assert row.request_notes == "keep"


def test_urgent_manual_priority_score() -> None:
    urgent = compute_manual_request_priority(urgent=True)
    normal = compute_manual_request_priority(urgent=False)
    assert urgent.priority_score > normal.priority_score
