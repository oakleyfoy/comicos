"""P98-Base — issue shell builder stability tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import (
    DEFAULT_VARIANT_TYPE,
    UniverseIssue,
    UniverseVariant,
    UniverseVolume,
)
from app.services.universe import universe_issue_service as svc
from app.services.universe.universe_health_service import compute_skeleton_health
from app.services.universe.universe_issue_service import (
    VOLUME_STATUS_VOLUME_ONLY,
    build_issue_shells,
)
from app.services.universe.universe_publisher_service import build_publishers_from_discovered_volumes
from app.services.universe.universe_volume_service import build_volumes_from_discovered_universe


def _seed(session: Session) -> None:
    # Two discovered volumes -> universe publishers/volumes.
    session.add(
        ComicVineVolumeUniverse(
            volume_id=88001, name="Amazing Spider-Man", publisher="Marvel", start_year=1963, count_of_issues=900
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=88002, name="Batman", publisher="DC Comics", start_year=1940, count_of_issues=800
        )
    )
    # A discovered volume with NO catalog source -> should become VOLUME_ONLY.
    session.add(
        ComicVineVolumeUniverse(
            volume_id=88003, name="Obscure Mini", publisher="Indie", start_year=2001, count_of_issues=4
        )
    )
    session.commit()
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)

    # Catalog source: Spider-Man (88001) two issues, Batman (88002) one issue.
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    asm = CatalogSeries(
        publisher_id=pub.id,
        name="Amazing Spider-Man",
        normalized_name="amazing spider man",
        start_year=1963,
        external_source_ids={"COMICVINE": {"88001": True}},
    )
    bat = CatalogSeries(
        publisher_id=pub.id,
        name="Batman",
        normalized_name="batman",
        start_year=1940,
        external_source_ids={"COMICVINE": {"88002": True}},
    )
    session.add(asm)
    session.add(bat)
    session.flush()
    session.add(CatalogIssue(series_id=int(asm.id), issue_number="300", normalized_issue_number="300", title="Venom"))
    session.add(CatalogIssue(series_id=int(asm.id), issue_number="347", normalized_issue_number="347", title="S&M"))
    session.add(CatalogIssue(series_id=int(bat.id), issue_number="497", normalized_issue_number="497", title="Bane"))
    session.commit()


def test_builder_selects_universe_volumes(client: TestClient, session: Session) -> None:
    _seed(session)
    selected = svc._select_universe_volumes(
        session, publisher=None, start_after_volume_id=None, limit_volumes=None
    )
    assert len(selected) == 3
    limited = svc._select_universe_volumes(
        session, publisher=None, start_after_volume_id=None, limit_volumes=1
    )
    assert len(limited) == 1
    marvel_only = svc._select_universe_volumes(
        session, publisher="Marvel", start_after_volume_id=None, limit_volumes=None
    )
    assert len(marvel_only) == 1


def test_builder_creates_issue_and_variant_shells(client: TestClient, session: Session) -> None:
    _seed(session)
    stats = build_issue_shells(session)
    assert stats.issues_created == 3
    assert stats.variants_created == 3
    assert stats.skipped_no_source == 1  # the obscure volume with no source

    issues = session.exec(select(UniverseIssue)).all()
    assert len(issues) == 3
    for issue in issues:
        variants = session.exec(
            select(UniverseVariant).where(UniverseVariant.issue_id == issue.id)
        ).all()
        assert len(variants) >= 1
        assert any(v.variant_type == DEFAULT_VARIANT_TYPE for v in variants)


def test_builder_marks_volume_only(client: TestClient, session: Session) -> None:
    _seed(session)
    stats = build_issue_shells(session)
    assert 88003 in stats.volume_only_ids
    vol = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88003)
    ).first()
    assert vol.volume_status == VOLUME_STATUS_VOLUME_ONLY


def test_builder_rerun_is_idempotent(client: TestClient, session: Session) -> None:
    _seed(session)
    build_issue_shells(session)
    issues_before = len(session.exec(select(UniverseIssue)).all())
    variants_before = len(session.exec(select(UniverseVariant)).all())

    stats2 = build_issue_shells(session, refresh=True)
    assert stats2.issues_created == 0
    assert stats2.variants_created == 0
    assert len(session.exec(select(UniverseIssue)).all()) == issues_before
    assert len(session.exec(select(UniverseVariant)).all()) == variants_before


def test_resume_skips_processed_volumes(client: TestClient, session: Session) -> None:
    _seed(session)
    build_issue_shells(session)
    stats2 = build_issue_shells(session)  # default: refresh=False
    assert stats2.processed == 0
    assert stats2.skipped_existing >= 2  # Spider-Man + Batman already built
    assert stats2.issues_created == 0


def test_failed_volume_does_not_abort(client: TestClient, session: Session, monkeypatch) -> None:
    _seed(session)
    original = svc._build_single_volume

    def _flaky(session_, *, volume, source_series_ids, stats):
        if int(volume.comicvine_volume_id) == 88001:
            raise RuntimeError("boom")
        return original(session_, volume=volume, source_series_ids=source_series_ids, stats=stats)

    monkeypatch.setattr(svc, "_build_single_volume", _flaky)
    stats = build_issue_shells(session)

    assert stats.failed == 1
    assert 88001 in stats.failed_volume_ids
    # Batman (88002) still built despite Spider-Man failure.
    bat_vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88002)).first()
    bat_issue = session.exec(select(UniverseIssue).where(UniverseIssue.volume_id == bat_vol.id)).first()
    assert bat_issue is not None


def test_dry_run_creates_no_rows(client: TestClient, session: Session) -> None:
    _seed(session)
    stats = build_issue_shells(session, dry_run=True)
    assert stats.issues_created == 3
    assert len(session.exec(select(UniverseIssue)).all()) == 0
    assert len(session.exec(select(UniverseVariant)).all()) == 0


def test_health_report_counts(client: TestClient, session: Session) -> None:
    _seed(session)
    build_issue_shells(session)
    health = compute_skeleton_health(session)
    assert health.publishers == 3
    assert health.volumes == 3
    assert health.issues == 3
    assert health.variants == 3
    assert health.issues_without_variants == 0
    assert health.catalog_linked_issues == 3
    assert health.volume_only_volumes == 1
