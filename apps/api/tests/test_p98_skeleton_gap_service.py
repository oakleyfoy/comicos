"""P98 — skeleton gap service + priority + P97 promotion tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UNIVERSE_VARIANT_STATUS_CATALOGED,
    UNIVERSE_VARIANT_STATUS_DISCOVERED,
    UniverseIssue,
    UniverseVariant,
    UniverseVolume,
)
from app.services.p98_gap_priority_service import (
    is_core_title,
    major_publisher_for,
    publisher_weight,
    recent_year_bonus,
    score_volume,
    volume_size_bonus,
)
from app.services.p98_p97_promotion_service import promote_import_rows
from app.services.p98_skeleton_gap_service import (
    ACTION_BUILD_SHELLS,
    ACTION_IMPORT,
    ACTION_READY,
    STATUS_CATALOG_COMPLETE,
    STATUS_CATALOG_PARTIAL,
    STATUS_SHELL_ONLY,
    STATUS_VOLUME_ONLY,
    build_action_queue,
    classify_volume,
    get_priority_gap_volumes,
    get_publisher_gap_summary,
    get_publisher_volume_status,
)
from app.services.universe.universe_publisher_service import build_publishers_from_discovered_volumes
from app.services.universe.universe_volume_service import build_volumes_from_discovered_universe


def _add_issue(session: Session, *, volume_id: int, number: str, cataloged: bool) -> None:
    issue = UniverseIssue(
        volume_id=volume_id,
        issue_number=number,
        normalized_issue_number=number,
        status=UNIVERSE_ISSUE_STATUS_CATALOGED if cataloged else UNIVERSE_ISSUE_STATUS_DISCOVERED,
    )
    session.add(issue)
    session.flush()
    session.add(
        UniverseVariant(
            issue_id=int(issue.id or 0),
            variant_type="UNKNOWN",
            variant_name="",
            catalog_issue_id=999 if cataloged else None,
            status=UNIVERSE_VARIANT_STATUS_CATALOGED if cataloged else UNIVERSE_VARIANT_STATUS_DISCOVERED,
        )
    )


def seed_gap(session: Session) -> dict[str, int]:
    """Seed publishers/volumes/issues covering every classification."""
    discovered = [
        (88001, "Amazing Spider-Man", "Marvel", 2018, 3),
        (88002, "Avengers", "Marvel", 2018, 5),
        (88003, "Marvel Team-Up", "Marvel", 1972, 2),
        (88004, "Obscure Marvel One-Shot", "Marvel", 1995, 10),
        (88005, "Batman", "DC Comics", 2016, 4),
    ]
    for vid, name, pub, year, count in discovered:
        session.add(
            ComicVineVolumeUniverse(
                volume_id=vid, name=name, publisher=pub, start_year=year, count_of_issues=count
            )
        )
    session.commit()
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)

    vols = {
        int(v.comicvine_volume_id): int(v.id or 0)
        for v in session.exec(select(UniverseVolume)).all()
    }
    # 88001 COMPLETE: 3/3 cataloged
    for n in ("1", "2", "3"):
        _add_issue(session, volume_id=vols[88001], number=n, cataloged=True)
    # 88002 PARTIAL: 1/3 cataloged
    _add_issue(session, volume_id=vols[88002], number="1", cataloged=True)
    _add_issue(session, volume_id=vols[88002], number="2", cataloged=False)
    _add_issue(session, volume_id=vols[88002], number="3", cataloged=False)
    # 88003 SHELL_ONLY: 0/2 cataloged
    _add_issue(session, volume_id=vols[88003], number="1", cataloged=False)
    _add_issue(session, volume_id=vols[88003], number="2", cataloged=False)
    # 88004 VOLUME_ONLY: no issues
    # 88005 DC PARTIAL: 1/2 cataloged
    _add_issue(session, volume_id=vols[88005], number="1", cataloged=True)
    _add_issue(session, volume_id=vols[88005], number="2", cataloged=False)
    session.commit()
    return vols


# ---------------------------------------------------------------------------
# Pure unit tests
# ---------------------------------------------------------------------------


def test_classify_volume_pure() -> None:
    assert classify_volume(0, 0) == STATUS_VOLUME_ONLY
    assert classify_volume(3, 0) == STATUS_SHELL_ONLY
    assert classify_volume(3, 1) == STATUS_CATALOG_PARTIAL
    assert classify_volume(3, 3) == STATUS_CATALOG_COMPLETE
    assert classify_volume(3, 5) == STATUS_CATALOG_COMPLETE


def test_priority_scoring_pure() -> None:
    assert publisher_weight("marvel") == 10000
    assert publisher_weight("dc comics") == 10000
    assert publisher_weight("image comics") == 8000
    assert publisher_weight("some indie press") == 0
    assert major_publisher_for("marvel uk") is not None
    assert is_core_title("Avengers") is True
    assert is_core_title("Random Title") is False
    assert recent_year_bonus(2021) == 3000
    assert recent_year_bonus(2014) == 2000
    assert recent_year_bonus(2003) == 1000
    assert recent_year_bonus(1975) == 0
    assert volume_size_bonus(5000) == 1000
    # Avengers (Marvel, core, 2018, missing 2, size 5)
    assert (
        score_volume(
            publisher_normalized="marvel",
            volume_name="Avengers",
            start_year=2018,
            missing_issue_count=2,
            issue_count=5,
        )
        == 10000 + 200 + 5000 + 2000 + 5
    )


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------


def test_publisher_metrics(client: TestClient, session: Session) -> None:
    seed_gap(session)
    summary = get_publisher_gap_summary(session, publisher="Marvel")
    assert summary.universe_volumes == 4
    assert summary.catalog_complete == 1
    assert summary.catalog_partial == 1
    assert summary.shell_only == 1
    assert summary.volume_only == 1
    assert summary.universe_issues == 8  # 3 + 3 + 2 + 0
    assert summary.catalog_linked_issues == 4  # 3 + 1
    assert summary.discovered_only_issues == 4
    assert 0 < summary.coverage_percent < 100
    assert summary.volume_coverage_percent == 75.0  # 3 of 4 volumes have issues


def test_volume_classification(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = {r.comicvine_volume_id: r for r in get_publisher_volume_status(session, publisher="Marvel")}
    assert rows[88001].status == STATUS_CATALOG_COMPLETE
    assert rows[88001].recommended_action == ACTION_READY
    assert rows[88002].status == STATUS_CATALOG_PARTIAL
    assert rows[88002].recommended_action == ACTION_IMPORT
    assert rows[88003].status == STATUS_SHELL_ONLY
    assert rows[88003].recommended_action == ACTION_IMPORT
    assert rows[88004].status == STATUS_VOLUME_ONLY
    assert rows[88004].recommended_action == ACTION_BUILD_SHELLS
    assert rows[88002].missing_issue_count == 2
    assert rows[88004].missing_issue_count == 10  # expected count for volume-only


def test_dc_report_separates_publishers(client: TestClient, session: Session) -> None:
    seed_gap(session)
    dc = get_publisher_volume_status(session, publisher="DC Comics")
    assert len(dc) == 1
    assert dc[0].comicvine_volume_id == 88005
    assert dc[0].status == STATUS_CATALOG_PARTIAL
    marvel = get_publisher_volume_status(session, publisher="Marvel")
    assert all(r.publisher_name == "Marvel" for r in marvel)
    assert 88005 not in {r.comicvine_volume_id for r in marvel}


def test_priority_ordering(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = get_priority_gap_volumes(session, publisher="Marvel", top=100)
    scores = [r.priority_score for r in rows]
    assert scores == sorted(scores, reverse=True)
    # Complete volume excluded by default.
    assert all(r.status != STATUS_CATALOG_COMPLETE for r in rows)


def test_p97_promotion_dry_run(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = build_action_queue(session, publisher="Marvel")
    result = promote_import_rows(session, rows, apply=False)
    assert result.promotable >= 2  # PARTIAL + SHELL_ONLY
    assert result.created == result.promotable
    assert session.exec(select(P97VolumeIssueImportQueue)).first() is None  # nothing written


def test_p97_promotion_apply(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = build_action_queue(session, publisher="Marvel")
    result = promote_import_rows(session, rows, apply=True)
    assert result.applied is True
    queued = session.exec(select(P97VolumeIssueImportQueue)).all()
    assert len(queued) == result.created
    queued_ids = {q.comicvine_volume_id for q in queued}
    assert 88002 in queued_ids  # PARTIAL
    assert 88003 in queued_ids  # SHELL_ONLY
    assert 88001 not in queued_ids  # COMPLETE not promoted
    assert 88004 not in queued_ids  # VOLUME_ONLY (build shells, not import)

    # Idempotent re-apply updates pending rows, does not duplicate.
    result2 = promote_import_rows(session, rows, apply=True)
    assert result2.created == 0
    assert result2.updated == result.created
    assert len(session.exec(select(P97VolumeIssueImportQueue)).all()) == len(queued)
