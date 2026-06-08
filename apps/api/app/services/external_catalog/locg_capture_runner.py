"""Unattended LoCG browser capture: final summary and exit codes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.external_catalog.sync_service import (
    SYNC_COMPLETE_WITH_WARNINGS,
    SYNC_COMPLETED,
    SYNC_FAILED,
    SYNC_PARTIAL,
    parent_browser_capture_complete,
)

STATUS_DISPLAY = {
    SYNC_COMPLETED: "COMPLETE",
    SYNC_COMPLETE_WITH_WARNINGS: "COMPLETE_WITH_WARNINGS",
    SYNC_PARTIAL: "PARTIAL",
    SYNC_FAILED: "FAILED",
    "DRY_RUN": "DRY_RUN",
    "BLOCKED": "BLOCKED",
    "CERTIFICATION_FAILED": "CERTIFICATION_FAILED",
    "DISCOVERY_FAILED": "DISCOVERY_FAILED",
}


def display_run_status(status: str) -> str:
    return STATUS_DISPLAY.get(status, status)


def variant_upsert_failure_count(variant_skipped: dict[str, Any] | None) -> int:
    if not variant_skipped:
        return 0
    return int(variant_skipped.get("variant_upsert_failure") or 0)


def skipped_missing_parent_count(variant_skipped: dict[str, Any] | None) -> int:
    if not variant_skipped:
        return 0
    return int(variant_skipped.get("skipped_missing_parent") or 0)


def resolve_capture_exit_code(
    *,
    run_status: str,
    list_page_loaded: bool,
    list_issues_found: int,
    detail_pages_succeeded: int,
    max_issues: int | None,
    hard_failure: bool = False,
    intentional_parent_skips: int = 0,
    resume_parent_skips: int = 0,
) -> int:
    """Exit 0 only for successful parent capture; 1 for real capture failures."""
    if hard_failure:
        return 1
    if not list_page_loaded:
        return 1
    parent_done = parent_browser_capture_complete(
        list_page_loaded=list_page_loaded,
        list_issues_found=list_issues_found,
        detail_pages_succeeded=detail_pages_succeeded,
        max_issues=max_issues,
        intentional_parent_skips=intentional_parent_skips,
        resume_parent_skips=resume_parent_skips,
    )
    if run_status in {SYNC_COMPLETED, SYNC_COMPLETE_WITH_WARNINGS, "DRY_RUN"}:
        return 0 if parent_done or run_status == "DRY_RUN" else 1
    return 1


def print_final_capture_summary(
    *,
    page_date: str,
    run_status: str,
    parent_queue: int,
    parent_captured: int,
    db_issues: int,
    db_variants: int,
    skipped_missing_parent: int,
    variant_upsert_failures: int,
    warnings: list[str],
    failures: list[str],
    elapsed_seconds: float,
    crosswalk_skipped: bool,
    raw_path: str,
) -> None:
    lines = [
        "--- LoCG capture final summary ---",
        f"Date: {page_date}",
        f"Run status: {display_run_status(run_status)}",
        f"Parent queue: {parent_queue}",
        f"Parent captured: {parent_captured}",
        f"DB issues: {db_issues}",
        f"DB variants: {db_variants}",
        f"Skipped missing parent: {skipped_missing_parent}",
        f"Variant upsert failures: {variant_upsert_failures}",
        f"Warnings: {warnings if warnings else '[]'}",
        f"Failures: {failures if failures else '[]'}",
        f"Elapsed seconds: {round(elapsed_seconds, 1)}",
        f"Crosswalk skipped: {crosswalk_skipped}",
        f"Raw path: {raw_path}",
        "--- end final summary ---",
    ]
    print("\n".join(lines), flush=True)


def default_raw_path(page_date: str) -> str:
    api_root = Path(__file__).resolve().parents[3]
    return str(api_root.parent.parent / "data" / "locg_browser_capture" / page_date)


def merge_run_warnings(run: Any, warnings: list[str]) -> None:
    if run is None or not getattr(run, "error_sample", None):
        return
    sample = run.error_sample
    if not isinstance(sample, dict):
        return
    for item in sample.get("warnings") or []:
        text = str(item)
        if text not in warnings:
            warnings.append(text)
