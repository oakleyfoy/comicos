from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"
for _p in (str(API_ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import P97ComicVineVolumeQueue  # noqa: E402
import p97_volume_yield_report as report  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_cli_summary_and_sections(session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    session.add(
        P97ComicVineVolumeQueue(
            comicvine_volume_id=1,
            status="imported",
            series_name="Spawn",
            publisher="Image",
            issues_created=358,
        )
    )
    session.add(
        P97ComicVineVolumeQueue(
            comicvine_volume_id=2,
            status="imported",
            series_name="Invincible",
            publisher="Image",
            issues_created=144,
        )
    )
    session.commit()

    text = report.format_summary_report(session, top_limit=5)
    assert "P97 VOLUME ANALYTICS" in text
    assert "Spawn" in text
    assert "358" in text
    assert "TOP PUBLISHERS" in text

    assert "TOP CREATED VOLUMES" in report.format_top_created(session, limit=2)
    assert "TOP PUBLISHERS" in report.format_publishers(session)
    assert "REMAINING QUEUE FORECAST" in report.format_remaining(session)
    assert "FINAL CATALOG PROJECTION" in report.format_projection(session)
