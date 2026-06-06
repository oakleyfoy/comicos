from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models.external_catalog import ExternalCatalogSyncRun
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.locg_browser import BrowserCaptureCounters
from app.services.external_catalog.locg_browser_finalize import finalize_browser_capture_sync_run
from app.services.external_catalog.sync_service import (
    SYNC_COMPLETE_WITH_WARNINGS,
    SYNC_FAILED,
    create_sync_run,
    ensure_locg_source,
    SyncCounters,
)


def test_complete_with_warnings_when_parent_done_and_post_loop_error(session: Session) -> None:
    ensure_locg_source(session)
    run = create_sync_run(
        session,
        source_name=LOCG_SOURCE_NAME,
        sync_type="BROWSER",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
    )
    browser = BrowserCaptureCounters(
        list_page_loaded=True,
        list_issues_found=10,
        detail_pages_succeeded=10,
        post_capture_warnings=["browser close: [Errno 22] Invalid argument"],
    )
    counters = SyncCounters(issues_created=3, issues_updated=7, variants_created=5)
    status = finalize_browser_capture_sync_run(
        session,
        run=run,
        page_date=date(2025, 1, 1),
        browser=browser,
        process_counters=counters,
        max_issues=None,
        post_warnings=list(browser.post_capture_warnings),
        capture_exception=OSError(22, "Invalid argument"),
    )
    assert status == SYNC_COMPLETE_WITH_WARNINGS
    refreshed = session.get(ExternalCatalogSyncRun, run.id)
    assert refreshed is not None
    assert refreshed.status == SYNC_COMPLETE_WITH_WARNINGS
    assert refreshed.issues_created == 3
    assert refreshed.issues_updated == 7
    assert refreshed.variants_created == 5
    assert refreshed.error_sample is not None
    assert refreshed.error_sample.get("warnings")


def test_failed_when_parent_incomplete(session: Session) -> None:
    ensure_locg_source(session)
    run = create_sync_run(
        session,
        source_name=LOCG_SOURCE_NAME,
        sync_type="BROWSER",
        start_date=date(2025, 2, 5),
        end_date=date(2025, 2, 5),
    )
    browser = BrowserCaptureCounters(
        list_page_loaded=True,
        list_issues_found=10,
        detail_pages_succeeded=2,
    )
    counters = SyncCounters()
    status = finalize_browser_capture_sync_run(
        session,
        run=run,
        page_date=date(2025, 2, 5),
        browser=browser,
        process_counters=counters,
        max_issues=None,
        post_warnings=[],
        capture_exception=RuntimeError("blocked"),
    )
    assert status == SYNC_FAILED
    refreshed = session.get(ExternalCatalogSyncRun, run.id)
    assert refreshed is not None
    assert refreshed.status == SYNC_FAILED


def test_artifact_write_failure_does_not_raise(tmp_path, monkeypatch) -> None:
    from app.services.external_catalog import locg_capture_certification as cert_mod
    from app.services.external_catalog import locg_capture_io as io_mod

    def _boom(path, payload, *, warnings, label):
        warnings.append(f"{label}: [Errno 22] Invalid argument")

    monkeypatch.setattr(io_mod, "safe_write_json", _boom)
    warnings: list[str] = []
    cert_mod.save_capture_certification_artifacts(
        report_dir=tmp_path,
        cert=cert_mod.LocgCaptureCertificationResult(page_date="2025-01-01"),
        live_page_state={"ok": True},
        source_universe={"ok": True},
        warnings=warnings,
    )
    assert len(warnings) == 3
