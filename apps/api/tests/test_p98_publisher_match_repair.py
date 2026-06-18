"""P98 publisher match scoring and repair tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.models.universe import UniverseVolume  # noqa: E402
from app.services.p97_core_run_registry import pick_best_universe_match  # noqa: E402
from app.services.p97_discovered_not_queued_service import build_discovered_not_queued_audit  # noqa: E402
from app.services.p97_queue_repair_service import build_queue_repair_plan  # noqa: E402
from app.services.p98_publisher_match_audit_service import build_publisher_match_audit  # noqa: E402
from app.services.p98_publisher_match_repair_service import (  # noqa: E402
    VOLUME_STATUS_FOREIGN_SUPERSEDED,
    apply_publisher_match_repairs,
    build_publisher_match_repairs,
)
from app.services.p98_publisher_match_service import (  # noqa: E402
    MATCH_EXACT,
    MATCH_FOREIGN,
    publisher_match_type,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _uni(
    session: Session,
    *,
    volume_id: int,
    name: str,
    publisher: str,
    count: int = 100,
    year: int = 2010,
) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=volume_id,
            name=name,
            publisher=publisher,
            count_of_issues=count,
            start_year=year,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    session.commit()


def test_flash_picks_dc_over_ecc(session: Session) -> None:
    _uni(session, volume_id=78610, name="Flash", publisher="ECC Ediciones", count=82, year=2010)
    _uni(session, volume_id=3790, name="The Flash", publisher="DC Comics", count=250, year=1987)
    rows = list(session.exec(select(ComicVineVolumeUniverse)).all())
    best, pub_ok = pick_best_universe_match(
        rows,
        "Flash",
        name_getter=lambda u: u.name,
        publisher_getter=lambda u: u.publisher,
        issue_count_getter=lambda u: u.count_of_issues,
        start_year_getter=lambda u: u.start_year,
    )
    assert best is not None
    assert int(best.volume_id) == 3790
    assert pub_ok is True


def test_publisher_match_type_foreign() -> None:
    assert (
        publisher_match_type(
            expected_publisher="DC Comics",
            matched_publisher="ECC Ediciones",
            volume_name="Flash",
        )
        == MATCH_FOREIGN
    )


def test_audit_flash_exact(session: Session) -> None:
    _uni(session, volume_id=78610, name="Flash", publisher="ECC Ediciones", count=82)
    _uni(session, volume_id=3790, name="The Flash", publisher="DC Comics", count=250, year=1987)
    audit = build_publisher_match_audit(session, dc_queue_limit=0)
    flash = next(r for r in audit if r.core_label == "Flash")
    assert flash.publisher_match_type == MATCH_EXACT
    assert flash.matched_publisher == "DC Comics"


def test_ecc_flash_excluded_from_discovered_not_queued(session: Session) -> None:
    _uni(session, volume_id=78610, name="Flash", publisher="ECC Ediciones", count=82)
    _uni(session, volume_id=3790, name="The Flash", publisher="DC Comics", count=250, year=1987)
    session.add(
        UniverseVolume(
            comicvine_volume_id=78610,
            name="Flash",
            publisher_id=1,
            normalized_name="flash",
        )
    )
    session.commit()
    gaps = build_discovered_not_queued_audit(session)
    assert not any(g.comicvine_volume_id == 78610 for g in gaps)


def test_repair_dry_run_then_apply_supersedes(session: Session) -> None:
    _uni(session, volume_id=78610, name="Flash", publisher="ECC Ediciones", count=82)
    _uni(session, volume_id=3790, name="The Flash", publisher="DC Comics", count=250, year=1987)
    session.add(
        UniverseVolume(
            comicvine_volume_id=78610,
            name="Flash",
            publisher_id=1,
            normalized_name="flash",
            volume_status="active",
        )
    )
    session.commit()
    repairs = build_publisher_match_repairs(session)
    assert any(r.comicvine_volume_id == 78610 for r in repairs)
    apply_publisher_match_repairs(session, repairs, dry_run=True)
    uv = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 78610)
    ).one()
    assert uv.volume_status == "active"
    apply_publisher_match_repairs(session, repairs, dry_run=False)
    session.refresh(uv)
    assert uv.volume_status == VOLUME_STATUS_FOREIGN_SUPERSEDED


def test_queue_plan_flash_add_not_review(session: Session) -> None:
    _uni(
        session,
        volume_id=42285,
        name="Teenage Mutant Ninja Turtles",
        publisher="IDW Publishing",
        count=150,
    )
    _uni(session, volume_id=78610, name="Flash", publisher="ECC Ediciones", count=82)
    _uni(session, volume_id=3790, name="The Flash", publisher="DC Comics", count=250, year=1987)
    plan = build_queue_repair_plan(session)
    assert not any(
        p.comicvine_volume_id == 78610 and p.recommended_action == "REVIEW_PUBLISHER_MISMATCH"
        for p in plan
    )
    tmnt = next(p for p in plan if p.comicvine_volume_id == 42285)
    assert tmnt.recommended_action == "ADD_TO_P97_QUEUE"
