from __future__ import annotations

from app.services.external_catalog.locg_browser import BrowserCaptureCounters
from app.services.external_catalog.locg_browser_user_skip import (
    UserSkipMatcher,
    normalize_detail_url,
    record_skipped_blocked_detail,
)
from app.services.external_catalog.locg_capture_certification import (
    certify_locg_capture,
    evaluate_proof_run_completeness,
)
from app.services.external_catalog.locg_capture_runner import resolve_capture_exit_code
from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit
from app.services.external_catalog.sync_service import (
    SYNC_COMPLETED,
    parent_browser_capture_complete,
)


def test_normalize_detail_url_strips_trailing_slash() -> None:
    a = normalize_detail_url("https://leagueofcomicgeeks.com/comic/3638265/you-never-heard-of-me-5/")
    b = normalize_detail_url("https://leagueofcomicgeeks.com/comic/3638265/you-never-heard-of-me-5")
    assert a == b


def test_user_skip_matcher_url_and_title() -> None:
    matcher = UserSkipMatcher.from_cli(
        urls=["https://leagueofcomicgeeks.com/comic/3638265/you-never-heard-of-me-5"],
        titles=["You Never Heard of Me"],
    )
    assert matcher.matches(
        url="https://leagueofcomicgeeks.com/comic/3638265/you-never-heard-of-me-5/",
        title="Something else",
    )
    assert matcher.matches(url="https://example.com/x", title="You Never Heard of Me #5")
    assert not matcher.matches(url="https://example.com/x", title="Other Comic")


def test_parent_complete_counts_intentional_and_resume_skips() -> None:
    assert parent_browser_capture_complete(
        list_page_loaded=True,
        list_issues_found=10,
        detail_pages_succeeded=8,
        max_issues=None,
        intentional_parent_skips=1,
        resume_parent_skips=1,
    )
    assert resolve_capture_exit_code(
        run_status=SYNC_COMPLETED,
        list_page_loaded=True,
        list_issues_found=10,
        detail_pages_succeeded=8,
        max_issues=None,
        intentional_parent_skips=1,
        resume_parent_skips=1,
    ) == 0


def test_record_skipped_blocked_detail_updates_cert_persistence_fields() -> None:
    counters = BrowserCaptureCounters()
    record_skipped_blocked_detail(
        counters,
        url="https://leagueofcomicgeeks.com/comic/3638265/you-never-heard-of-me-5",
        title="You Never Heard of Me #5",
    )
    assert counters.intentional_parent_skips == 1
    assert counters.skipped_blocked_details[0]["reason"] == "skipped_blocked_detail"

    audit = ListDiscoveryAudit(
        total_li_issue_rows=100,
        parent_issue_rows=10,
        variant_rows=0,
        other_release_rows=90,
        final_parent_issue_queue_count=10,
        final_variant_queue_count=0,
        pagination_mechanism="scroll",
        pagination_extend_calls=1,
        scroll_row_count_stabilized=True,
    )
    _fail, assessment, _warn = evaluate_proof_run_completeness(
        audit,
        list_variants_found=0,
        list_variants_persisted=0,
        detail_pages_succeeded=9,
        detail_pages_attempted=9,
        variant_skipped_reason_counts={"skipped_blocked_detail": 1},
        intentional_parent_skips=1,
        resume_parent_skips=0,
    )
    assert assessment["parent_details_complete"] is True
