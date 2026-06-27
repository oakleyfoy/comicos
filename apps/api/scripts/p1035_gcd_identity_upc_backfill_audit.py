"""Post-write audit for P103.5 identity + UPC backfill batches."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models.catalog_master import CatalogUpc  # noqa: E402
from app.services.catalog_issue_link_service import resolve_catalog_issue_link  # noqa: E402
from app.services.gcd_barcode_import_service import GCD_SOURCE  # noqa: E402
from app.services.p103_gcd_enrichment_audit_helpers import (  # noqa: E402
    build_overall_assertion_failures,
    duplicate_barcodes_in_job_inserts,
    fetch_existing_catalog_issue_ids,
    resolve_job_upc_audit_fields,
)
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id  # noqa: E402
from app.services.p1035_gcd_identity_dashboard_service import load_p1035_identity_job  # noqa: E402
from gcd_pipeline_cli import (  # noqa: E402
    add_audit_mode_arguments,
    add_output_argument,
    add_report_source_arguments,
    resolve_output_path,
)

DEFAULT_REPORT = Path("data/p1035/gcd_identity_backfill_write.json")
DEFAULT_OUT = Path("data/p1035/gcd_identity_backfill_audit.json")


def _load_payload(report_path: Path, job_id: int | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if job_id is not None:
        with Session(get_engine()) as session:
            payload = load_p1035_identity_job(session, job_id)
        report = dict(payload.get("report") or {})
        rollback = dict(payload.get("rollback") or {})
        return payload, report, rollback
    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    report = dict(raw.get("report") or raw)
    rollback = dict(raw.get("rollback") or {})
    return raw, report, rollback


def _effective_written_rows(report: dict[str, Any], rollback: dict[str, Any]) -> list[dict[str, Any]]:
    written = list(report.get("written_rows") or [])
    if written:
        return written
    expected_updated = int(report.get("updated_issues", 0))
    snapshots = rollback.get("issue_snapshots") or []
    if expected_updated > 0 and len(snapshots) == expected_updated:
        return [
            {"catalog_issue_id": int(s["catalog_issue_id"])}
            for s in snapshots
            if s.get("catalog_issue_id") is not None
        ]
    return written


def _confirm_report_counts(report: dict[str, Any], rollback: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    written = _effective_written_rows(report, rollback)
    failures: list[str] = []
    expected_updated = int(report.get("updated_issues", len(written)))
    expected_upcs = int(report.get("inserted_upcs", 0))
    upc_flags = sum(1 for r in written if r.get("inserted_upc"))
    if len(written) != expected_updated:
        failures.append(f"written_rows {len(written)} != updated_issues {expected_updated}")
    if upc_flags != expected_upcs:
        failures.append(f"inserted_upc flags {upc_flags} != inserted_upcs {expected_upcs}")
    snapshots = rollback.get("issue_snapshots") or []
    upc_ids = rollback.get("upc_ids") or []
    if not snapshots and expected_updated > 0:
        failures.append("rollback missing issue_snapshots")
    if upc_ids and len(upc_ids) != expected_upcs:
        failures.append(f"rollback upc_ids {len(upc_ids)} != inserted_upcs {expected_upcs}")
    summary = {
        "written_rows_count": len(written),
        "updated_issues_report": expected_updated,
        "inserted_upcs_report": expected_upcs,
        "rollback_snapshots": len(snapshots),
        "rollback_upc_ids": len(upc_ids),
        "report_counts_ok": not failures,
    }
    return summary, failures


def _barcode_sample(written: list[dict], sample_size: int) -> list[dict]:
    pool = [r for r in written if r.get("inserted_upc") and r.get("barcode")]
    n = min(sample_size, len(pool))
    if n < len(pool):
        return random.sample(pool, n)
    return pool


def _run_barcode_sample_tests(session: Session, sample: list[dict]) -> list[dict]:
    tests: list[dict] = []
    for wr in sample:
        bc = str(wr["barcode"])
        expected_id = int(wr["catalog_issue_id"])
        link = resolve_catalog_issue_link(session, barcode=bc)
        ok = link.catalog_issue_id == expected_id and link.method == "upc"
        tests.append(
            {
                "barcode": bc,
                "expected_catalog_issue_id": expected_id,
                "lookup_issue_id": link.catalog_issue_id,
                "lookup_method": link.method,
                "pass": ok,
            }
        )
    return tests


def _verify_gcd_links(session: Session, written: list[dict], sample: list[dict]) -> list[dict]:
    from app.models.catalog_master import CatalogIssue

    tests: list[dict] = []
    for wr in sample:
        iid = int(wr["catalog_issue_id"])
        expected_gcd = wr.get("gcd_issue_id")
        issue = session.get(CatalogIssue, iid)
        got = extract_gcd_issue_id(issue.external_source_ids if issue else None)
        tests.append(
            {
                "catalog_issue_id": iid,
                "expected_gcd_issue_id": expected_gcd,
                "actual_gcd_issue_id": got,
                "pass": expected_gcd is None or int(expected_gcd) == int(got or 0),
            }
        )
    return tests


def main() -> int:
    parser = argparse.ArgumentParser(description="P103.5 identity backfill post audit")
    add_report_source_arguments(parser, default_report=str(DEFAULT_REPORT))
    add_output_argument(parser, default=str(DEFAULT_OUT))
    add_audit_mode_arguments(parser, default_sample_size=50)
    args = parser.parse_args()

    timings: dict[str, float] = {}
    t_main = time.perf_counter()
    payload, report, rollback = _load_payload(Path(args.report), args.job_id)

    written = _effective_written_rows(report, rollback)
    expected_updated = int(report.get("updated_issues", len(written)))
    expected_upcs = int(report.get("inserted_upcs", 0))
    errors = report.get("errors") or []

    with Session(get_engine()) as session:
        t0 = time.perf_counter()
        report_summary, report_failures = _confirm_report_counts(report, rollback)
        timings["confirm_report_counts"] = time.perf_counter() - t0

        pilot_ids = sorted({int(r["catalog_issue_id"]) for r in written if r.get("catalog_issue_id")})
        t0 = time.perf_counter()
        existing_ids = fetch_existing_catalog_issue_ids(session, pilot_ids)
        timings["db_issue_existence"] = time.perf_counter() - t0

        sample = _barcode_sample(written, args.sample_size)
        gcd_sample = sample if sample else written[: min(args.sample_size, len(written))]
        barcode_tests = _run_barcode_sample_tests(session, sample)
        gcd_tests = _verify_gcd_links(session, written, gcd_sample)

        upc_audit = resolve_job_upc_audit_fields(report, rollback)
        duplicate_upc_barcodes = duplicate_barcodes_in_job_inserts(written)

    db_failures = list(report_failures)
    if len(existing_ids) != expected_updated:
        db_failures.append(f"issues_found_in_db {len(existing_ids)} != updated_issues {expected_updated}")

    barcode_pass = not barcode_tests or all(t["pass"] for t in barcode_tests)
    gcd_pass = not gcd_tests or all(t["pass"] for t in gcd_tests)
    assertion_failures = build_overall_assertion_failures(
        report_counts_ok=bool(report_summary["report_counts_ok"]),
        report_failures=report_failures,
        issues_found_in_db=len(existing_ids),
        expected_updated=expected_updated,
        expected_inserted_upcs=expected_upcs,
        job_inserted_upc_count=int(upc_audit["job_inserted_upc_count"] or 0),
        tracks_job_upc_inserts=bool(upc_audit["tracks_job_upc_inserts"]),
        barcode_pass=barcode_pass,
        barcode_tests=barcode_tests,
        error_count=len(errors),
        missing_catalog_issue_count=0,
        upc_mismatch_count=0,
        duplicate_job_upc_barcodes=duplicate_upc_barcodes,
    )
    if not gcd_pass:
        assertion_failures.append("gcd_issue_id link sample failed")
    overall_pass = len(assertion_failures) == 0

    audit = {
        "report_source": str(args.report) if args.job_id is None else f"job:{args.job_id}",
        "summary": "PASS" if overall_pass else "FAIL",
        "mode": "fast" if args.fast else "full",
        "checks": {
            **report_summary,
            "issues_found_in_db": len(existing_ids),
            "barcode_lookup_pass": barcode_pass,
            "gcd_link_pass": gcd_pass,
            "duplicate_job_upc_barcodes": duplicate_upc_barcodes,
        },
        "assertion_failures": assertion_failures,
        "timings_seconds": {k: round(v, 3) for k, v in timings.items()},
        "db_failures": db_failures[:50],
        "barcode_lookup_sample": barcode_tests,
        "gcd_link_sample": gcd_tests,
        "errors_sample": errors[:30],
    }
    audit["timings_seconds"]["total"] = round(time.perf_counter() - t_main, 3)

    out = resolve_output_path(args, DEFAULT_OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(audit, indent=2))
        return 0 if overall_pass else 1

    print("=" * 72)
    print(f"P103.5 IDENTITY BACKFILL AUDIT — {audit['summary']}")
    print("=" * 72)
    print(f"Full audit: {out}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
