"""P104 cover hydration unit tests."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, func, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_cover_assets import CatalogCoverAsset, COVER_ASSET_STATUS_COMPLETE
from app.services.p104_cover_hydration_service import (
    _comicvine_cover_from_external_ids,
    compute_priority_for_issue,
    resolve_cover_url_for_issue,
    run_p104_dry_run,
    sync_cover_assets_batch,
    TIER_INVENTORY,
    TIER_MODERN_MAJOR,
    TIER_UPC,
)


def _seed_issue(session: Session, *, publisher: str = "DC Comics", year: int = 2018) -> CatalogIssue:
    pub = CatalogPublisher(name=publisher, normalized_name=publisher.lower())
    session.add(pub)
    session.commit()
    series = CatalogSeries(
        name="Test Series",
        normalized_name="test series",
        publisher_id=int(pub.id),
        start_year=year,
    )
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="1",
        normalized_issue_number="1",
        cover_date=date(year, 1, 1),
    )
    session.add(issue)
    session.commit()
    return issue


def test_resolve_cover_url_prefers_catalog_image(session: Session) -> None:
    issue = _seed_issue(session)
    session.add(
        CatalogImage(
            issue_id=int(issue.id),
            source_url="https://example.com/cover.jpg",
            image_type="cover",
            source="COMICVINE",
            download_status="pending",
        )
    )
    session.commit()
    url, source = resolve_cover_url_for_issue(session, issue)
    assert url == "https://example.com/cover.jpg"
    assert source == "COMICVINE"


def test_comicvine_meta_fallback_without_live_api(session: Session) -> None:
    issue = _seed_issue(session)
    issue.external_source_ids = {"COMICVINE": {"image_url": "https://example.com/cv.jpg"}}
    session.add(issue)
    session.commit()
    url, source = resolve_cover_url_for_issue(session, issue)
    assert url == "https://example.com/cv.jpg"
    assert source == "COMICVINE_META"


def test_comicvine_nested_external_ids() -> None:
    url = _comicvine_cover_from_external_ids({"COMICVINE": {"12345": {"cover_image_url": "https://x/y.jpg"}}})
    assert url == "https://x/y.jpg"


def test_priority_tiers(session: Session) -> None:
    issue = _seed_issue(session, publisher="DC Comics", year=2015)
    score, tier = compute_priority_for_issue(
        session,
        issue,
        inventory_ids={int(issue.id)},
        upc_ids=set(),
        publisher_name="DC Comics",
    )
    assert tier == TIER_INVENTORY
    assert score == 100

    score2, tier2 = compute_priority_for_issue(
        session,
        issue,
        inventory_ids=set(),
        upc_ids={int(issue.id)},
        publisher_name="DC Comics",
    )
    assert tier2 == TIER_UPC

    score3, tier3 = compute_priority_for_issue(
        session,
        issue,
        inventory_ids=set(),
        upc_ids=set(),
        publisher_name="DC Comics",
    )
    assert tier3 == TIER_MODERN_MAJOR


def test_dry_run_builds_queue(session: Session) -> None:
    issue = _seed_issue(session)
    session.add(
        CatalogImage(
            issue_id=int(issue.id),
            source_url="https://example.com/pilot.jpg",
            image_type="cover",
            source="TEST",
            download_status="pending",
        )
    )
    session.commit()
    report = run_p104_dry_run(session, pilot_limit=10, sync_limit=10)
    assert report.pilot_would_process >= 1
    assert report.assets_total >= 1


def _seed_issue_with_cover(session: Session, n: int, base: str = "https://example.com/c") -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    for i in range(n):
        issue = _seed_issue(session, publisher=f"Pub {i}", year=2018)
        session.add(
            CatalogImage(
                issue_id=int(issue.id),
                source_url=f"{base}/{i}.jpg",
                image_type="cover",
                source="TEST",
                download_status="pending",
            )
        )
        issues.append(issue)
    session.commit()
    return issues


def test_sync_limit_expands_queue_without_duplicating_completed(session: Session) -> None:
    issues = _seed_issue_with_cover(session, 8)
    first = sync_cover_assets_batch(session, sync_limit=3)
    session.commit()
    assert first.created == 3
    assert first.touched == 3

    asset = session.exec(
        select(CatalogCoverAsset).where(CatalogCoverAsset.catalog_issue_id == int(issues[0].id))
    ).first()
    assert asset is not None
    asset.status = COVER_ASSET_STATUS_COMPLETE
    asset.verified_at = asset.updated_at
    session.add(asset)
    session.commit()

    second = sync_cover_assets_batch(session, sync_limit=5)
    session.commit()
    assert second.skipped_complete >= 1
    assert second.created >= 2
    total = session.exec(select(func.count()).select_from(CatalogCoverAsset)).one()
    total_n = int(total[0] if isinstance(total, tuple) else total)
    assert total_n >= 5
    assert total_n <= 8
