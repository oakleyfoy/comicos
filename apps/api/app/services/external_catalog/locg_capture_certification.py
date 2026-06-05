"""Internal LoCG browser capture certification (not distributor spreadsheet matching)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.services.external_catalog.locg_list_discovery import (
    EXPECTED_MINIMUM_ISSUE_COUNT,
    PROOF_RUN_TYPICAL_WEEK_LI_ROWS,
    ListDiscoveryAudit,
)
from app.services.external_catalog.locg_spreadsheet_certification import (
    extract_list_row_titles,
    extract_parent_issue_titles,
)

# Shop/distributor exports (e.g. 6-10-26.xlsx) are external validation only — not LoCG PASS/FAIL.
EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE = (
    "Files such as 6-10-26.xlsx are external distributor/shop validation, "
    "not LoCG source-of-truth for capture certification."
)

MAX_AVG_PARENT_DETAIL_SECONDS = 5.0

_PAGINATION_NO_EXTEND_MECHANISMS = frozenset(
    {
        "hidden_api_get_comics_detected_no_extend",
        "initial_dom_only",
    }
)


# Initial DOM often ~165 when list is truncated; full weeks grow on scroll or start higher.
PROOF_RUN_INCOMPLETE_INITIAL_DOM_MAX = 200
PROOF_RUN_INCOMPLETE_MIN_SCROLL_GROWTH = 150
PROOF_RUN_LIGHT_WEEK_MIN_PARENT_ROWS = 70
PROOF_RUN_NEIGHBOR_REFERENCE_LI_ROWS = 450


def _discovery_timeline_counts(discovery_audit: ListDiscoveryAudit) -> list[int]:
    counts: list[int] = []
    for entry in discovery_audit.discovery_row_count_log or []:
        if "li_issue_rows" in entry:
            counts.append(int(entry["li_issue_rows"]))
    return counts


def _scroll_stabilized(discovery_audit: ListDiscoveryAudit, counts: list[int]) -> bool:
    if discovery_audit.scroll_row_count_stabilized:
        return True
    scroll_only = [
        int(e["li_issue_rows"])
        for e in (discovery_audit.discovery_row_count_log or [])
        if str(e.get("phase", "")).startswith("after_scroll")
    ]
    if len(scroll_only) >= 2 and scroll_only[-1] == scroll_only[-2]:
        return True
    if len(scroll_only) >= 1 and counts:
        initial = counts[0]
        if initial > PROOF_RUN_INCOMPLETE_INITIAL_DOM_MAX and all(c == initial for c in counts):
            return True
    if len(counts) >= 2 and counts[-1] == counts[-2]:
        return True
    return False


def evaluate_proof_run_completeness(
    discovery_audit: ListDiscoveryAudit,
    *,
    list_variants_found: int,
    list_variants_persisted: int,
    detail_pages_succeeded: int,
    detail_pages_attempted: int,
    variant_skipped_reason_counts: dict[str, int] | None,
) -> tuple[str | None, dict[str, Any], list[str]]:
    """
    Proof-run pass/fail from discovery + persistence signals (not a fixed 400-row floor).

    Returns (failure_reason, assessment_dict, extra_warnings).
    """
    warnings: list[str] = []
    skip = variant_skipped_reason_counts or {}
    n = discovery_audit.total_li_issue_rows
    parents_dom = discovery_audit.parent_issue_rows
    parents = discovery_audit.final_parent_issue_queue_count or parents_dom
    variants_dom = discovery_audit.variant_rows
    variants_expected = discovery_audit.final_variant_queue_count or variants_dom
    counts = _discovery_timeline_counts(discovery_audit)
    initial_dom = counts[0] if counts else n
    peak = max(counts) if counts else n
    scroll_growth = peak - initial_dom
    stabilized = _scroll_stabilized(discovery_audit, counts)
    truncated_initial = initial_dom <= PROOF_RUN_INCOMPLETE_INITIAL_DOM_MAX
    scroll_recovered = scroll_growth >= PROOF_RUN_INCOMPLETE_MIN_SCROLL_GROWTH
    high_initial_flat = (
        initial_dom > PROOF_RUN_INCOMPLETE_INITIAL_DOM_MAX
        and peak == n
        and scroll_growth == 0
    )
    lighter_week = (
        n < PROOF_RUN_TYPICAL_WEEK_LI_ROWS
        and not truncated_initial
        and (stabilized or high_initial_flat)
        and parents_dom >= PROOF_RUN_LIGHT_WEEK_MIN_PARENT_ROWS
    )
    variants_ok = (
        list_variants_found == variants_expected
        and list_variants_persisted == list_variants_found
        and int(skip.get("skipped_missing_parent") or 0) == 0
        and int(skip.get("variant_upsert_failure") or 0) == 0
    )
    parents_detail_ok = (
        detail_pages_attempted == parents
        and detail_pages_succeeded == parents
        and detail_pages_succeeded == detail_pages_attempted
    )
    parent_queue_coverage_passed = parents_detail_ok
    variant_queue_coverage_passed = variants_ok
    assessment: dict[str, Any] = {
        "total_li_issue_rows": n,
        "parent_issue_rows": parents_dom,
        "variant_rows": variants_dom,
        "parent_issue_queue_count": parents,
        "variant_queue_count": variants_expected,
        "duplicate_parent_li_rows": discovery_audit.duplicate_parent_li_rows,
        "duplicate_variant_li_rows": discovery_audit.duplicate_variant_li_rows,
        "parent_queue_coverage_passed": parent_queue_coverage_passed,
        "variant_queue_coverage_passed": variant_queue_coverage_passed,
        "typical_week_li_reference": PROOF_RUN_TYPICAL_WEEK_LI_ROWS,
        "neighbor_reference_li_rows": PROOF_RUN_NEIGHBOR_REFERENCE_LI_ROWS,
        "initial_dom_li_rows": initial_dom,
        "peak_li_rows": peak,
        "scroll_row_growth": scroll_growth,
        "scroll_stabilized": stabilized,
        "truncated_initial_dom_pattern": truncated_initial,
        "scroll_recovered_from_truncation": scroll_recovered,
        "high_initial_dom_no_scroll_growth": high_initial_flat,
        "legitimately_lighter_release_week": lighter_week,
        "variants_fully_persisted": variants_ok,
        "parent_details_complete": parents_detail_ok,
        "list_variants_found": list_variants_found,
        "list_variants_persisted": list_variants_persisted,
    }

    if truncated_initial and not scroll_recovered:
        return (
            "proof-run list incomplete: initial DOM "
            f"{initial_dom} rows with insufficient scroll growth (+{scroll_growth}, "
            f"need +{PROOF_RUN_INCOMPLETE_MIN_SCROLL_GROWTH}); likely truncated first chunk only",
            assessment,
            warnings,
        )
    if n < 100:
        return (
            f"proof-run list too small: {n} li.issue rows",
            assessment,
            warnings,
        )
    if parents_dom < PROOF_RUN_LIGHT_WEEK_MIN_PARENT_ROWS:
        return (
            f"proof-run parent_issue_rows={parents_dom} below minimum "
            f"{PROOF_RUN_LIGHT_WEEK_MIN_PARENT_ROWS}",
            assessment,
            warnings,
        )
    if not stabilized and not high_initial_flat and n < PROOF_RUN_TYPICAL_WEEK_LI_ROWS:
        return (
            "proof-run discovery did not stabilize row count during scroll",
            assessment,
            warnings,
        )
    if not variants_ok:
        return (
            "proof-run variant coverage incomplete: "
            f"found={list_variants_found} persisted={list_variants_persisted} "
            f"expected_queue={variants_expected} dom_variant_rows={variants_dom}",
            assessment,
            warnings,
        )
    if not parents_detail_ok:
        return (
            "proof-run parent detail coverage incomplete: "
            f"succeeded={detail_pages_succeeded} attempted={detail_pages_attempted} "
            f"expected_queue={parents} dom_parent_rows={parents_dom}",
            assessment,
            warnings,
        )
    if discovery_audit.duplicate_parent_li_rows > 0 or discovery_audit.duplicate_variant_li_rows > 0:
        warnings.append(
            "duplicate DOM li rows (not missing coverage): "
            f"parent_dup={discovery_audit.duplicate_parent_li_rows} "
            f"variant_dup={discovery_audit.duplicate_variant_li_rows}; "
            f"queue parents={parents} variants={variants_expected}"
        )
    if lighter_week:
        warnings.append(
            f"lighter release week: {n} li rows / {parents_dom} parents "
            f"(vs ~{PROOF_RUN_NEIGHBOR_REFERENCE_LI_ROWS} li typical); "
            "scroll stabilized, variants persisted"
        )
    elif n < PROOF_RUN_TYPICAL_WEEK_LI_ROWS:
        warnings.append(
            f"row count {n} below typical {PROOF_RUN_TYPICAL_WEEK_LI_ROWS} but passed completeness signals"
        )
    return None, assessment, warnings


def _pagination_more_data_still_available(
    *,
    extend_now: str | None,
    discovery_audit: ListDiscoveryAudit,
) -> tuple[bool, str | None]:
    """True when certification should fail because more list pages appear available."""
    normalized = (extend_now or "").strip() or None
    if normalized == "1":
        return True, "extend_now is '1' at end (more pages indicated)"
    if normalized == "0":
        return False, None
    mechanism = discovery_audit.pagination_mechanism or ""
    if discovery_audit.total_li_issue_rows > 0 and discovery_audit.parent_issue_rows > 0:
        if mechanism in _PAGINATION_NO_EXTEND_MECHANISMS or "no_extend" in mechanism:
            return False, None
        if discovery_audit.pagination_extend_calls == 0:
            return False, None
    return False, None


@dataclass
class LocgCaptureCertificationResult:
    passed: bool = False
    page_date: str = ""
    failure_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    url_date_checks: dict[str, Any] = field(default_factory=dict)
    completeness: dict[str, Any] = field(default_factory=dict)
    persistence: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    external_validation_note: str = EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "page_date": self.page_date,
            "failure_reasons": self.failure_reasons,
            "warnings": self.warnings,
            "url_date_checks": self.url_date_checks,
            "completeness": self.completeness,
            "persistence": self.persistence,
            "runtime": self.runtime,
            "external_validation_note": self.external_validation_note,
        }


def _block_attrs_from_html(html: str) -> dict[str, str]:
    block_m = re.search(r'id="comic-list-block"[^>]*>', html, re.IGNORECASE)
    if not block_m:
        return {}
    tag = block_m.group(0)
    out: dict[str, str] = {}
    for name in (
        "data-list",
        "data-date-type",
        "data-date",
        "data-date-end",
        "data-view",
        "data-extend-now",
        "data-list-offset",
    ):
        m = re.search(rf'{name}="([^"]*)"', tag, re.IGNORECASE)
        if m:
            out[name] = m.group(1)
    return out


def _variant_titles(html: str, *, limit: int = 50) -> list[str]:
    titles: list[str] = []
    for block in re.finditer(
        r"<li[^>]*\bissue\b[^>]*\bdata-parent=\"(?!0\")[^>]*>.*?</li>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        sort_m = re.search(r'data-sorting="([^"]*)"', block.group(0), re.IGNORECASE)
        if sort_m:
            t = sort_m.group(1).strip()
            if t:
                titles.append(t)
        if len(titles) >= limit:
            break
    if len(titles) < limit:
        parents = set(extract_parent_issue_titles(html))
        for t in extract_list_row_titles(html):
            if t not in parents and t not in titles:
                titles.append(t)
            if len(titles) >= limit:
                break
    return titles[:limit]


def build_live_page_state(
    *,
    page_date: date,
    final_url: str,
    page_title: str,
    html: str,
    discovery_audit: ListDiscoveryAudit,
) -> dict[str, Any]:
    block = _block_attrs_from_html(html)
    return {
        "target_date": page_date.isoformat(),
        "final_url": final_url,
        "page_title": page_title,
        "comic_list_block": block,
        "discovery_audit_summary": {
            "total_li_issue_rows": discovery_audit.total_li_issue_rows,
            "parent_issue_rows": discovery_audit.parent_issue_rows,
            "variant_rows": discovery_audit.variant_rows,
            "other_release_rows": discovery_audit.other_release_rows,
            "pagination": discovery_audit.to_report_dict().get("pagination"),
        },
    }


def build_source_universe_report(html: str) -> dict[str, Any]:
    return {
        "first_50_parent_titles": extract_parent_issue_titles(html)[:50],
        "first_50_variant_titles": _variant_titles(html, limit=50),
        "external_validation_note": EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE,
    }


def certify_locg_capture(
    *,
    page_date: date,
    final_url: str,
    page_title: str,
    html: str,
    discovery_audit: ListDiscoveryAudit,
    list_variants_found: int,
    list_variants_persisted: int,
    detail_pages_succeeded: int,
    detail_pages_attempted: int,
    dry_run: bool,
    variant_persist_skipped_reason: str | None = None,
    variant_skipped_reason_counts: dict[str, int] | None = None,
    parent_detail_seconds: list[float] | None = None,
    total_runtime_seconds: float | None = None,
    cloudflare_wait_count: int | None = None,
    cloudflare_total_wait_seconds: float | None = None,
    proof_run: bool = True,
) -> LocgCaptureCertificationResult:
    result = LocgCaptureCertificationResult(page_date=page_date.isoformat())
    iso = page_date.isoformat()
    y, m, d = page_date.year, page_date.month, page_date.day
    path_segment = f"/{y}/{m:02d}/{d:02d}"
    block = _block_attrs_from_html(html)

    result.url_date_checks = {
        "final_url": final_url,
        "url_contains_date_path": path_segment in (final_url or ""),
        "data_date": block.get("data-date"),
        "data_list": block.get("data-list"),
        "data_date_type": block.get("data-date-type"),
        "expected_date": iso,
        "expected_list": "releases",
        "expected_date_type": "week",
    }
    dom_date_ok = (
        block.get("data-date") == iso
        and block.get("data-list") == "releases"
        and block.get("data-date-type") == "week"
    )
    if path_segment not in (final_url or ""):
        if dom_date_ok:
            result.url_date_checks["url_path_warning"] = (
                f"final URL missing date path {path_segment}; DOM date attrs OK"
            )
        else:
            result.failure_reasons.append(f"final URL missing date path {path_segment}")
    if block.get("data-date") != iso:
        result.failure_reasons.append(
            f"#comic-list-block data-date={block.get('data-date')!r} expected {iso}"
        )
    if block.get("data-list") != "releases":
        result.failure_reasons.append(
            f"data-list={block.get('data-list')!r} expected releases"
        )
    if block.get("data-date-type") != "week":
        result.failure_reasons.append(
            f"data-date-type={block.get('data-date-type')!r} expected week"
        )

    extend_now_audit = discovery_audit.pagination_extend_now
    extend_now_block = block.get("data-extend-now")
    extend_now = extend_now_audit if extend_now_audit is not None else extend_now_block
    reconciled = (
        discovery_audit.parent_issue_rows
        + discovery_audit.variant_rows
        + discovery_audit.other_release_rows
    )
    result.completeness = {
        "extend_now": extend_now,
        "pagination_mechanism": discovery_audit.pagination_mechanism,
        "pagination_extend_calls": discovery_audit.pagination_extend_calls,
        "total_li_issue_rows": discovery_audit.total_li_issue_rows,
        "parent_issue_rows": discovery_audit.parent_issue_rows,
        "variant_rows": discovery_audit.variant_rows,
        "other_release_rows": discovery_audit.other_release_rows,
        "total_release_rows_reconciled": reconciled,
        "final_parent_issue_queue_count": discovery_audit.final_parent_issue_queue_count,
        "final_variant_queue_count": discovery_audit.final_variant_queue_count,
        "duplicate_parent_li_rows": discovery_audit.duplicate_parent_li_rows,
        "duplicate_variant_li_rows": discovery_audit.duplicate_variant_li_rows,
        "extend_now_audit": extend_now_audit,
        "extend_now_block": extend_now_block,
    }
    incomplete, incomplete_reason = _pagination_more_data_still_available(
        extend_now=extend_now,
        discovery_audit=discovery_audit,
    )
    if incomplete and incomplete_reason:
        result.failure_reasons.append(incomplete_reason)
    elif extend_now is None:
        result.warnings.append(
            "extend_now missing/null; no extend-now=1 signal (see proof_run_assessment)"
        )
    elif extend_now != "0":
        result.warnings.append(f"extend_now={extend_now!r} (non-fatal; not '1')")
    if discovery_audit.parent_issue_rows < 1:
        result.failure_reasons.append("parent_issue_rows is 0")
    if reconciled != discovery_audit.total_li_issue_rows:
        result.failure_reasons.append(
            f"reconciliation failed: {reconciled} != total_li_issue_rows "
            f"{discovery_audit.total_li_issue_rows}"
        )
    if discovery_audit.total_li_issue_rows < 1:
        result.failure_reasons.append("total_li_issue_rows is 0")

    skip_counts = dict(variant_skipped_reason_counts or {})
    if proof_run and not dry_run:
        proof_fail, proof_assessment, proof_warnings = evaluate_proof_run_completeness(
            discovery_audit,
            list_variants_found=list_variants_found,
            list_variants_persisted=list_variants_persisted,
            detail_pages_succeeded=detail_pages_succeeded,
            detail_pages_attempted=detail_pages_attempted,
            variant_skipped_reason_counts=skip_counts,
        )
        result.completeness["proof_run_assessment"] = proof_assessment
        result.completeness["proof_run_typical_week_li_rows"] = PROOF_RUN_TYPICAL_WEEK_LI_ROWS
        result.warnings.extend(proof_warnings)
        if proof_fail:
            result.failure_reasons.append(proof_fail)
    result.completeness["discovery_row_count_log"] = discovery_audit.discovery_row_count_log
    result.persistence = {
        "dry_run": dry_run,
        "detail_pages_attempted": detail_pages_attempted,
        "detail_pages_succeeded": detail_pages_succeeded,
        "list_variants_found": list_variants_found,
        "list_variants_persisted": list_variants_persisted,
        "variant_persist_skipped_reason": variant_persist_skipped_reason,
        "variant_skipped_reason_counts": skip_counts,
    }
    if not dry_run:
        if detail_pages_succeeded < 1:
            result.failure_reasons.append("no parent detail pages persisted (succeeded=0)")
        if list_variants_found < 1:
            result.failure_reasons.append("list_variants_found is 0")
        elif list_variants_persisted < 1:
            result.failure_reasons.append("list_variants_persisted is 0")
        elif list_variants_persisted != list_variants_found:
            explained = sum(
                v
                for k, v in skip_counts.items()
                if k.startswith("skipped_") or k == "upsert_errors"
            )
            if explained + list_variants_persisted < list_variants_found:
                result.failure_reasons.append(
                    f"list_variants_found={list_variants_found} != "
                    f"list_variants_persisted={list_variants_persisted} "
                    f"(skipped={explained}, counts={skip_counts})"
                )
        variant_failures = int(skip_counts.get("variant_upsert_failure") or 0)
        if variant_failures > 0:
            result.failure_reasons.append(
                f"variant_upsert_failure={variant_failures}"
            )
        missing_parent = int(skip_counts.get("skipped_missing_parent") or 0)
        if missing_parent > 0:
            samples = skip_counts.get("skipped_missing_parent_samples") or []
            result.failure_reasons.append(
                f"skipped_missing_parent={missing_parent} "
                f"(samples={len(samples)}); ensure variant-only parents get list stubs"
            )
            if samples:
                result.warnings.append(
                    f"skipped_missing_parent sample: {samples[0]!r}"
                )

    times = [t for t in (parent_detail_seconds or []) if t > 0]
    avg_detail = sum(times) / len(times) if times else 0.0
    result.runtime = {
        "parent_detail_timing_count": len(times),
        "average_parent_detail_seconds": round(avg_detail, 3),
        "max_allowed_average_parent_detail_seconds": MAX_AVG_PARENT_DETAIL_SECONDS,
        "total_runtime_seconds": total_runtime_seconds,
        "cloudflare_wait_count": cloudflare_wait_count,
        "cloudflare_total_wait_seconds": cloudflare_total_wait_seconds,
    }
    if times and avg_detail > MAX_AVG_PARENT_DETAIL_SECONDS:
        result.failure_reasons.append(
            f"average parent detail time {avg_detail:.2f}s > {MAX_AVG_PARENT_DETAIL_SECONDS}s"
        )

    result.passed = len(result.failure_reasons) == 0
    return result


def save_capture_certification_artifacts(
    *,
    report_dir: Path,
    cert: LocgCaptureCertificationResult,
    live_page_state: dict[str, Any],
    source_universe: dict[str, Any],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "locg_capture_certification.json").write_text(
        json.dumps(cert.to_dict(), indent=2), encoding="utf-8"
    )
    (report_dir / "live_page_state_report.json").write_text(
        json.dumps(live_page_state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (report_dir / "source_universe_report.json").write_text(
        json.dumps(source_universe, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def print_capture_certification_summary(cert: LocgCaptureCertificationResult) -> None:
    comp = cert.completeness
    pers = cert.persistence
    pra = comp.get("proof_run_assessment") or {}
    parent_q = (
        comp.get("final_parent_issue_queue_count")
        or pra.get("parent_issue_queue_count")
        or pers.get("detail_pages_attempted")
    )
    variant_q = (
        comp.get("final_variant_queue_count")
        or pra.get("variant_queue_count")
        or pers.get("list_variants_found")
    )
    print("\n--- LoCG internal capture certification ---", flush=True)
    print(f"Page date: {cert.page_date}", flush=True)
    print(f"PASS: {cert.passed}", flush=True)
    print(EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE, flush=True)
    if cert.failure_reasons:
        print("Failure reasons:", flush=True)
        for reason in cert.failure_reasons:
            print(f"  - {reason}", flush=True)
    if cert.warnings:
        print("Warnings:", flush=True)
        for warning in cert.warnings:
            print(f"  - {warning}", flush=True)
    print(
        f"Queue coverage: parents {pers.get('detail_pages_succeeded')}/{parent_q} "
        f"variants {pers.get('list_variants_persisted')}/{variant_q}",
        flush=True,
    )
    print(
        f"List DOM rows: total_li={comp.get('total_li_issue_rows')} "
        f"dup_parent={comp.get('duplicate_parent_li_rows') or pra.get('duplicate_parent_li_rows') or 0} "
        f"dup_variant={comp.get('duplicate_variant_li_rows') or pra.get('duplicate_variant_li_rows') or 0}",
        flush=True,
    )
    print(f"Runtime: {cert.runtime}", flush=True)
    print(f"Cert artifact: data/locg_browser_capture/{cert.page_date}/locg_capture_certification.json", flush=True)
