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


def _proof_run_list_row_count_failure(discovery_audit: ListDiscoveryAudit) -> str | None:
    """Fail proof-run capture when the list is far below a typical full week (~500 li rows)."""
    n = discovery_audit.total_li_issue_rows
    if n >= PROOF_RUN_TYPICAL_WEEK_LI_ROWS:
        return None
    log_tail = ""
    if discovery_audit.discovery_row_count_log:
        final = discovery_audit.discovery_row_count_log[-1]
        log_tail = (
            f"; discovery timeline final li={final.get('li_issue_rows')} "
            f"offset={final.get('data_list_offset')!r} extend_now={final.get('data_extend_now')!r}"
        )
    if n < EXPECTED_MINIMUM_ISSUE_COUNT:
        return (
            f"proof-run list incomplete: {n} li.issue rows < minimum "
            f"{EXPECTED_MINIMUM_ISSUE_COUNT}{log_tail}"
        )
    return (
        f"proof-run list count {n} is below typical full week "
        f"(~500 li rows, threshold {PROOF_RUN_TYPICAL_WEEK_LI_ROWS}); "
        f"recert from saved HTML does not count — rerun live capture or document "
        f"legitimate smaller-week rationale in discovery_report{log_tail}"
    )


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
        if discovery_audit.total_li_issue_rows >= PROOF_RUN_TYPICAL_WEEK_LI_ROWS:
            result.warnings.append(
                "extend_now missing/null; treated as complete (rows present, no extend-now=1 signal)"
            )
        else:
            result.warnings.append(
                "extend_now missing/null with low row count; list may be incomplete (see discovery_row_count_log)"
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

    if proof_run:
        proof_fail = _proof_run_list_row_count_failure(discovery_audit)
        if proof_fail:
            result.failure_reasons.append(proof_fail)
    result.completeness["discovery_row_count_log"] = discovery_audit.discovery_row_count_log
    result.completeness["proof_run_typical_week_li_rows"] = PROOF_RUN_TYPICAL_WEEK_LI_ROWS

    skip_counts = dict(variant_skipped_reason_counts or {})
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
    print("\n--- LoCG internal capture certification ---", flush=True)
    print(f"Page date: {cert.page_date}", flush=True)
    print(f"PASS: {cert.passed}", flush=True)
    print(EXTERNAL_DISTRIBUTOR_VALIDATION_NOTE, flush=True)
    if cert.failure_reasons:
        print("Failure reasons:", flush=True)
        for reason in cert.failure_reasons:
            print(f"  - {reason}", flush=True)
    print(f"URL/date checks: {cert.url_date_checks}", flush=True)
    print(f"Completeness: {cert.completeness}", flush=True)
    print(f"Persistence: {cert.persistence}", flush=True)
    print(f"Runtime: {cert.runtime}", flush=True)
