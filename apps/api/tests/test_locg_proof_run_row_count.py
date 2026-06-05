from __future__ import annotations

from datetime import date

from app.services.external_catalog.locg_capture_certification import certify_locg_capture
from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit


def test_proof_run_fails_june24_sized_incomplete_list() -> None:
    audit = ListDiscoveryAudit(
        total_li_issue_rows=165,
        parent_issue_rows=31,
        variant_rows=134,
        other_release_rows=0,
        pagination_extend_now=None,
        pagination_mechanism="hidden_api_get_comics_detected_no_extend",
        discovery_row_count_log=[
            {"phase": "before_text_view", "li_issue_rows": 165},
            {"phase": "after_scroll_to_bottom_1", "li_issue_rows": 165},
        ],
    )
    cert = certify_locg_capture(
        page_date=date(2026, 6, 24),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/24",
        page_title="New Comics",
        html='<div id="comic-list-block" data-list="releases" data-date-type="week" '
        'data-date="2026-06-24"></div>',
        discovery_audit=audit,
        list_variants_found=134,
        list_variants_persisted=134,
        detail_pages_succeeded=23,
        detail_pages_attempted=31,
        dry_run=False,
        parent_detail_seconds=[1.0],
    )
    assert not cert.passed
    assert any("proof-run" in r for r in cert.failure_reasons)
