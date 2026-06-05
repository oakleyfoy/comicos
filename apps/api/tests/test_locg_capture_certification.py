from __future__ import annotations

from datetime import date

from app.services.external_catalog.locg_capture_certification import (
    EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE,
    certify_locg_capture,
)
from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit


def _minimal_html() -> str:
    parents = []
    variants = []
    for i in range(3):
        parents.append(
            f'<li class="issue" data-comic="{i}" data-parent="0">'
            f'<div class="title" data-sorting="Parent Series #{i}">'
            f"<a>Parent Series #{i}</a></div></li>"
        )
        variants.append(
            f'<li class="issue variant" data-comic="{i}00" data-parent="{i}">'
            f'<div class="title" data-sorting="Parent Series #{i} Variant A">'
            f"<a>Variant</a></div></li>"
        )
    block = (
        '<div id="comic-list-block" data-list="releases" data-date-type="week" '
        'data-date="2026-06-10" data-extend-now="0"></div>'
    )
    return block + "<ul>" + "".join(parents + variants) + "</ul>"


def test_internal_cert_passes_minimal_capture() -> None:
    html = _minimal_html()
    audit = ListDiscoveryAudit(
        total_li_issue_rows=6,
        parent_issue_rows=3,
        variant_rows=3,
        other_release_rows=0,
        pagination_extend_now="0",
        pagination_extend_calls=2,
        pagination_mechanism="hidden_api_get_comics_pagination_view_text",
    )
    cert = certify_locg_capture(
        page_date=date(2026, 6, 10),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10",
        page_title="New Comics",
        html=html,
        discovery_audit=audit,
        list_variants_found=3,
        list_variants_persisted=3,
        detail_pages_succeeded=3,
        detail_pages_attempted=3,
        dry_run=False,
        parent_detail_seconds=[1.0, 1.2, 0.8],
        proof_run=False,
    )
    assert cert.passed
    assert EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE in cert.external_validation_note


def test_internal_cert_fails_wrong_date() -> None:
    html = _minimal_html().replace("2026-06-10", "2026-06-03")
    audit = ListDiscoveryAudit(
        total_li_issue_rows=6,
        parent_issue_rows=3,
        variant_rows=3,
        other_release_rows=0,
        pagination_extend_now="0",
    )
    cert = certify_locg_capture(
        page_date=date(2026, 6, 10),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10",
        page_title="New Comics",
        html=html,
        discovery_audit=audit,
        list_variants_found=3,
        list_variants_persisted=3,
        detail_pages_succeeded=1,
        detail_pages_attempted=1,
        dry_run=False,
        parent_detail_seconds=[1.0],
        proof_run=False,
    )
    assert not cert.passed
    assert any("data-date" in r for r in cert.failure_reasons)


def test_extend_now_none_no_extend_mechanism_passes_with_warning() -> None:
    html = _minimal_html().replace('data-extend-now="0"', "")
    audit = ListDiscoveryAudit(
        total_li_issue_rows=504,
        parent_issue_rows=75,
        variant_rows=429,
        other_release_rows=0,
        final_parent_issue_queue_count=45,
        final_variant_queue_count=291,
        pagination_extend_now=None,
        pagination_extend_calls=0,
        pagination_mechanism="hidden_api_get_comics_detected_no_extend",
    )
    cert = certify_locg_capture(
        page_date=date(2026, 6, 10),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10",
        page_title="New Comics",
        html=html,
        discovery_audit=audit,
        list_variants_found=291,
        list_variants_persisted=291,
        detail_pages_succeeded=45,
        detail_pages_attempted=45,
        dry_run=False,
        parent_detail_seconds=[4.0] * 45,
        variant_skipped_reason_counts={"variant_upsert_failure": 0},
    )
    assert cert.passed
    assert not cert.failure_reasons
    assert any("extend_now" in w for w in cert.warnings)


def test_extend_now_one_fails() -> None:
    html = _minimal_html()
    audit = ListDiscoveryAudit(
        total_li_issue_rows=6,
        parent_issue_rows=3,
        variant_rows=3,
        other_release_rows=0,
        pagination_extend_now="1",
        pagination_mechanism="hidden_api_get_comics_pagination_view_text",
    )
    cert = certify_locg_capture(
        page_date=date(2026, 6, 10),
        final_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10",
        page_title="New Comics",
        html=html,
        discovery_audit=audit,
        list_variants_found=3,
        list_variants_persisted=3,
        detail_pages_succeeded=3,
        detail_pages_attempted=3,
        dry_run=False,
        parent_detail_seconds=[1.0],
        proof_run=False,
    )
    assert not cert.passed
    assert any("extend_now" in r for r in cert.failure_reasons)
