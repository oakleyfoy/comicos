"""P104 cover hydration unit tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from sqlmodel import Session, func, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_cover_assets import CatalogCoverAsset, COVER_ASSET_STATUS_COMPLETE
from app.services.p104_cover_hydration_service import (
    _comicvine_cover_from_external_ids,
    _preload_cover_urls_by_issue,
    compute_priority_for_issue,
    hydrate_cover_asset,
    resolve_cover_url_for_issue,
    resolve_cover_url_for_issue_cached,
    run_p104_dry_run,
    run_p104_hydration,
    sync_cover_assets_batch,
    TIER_INVENTORY,
    TIER_MODERN_MAJOR,
    TIER_UPC,
)
from app.services.p104_hydration_perf import P104PerformanceSummary


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


def test_sync_reports_timing(session: Session) -> None:
    _seed_issue_with_cover(session, 3)
    result = sync_cover_assets_batch(session, sync_limit=2)
    assert result.touched == 2
    assert result.timing is not None
    assert result.timing.total >= 0
    assert "cover_url_preload" in result.to_dict()["timing"]


def test_resolve_cover_url_cached_matches_db(session: Session) -> None:
    issue = _seed_issue(session)
    session.add(
        CatalogImage(
            issue_id=int(issue.id),
            source_url="https://example.com/cached.jpg",
            image_type="cover",
            source="TEST",
            download_status="pending",
        )
    )
    session.commit()
    session.refresh(issue)
    cover_map = _preload_cover_urls_by_issue(session)
    url_db, _ = resolve_cover_url_for_issue(session, issue)
    url_cached, _ = resolve_cover_url_for_issue_cached(issue, cover_urls_by_issue=cover_map)
    assert url_db == url_cached


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


def _tiny_jpeg_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (48, 48), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_performance_summary_aggregation() -> None:
    from app.services.p104_hydration_perf import HydrateStageTiming

    perf = P104PerformanceSummary()
    perf.add(HydrateStageTiming(download=1.0, total=2.0))
    perf.add(HydrateStageTiming(download=3.0, total=4.0))
    data = perf.to_dict()
    assert data["assets_timed"] == 2
    assert data["totals_seconds"]["download"] == 4.0
    assert data["avg_seconds_per_asset"]["download"] == 2.0


def test_hydrate_skips_complete_without_reprocess(session: Session) -> None:
    issue = _seed_issue(session)
    session.add(
        CatalogImage(
            issue_id=int(issue.id),
            source_url="https://example.com/skip.jpg",
            image_type="cover",
            source="TEST",
            download_status="pending",
        )
    )
    session.commit()
    sync_cover_assets_batch(session, sync_limit=1)
    session.commit()
    asset = session.exec(select(CatalogCoverAsset)).first()
    assert asset is not None
    asset.status = COVER_ASSET_STATUS_COMPLETE
    asset.verified_at = asset.updated_at
    session.add(asset)
    session.commit()

    with patch(
        "app.services.p104_cover_hydration_service._download_bytes",
        return_value=(_tiny_jpeg_bytes(), "image/jpeg"),
    ) as mocked:
        outcome = hydrate_cover_asset(session, asset, reprocess=False)
        mocked.assert_not_called()
    assert outcome == COVER_ASSET_STATUS_COMPLETE


def test_run_hydration_records_stage_performance(session: Session) -> None:
    _seed_issue_with_cover(session, 2)
    sync_cover_assets_batch(session, sync_limit=2)
    session.commit()
    with patch(
        "app.services.p104_cover_hydration_service._download_bytes",
        return_value=(_tiny_jpeg_bytes(), "image/jpeg"),
    ):
        summary = run_p104_hydration(
            session,
            limit=2,
            download_workers=1,
            process_workers=1,
            downloads_per_minute=600.0,
        )
    assert summary["completed"] >= 2
    assert summary["downloaded"] >= 2
    perf = summary["performance"]
    assert perf["assets_timed"] >= 2
    assert "derivative_resize_write" in perf["totals_seconds"]
    assert summary["progress"]["covers_per_minute"] >= 0
    assert summary["run_asset_complete_count"] >= 2


def test_concurrent_run_summary_matches_db(session: Session) -> None:
    _seed_issue_with_cover(session, 4)
    sync_cover_assets_batch(session, sync_limit=4)
    session.commit()
    with patch(
        "app.services.p104_cover_hydration_service._download_bytes",
        return_value=(_tiny_jpeg_bytes(), "image/jpeg"),
    ):
        summary = run_p104_hydration(
            session,
            limit=4,
            download_workers=2,
            process_workers=2,
            downloads_per_minute=600.0,
        )
    assert summary["performance"]["assets_timed"] >= 4
    assert summary["completed"] >= 4
    assert summary["downloaded"] >= 4
    assert summary["completed"] == summary["run_asset_complete_count"]
    run_id = int(summary["run_id"])
    assets = session.exec(
        select(CatalogCoverAsset).where(CatalogCoverAsset.last_hydration_run_id == run_id)
    ).all()
    assert len(assets) >= 4
    assert all(a.status == COVER_ASSET_STATUS_COMPLETE for a in assets)


def test_reconcile_marks_complete_when_files_exist(session: Session, tmp_path: Path, monkeypatch) -> None:
    issues = _seed_issue_with_cover(session, 1)
    sync_cover_assets_batch(session, sync_limit=1)
    session.commit()
    asset = session.exec(select(CatalogCoverAsset)).first()
    assert asset is not None

    from app.models.catalog_cover_assets import CatalogCoverHydrationRun, HYDRATION_RUN_STATUS_COMPLETED, utc_now

    run = CatalogCoverHydrationRun(mode="hydrate", limit=1, status=HYDRATION_RUN_STATUS_COMPLETED, queued=1)
    session.add(run)
    session.commit()
    run_id = int(run.id or 0)

    monkeypatch.setattr(
        "app.services.p104_cover_hydration_service.P104_LOG_DIR",
        tmp_path / "runs",
    )
    staging = tmp_path / "runs" / f"staging_run_{run_id}"
    staging.mkdir(parents=True)
    (staging / f"{int(asset.id)}.bin").write_bytes(_tiny_jpeg_bytes())

    with patch(
        "app.services.p104_cover_hydration_service._download_bytes",
        return_value=(_tiny_jpeg_bytes(), "image/jpeg"),
    ):
        from app.services.p104_cover_hydration_service import hydrate_cover_asset

        hydrate_cover_asset(session, asset, hydration_run_id=run_id)
        session.commit()

    asset.status = "downloading"
    asset.last_hydration_run_id = None
    session.add(asset)
    session.commit()

    from app.services.p104_cover_hydration_service import reconcile_p104_hydration_run

    report = reconcile_p104_hydration_run(session, run_id, dry_run=False)
    session.refresh(asset)
    assert asset.status == COVER_ASSET_STATUS_COMPLETE
    assert asset.last_hydration_run_id == run_id
    assert report["repaired_count"] >= 1
