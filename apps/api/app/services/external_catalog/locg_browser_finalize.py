"""Finalize LoCG browser sync runs: separate capture success from post-loop failures."""

from __future__ import annotations

import logging
from datetime import date

from sqlmodel import Session

from app.services.external_catalog.locg_browser import BrowserCaptureCounters
from app.services.external_catalog.sync_service import (
    SYNC_COMPLETE_WITH_WARNINGS,
    SYNC_COMPLETED,
    SYNC_FAILED,
    SYNC_PARTIAL,
    complete_sync_run,
    count_locg_release_date_persistence,
    fail_sync_run_preserving_counters,
    parent_browser_capture_complete,
    SyncCounters,
)
from app.models.external_catalog import ExternalCatalogSyncRun

logger = logging.getLogger(__name__)


def apply_db_persistence_to_counters(
    session: Session,
    *,
    release_date: date,
    counters: SyncCounters,
) -> dict[str, int]:
    """When in-memory counters were lost on failure path, infer activity from DB rows for the date."""
    counts = count_locg_release_date_persistence(session, release_date=release_date)
    if counters.issues_created == 0 and counters.issues_updated == 0 and counts["issues"] > 0:
        counters.issues_updated = counts["issues"]
    return counts


def resolve_browser_capture_status(
    *,
    browser: BrowserCaptureCounters,
    process_counters: SyncCounters,
    max_issues: int | None,
    post_warnings: list[str],
    capture_exception: BaseException | None,
) -> str:
    parent_done = parent_browser_capture_complete(
        list_page_loaded=browser.list_page_loaded,
        list_issues_found=browser.list_issues_found,
        detail_pages_succeeded=browser.detail_pages_succeeded,
        max_issues=max_issues,
        intentional_parent_skips=browser.intentional_parent_skips,
        resume_parent_skips=browser.resume_parent_skips,
    )
    if capture_exception is not None and not parent_done:
        return SYNC_FAILED
    if parent_done and (post_warnings or capture_exception is not None):
        return SYNC_COMPLETE_WITH_WARNINGS
    if process_counters.errors_count or browser.errors_count:
        return SYNC_PARTIAL
    accounted = (
        browser.detail_pages_succeeded
        + browser.intentional_parent_skips
        + browser.resume_parent_skips
    )
    if accounted < browser.list_issues_found and max_issues is None:
        return SYNC_PARTIAL
    return SYNC_COMPLETED


def log_browser_capture_finalize(
    *,
    page_date: date,
    browser: BrowserCaptureCounters,
    db_counts: dict[str, int],
    post_warnings: list[str],
    status: str,
) -> None:
    logger.info(
        "locg browser capture finalize date=%s parent_queue=%s parent_completed=%s "
        "db_issues=%s db_variants=%s status=%s post_warnings=%s",
        page_date.isoformat(),
        browser.list_issues_found,
        browser.detail_pages_succeeded,
        db_counts.get("issues"),
        db_counts.get("variants"),
        status,
        len(post_warnings),
    )
    for warning in post_warnings:
        logger.warning("locg browser capture post-loop: %s", warning)


def finalize_browser_capture_sync_run(
    session: Session,
    *,
    run: ExternalCatalogSyncRun,
    page_date: date,
    browser: BrowserCaptureCounters,
    process_counters: SyncCounters,
    max_issues: int | None,
    post_warnings: list[str],
    capture_exception: BaseException | None = None,
) -> str:
    process_counters.pages_scanned = 1 if browser.list_page_loaded else 0
    process_counters.errors_count = max(process_counters.errors_count, browser.errors_count)
    if browser.error_sample:
        merged = list(process_counters.error_sample)
        for msg in browser.error_sample:
            if len(merged) >= 20:
                break
            if msg not in merged:
                merged.append(msg)
        process_counters.error_sample = merged

    if capture_exception is not None:
        msg = str(capture_exception)
        if len(process_counters.error_sample) < 20 and msg not in process_counters.error_sample:
            process_counters.error_sample.append(msg)

    db_counts = apply_db_persistence_to_counters(session, release_date=page_date, counters=process_counters)
    status = resolve_browser_capture_status(
        browser=browser,
        process_counters=process_counters,
        max_issues=max_issues,
        post_warnings=post_warnings,
        capture_exception=capture_exception,
    )
    log_browser_capture_finalize(
        page_date=page_date,
        browser=browser,
        db_counts=db_counts,
        post_warnings=post_warnings,
        status=status,
    )

    parent_done = parent_browser_capture_complete(
        list_page_loaded=browser.list_page_loaded,
        list_issues_found=browser.list_issues_found,
        detail_pages_succeeded=browser.detail_pages_succeeded,
        max_issues=max_issues,
        intentional_parent_skips=browser.intentional_parent_skips,
        resume_parent_skips=browser.resume_parent_skips,
    )
    if capture_exception is not None and not parent_done:
        fail_sync_run_preserving_counters(
            session,
            run=run,
            counters=process_counters,
            message=str(capture_exception),
            warnings=post_warnings or None,
        )
        return SYNC_FAILED

    complete_sync_run(
        session,
        run=run,
        counters=process_counters,
        status=status,
        warnings=post_warnings or None,
    )
    return status
