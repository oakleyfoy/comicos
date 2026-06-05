from __future__ import annotations

from datetime import date

from app.services.external_catalog.locg_capture_certification import (
    certify_locg_capture,
    evaluate_proof_run_completeness,
)
from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit

JULY_29_LOG = [
    {"phase": "before_text_view", "li_issue_rows": 317, "data_list_offset": "317"},
    {"phase": "after_text_view", "li_issue_rows": 317, "data_list_offset": "0"},
    {"phase": "after_scroll_to_bottom_1", "li_issue_rows": 317},
    {"phase": "after_scroll_to_bottom_2", "li_issue_rows": 317},
]


def test_july_29_lighter_week_passes_completeness_signals() -> None:
    audit = ListDiscoveryAudit(
        total_li_issue_rows=317,
        parent_issue_rows=98,
        variant_rows=219,
        other_release_rows=0,
        pagination_extend_now=None,
        pagination_mechanism="hidden_api_get_comics_detected_no_extend",
        discovery_row_count_log=JULY_29_LOG,
        scroll_row_count_stabilized=True,
        scroll_final_li_issue_rows=317,
    )
    fail, assessment, _warnings = evaluate_proof_run_completeness(
        audit,
        list_variants_found=219,
        list_variants_persisted=219,
        detail_pages_succeeded=98,
        detail_pages_attempted=98,
        variant_skipped_reason_counts={"skipped_missing_parent": 0, "variant_upsert_failure": 0},
    )
    assert fail is None
    assert assessment["legitimately_lighter_release_week"] is True
    assert assessment["scroll_stabilized"] is True


def test_truncated_initial_dom_without_scroll_growth_fails() -> None:
    audit = ListDiscoveryAudit(
        total_li_issue_rows=165,
        parent_issue_rows=31,
        variant_rows=134,
        discovery_row_count_log=[
            {"phase": "before_text_view", "li_issue_rows": 165},
            {"phase": "after_scroll_to_bottom_1", "li_issue_rows": 165},
        ],
    )
    fail, _, _ = evaluate_proof_run_completeness(
        audit,
        list_variants_found=134,
        list_variants_persisted=134,
        detail_pages_succeeded=31,
        detail_pages_attempted=31,
        variant_skipped_reason_counts={},
    )
    assert fail is not None
    assert "truncated" in fail.lower() or "scroll growth" in fail.lower()


def test_certify_july_29_capture_passes() -> None:
    cert = certify_locg_capture(
        page_date=date(2026, 7, 29),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/07/29",
        page_title="New Comics",
        html='<div id="comic-list-block" data-list="releases" data-date-type="week" '
        'data-date="2026-07-29"></div>',
        discovery_audit=ListDiscoveryAudit(
            total_li_issue_rows=317,
            parent_issue_rows=98,
            variant_rows=219,
            discovery_row_count_log=JULY_29_LOG,
            scroll_row_count_stabilized=True,
        ),
        list_variants_found=219,
        list_variants_persisted=219,
        detail_pages_succeeded=98,
        detail_pages_attempted=98,
        dry_run=False,
        parent_detail_seconds=[1.0] * 98,
        variant_skipped_reason_counts={
            "skipped_missing_parent": 0,
            "variant_upsert_failure": 0,
        },
    )
    assert cert.passed
    assert cert.completeness["proof_run_assessment"]["legitimately_lighter_release_week"]
