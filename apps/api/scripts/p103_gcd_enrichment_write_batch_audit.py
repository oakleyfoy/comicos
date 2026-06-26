"""Post-write audit for P103 enrichment pilot batches."""
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
    DB_ISSUE_EXISTENCE_TARGET_SECONDS,
    build_overall_assertion_failures,
    duplicate_barcodes_in_job_inserts,
    fetch_existing_catalog_issue_ids,
    resolve_job_upc_audit_fields,
)
from app.services.p103_gcd_enrichment_dashboard_service import load_p103_enrichment_job  # noqa: E402
from gcd_pipeline_cli import (  # noqa: E402
    add_audit_mode_arguments,
    add_output_argument,
    add_report_source_arguments,
    resolve_output_path,
)

DEFAULT_REPORT = Path("data/p103/gcd_enrichment_write_batch.json")
DEFAULT_OUT = Path("data/p103/gcd_enrichment_write_batch_audit.json")


def _load_payload(report_path: Path, job_id: int | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if job_id is not None:
        with Session(get_engine()) as session:
            payload = load_p103_enrichment_job(session, job_id)
        report = dict(payload.get("report") or {})
        rollback = dict(payload.get("rollback") or {})
        return payload, report, rollback
    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    report = dict(raw.get("report") or raw)
    rollback = dict(raw.get("rollback") or {})
    return raw, report, rollback


def _confirm_report_counts(report: dict[str, Any], rollback: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    written = report.get("written_rows") or []
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


def _count_gcd_upcs_for_issue_ids(session: Session, issue_ids: list[int]) -> int:
    if not issue_ids:
        return 0
    count = session.exec(
        select(func.count())
        .select_from(CatalogUpc)
        .where(CatalogUpc.issue_id.in_(issue_ids))
        .where(CatalogUpc.source == GCD_SOURCE)
    ).one()
    if isinstance(count, tuple):
        count = count[0]
    return int(count)


def run_fast_audit(
    session: Session,
    written: list[dict],
    rollback: dict[str, Any],
    expected_updated: int,
    expected_upcs: int,
    sample_size: int,
    timings: dict[str, float],
) -> tuple[dict[str, Any], list[str], list[str], list[dict]]:
    t0 = time.perf_counter()
    report_summary, report_failures = _confirm_report_counts(
        {"written_rows": written, "updated_issues": expected_updated, "inserted_upcs": expected_upcs},
        rollback,
    )
    timings["confirm_report_counts"] = time.perf_counter() - t0

    pilot_ids = sorted({int(r["catalog_issue_id"]) for r in written if r.get("catalog_issue_id")})

    t0 = time.perf_counter()
    existing_ids = fetch_existing_catalog_issue_ids(session, pilot_ids)
    issues_found = len(existing_ids)
    timings["db_issue_existence"] = time.perf_counter() - t0
    timings["db_issue_existence_batches"] = (len(pilot_ids) + 499) // 500 if pilot_ids else 0

    t0 = time.perf_counter()
    existing_or_present_gcd_upc_count = _count_gcd_upcs_for_issue_ids(session, pilot_ids)
    timings["db_gcd_upc_count_for_updated_issues"] = time.perf_counter() - t0

    upc_audit = resolve_job_upc_audit_fields(
        {"written_rows": written, "inserted_upcs": expected_upcs},
        rollback,
    )
    duplicate_upc_barcodes = duplicate_barcodes_in_job_inserts(written)

    t0 = time.perf_counter()
    sample = _barcode_sample(written, sample_size)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0

    db_failures = list(report_failures)
    if issues_found != expected_updated:
        db_failures.append(f"issues_found_in_db {issues_found} != updated_issues {expected_updated}")
    if upc_audit["tracks_job_upc_inserts"] and upc_audit["job_inserted_upc_count"] != expected_upcs:
        db_failures.append(
            f"job_inserted_upc_count {upc_audit['job_inserted_upc_count']} != expected_inserted_upcs {expected_upcs}"
        )
    if duplicate_upc_barcodes:
        db_failures.append(f"duplicate job UPC barcodes: {duplicate_upc_barcodes[:10]}")

    job_count = upc_audit["job_inserted_upc_count"]
    checks = {
        "mode": "fast",
        "report_counts_ok": report_summary["report_counts_ok"],
        "issues_found_in_db": issues_found,
        "existing_or_present_gcd_upc_count": existing_or_present_gcd_upc_count,
        "job_inserted_upc_count": job_count,
        "expected_inserted_upcs": expected_upcs,
        "tracks_job_upc_inserts": upc_audit["tracks_job_upc_inserts"],
        "duplicate_job_upc_barcodes": duplicate_upc_barcodes,
        "db_ok": not db_failures,
        "barcode_sample_size": len(sample),
        "stage_row_counts": {
            "written_rows": len(written),
            "distinct_catalog_issue_ids": len(pilot_ids),
            "issues_found_in_db": issues_found,
            "expected_updated_issues": expected_updated,
            "existing_or_present_gcd_upc_count": existing_or_present_gcd_upc_count,
            "job_inserted_upc_count": job_count,
            "expected_inserted_upcs": expected_upcs,
            "duplicate_job_upc_barcodes": len(duplicate_upc_barcodes),
            "barcode_sample_size": len(sample),
            "barcode_sample_passed": sum(1 for t in barcode_tests if t.get("pass")),
        },
    }
    return checks, db_failures, report_failures, barcode_tests


def run_full_audit(
    session: Session,
    report: dict[str, Any],
    rollback: dict[str, Any],
    sample_size: int,
    timings: dict[str, float],
) -> tuple[dict[str, Any], list[str], list[str], list[dict]]:
    t0 = time.perf_counter()
    report_summary, report_failures = _confirm_report_counts(report, rollback)
    timings["confirm_report_counts"] = time.perf_counter() - t0

    written = report.get("written_rows") or []
    expected_updated = int(report.get("updated_issues", len(written)))
    expected_upcs = int(report.get("inserted_upcs", 0))

    issue_ids = sorted({int(row.get("catalog_issue_id") or 0) for row in written if row.get("catalog_issue_id")})
    t0 = time.perf_counter()
    existing_ids = fetch_existing_catalog_issue_ids(session, issue_ids)
    missing_issues = sorted(iid for iid in issue_ids if iid not in existing_ids)
    timings["db_issue_existence"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    bad_upcs: list[int] = []
    for row in written:
        iid = int(row.get("catalog_issue_id") or 0)
        if row.get("inserted_upc") and row.get("barcode"):
            from app.services.catalog_ingestion_service import normalize_upc

            norm = normalize_upc(str(row["barcode"]))
            upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == norm)).first()
            if upc is None or int(upc.issue_id or 0) != iid:
                bad_upcs.append(iid)
    timings["per_row_upc_verify"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sample = _barcode_sample(written, sample_size)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0

    upc_audit = resolve_job_upc_audit_fields(report, rollback)
    duplicate_upc_barcodes = duplicate_barcodes_in_job_inserts(written)
    existing_or_present_gcd_upc_count = _count_gcd_upcs_for_issue_ids(session, issue_ids)

    db_failures = list(report_failures)
    if missing_issues:
        db_failures.append(f"missing catalog_issue ids: {missing_issues[:10]}")
    if bad_upcs:
        db_failures.append(f"upc mismatch issue ids: {bad_upcs[:10]}")
    if upc_audit["tracks_job_upc_inserts"] and upc_audit["job_inserted_upc_count"] != expected_upcs:
        db_failures.append(
            f"job_inserted_upc_count {upc_audit['job_inserted_upc_count']} != expected_inserted_upcs {expected_upcs}"
        )
    if duplicate_upc_barcodes:
        db_failures.append(f"duplicate job UPC barcodes: {duplicate_upc_barcodes[:10]}")

    job_count = upc_audit["job_inserted_upc_count"]
    checks = {
        "mode": "full",
        "report_counts_ok": report_summary["report_counts_ok"],
        "issues_found_in_db": len(existing_ids),
        "existing_or_present_gcd_upc_count": existing_or_present_gcd_upc_count,
        "job_inserted_upc_count": job_count,
        "expected_inserted_upcs": expected_upcs,
        "tracks_job_upc_inserts": upc_audit["tracks_job_upc_inserts"],
        "duplicate_job_upc_barcodes": duplicate_upc_barcodes,
        "db_issues_missing": missing_issues,
        "db_upc_mismatch": bad_upcs,
        "db_ok": not db_failures,
        "barcode_sample_size": len(sample),
        "updated_issues_report": expected_updated,
        "inserted_upcs_report": expected_upcs,
        "stage_row_counts": {
            "written_rows": len(written),
            "distinct_catalog_issue_ids": len(issue_ids),
            "issues_found_in_db": len(existing_ids),
            "missing_catalog_issue_ids": len(missing_issues),
            "upc_mismatch_issue_ids": len(bad_upcs),
            "expected_updated_issues": expected_updated,
            "existing_or_present_gcd_upc_count": existing_or_present_gcd_upc_count,
            "job_inserted_upc_count": job_count,
            "expected_inserted_upcs": expected_upcs,
            "duplicate_job_upc_barcodes": len(duplicate_upc_barcodes),
            "barcode_sample_size": len(sample),
            "barcode_sample_passed": sum(1 for t in barcode_tests if t.get("pass")),
        },
    }
    return checks, db_failures, report_failures, barcode_tests


def main() -> int:
    parser = argparse.ArgumentParser(description="P103 enrichment write-batch post audit")
    add_report_source_arguments(parser, default_report=str(DEFAULT_REPORT))
    add_output_argument(parser, default=str(DEFAULT_OUT))
    add_audit_mode_arguments(parser, default_sample_size=50)
    args = parser.parse_args()

    timings: dict[str, float] = {}
    t_main = time.perf_counter()
    t_load = time.perf_counter()
    payload, report, rollback = _load_payload(Path(args.report), args.job_id)
    timings["load_report"] = time.perf_counter() - t_load

    written = report.get("written_rows") or []
    expected_updated = int(report.get("updated_issues", len(written)))
    expected_upcs = int(report.get("inserted_upcs", 0))
    errors = report.get("errors") or []

    with Session(get_engine()) as session:
        if args.fast:
            checks, db_failures, report_failures, barcode_tests = run_fast_audit(
                session,
                written,
                rollback,
                expected_updated,
                expected_upcs,
                args.sample_size,
                timings,
            )
        else:
            checks, db_failures, report_failures, barcode_tests = run_full_audit(
                session,
                report,
                rollback,
                args.sample_size,
                timings,
            )

    timings["total"] = time.perf_counter() - t_main

    upc_audit = resolve_job_upc_audit_fields(report, rollback)
    duplicate_upc_barcodes = list(checks.get("duplicate_job_upc_barcodes") or duplicate_barcodes_in_job_inserts(written))
    barcode_pass = not barcode_tests or all(t["pass"] for t in barcode_tests)
    job_count = checks.get("job_inserted_upc_count")
    if job_count is None and upc_audit["job_inserted_upc_count"] is not None:
        job_count = upc_audit["job_inserted_upc_count"]
    assertion_failures = build_overall_assertion_failures(
        report_counts_ok=bool(checks.get("report_counts_ok")),
        report_failures=report_failures,
        issues_found_in_db=int(checks["issues_found_in_db"]) if checks.get("issues_found_in_db") is not None else None,
        expected_updated=expected_updated,
        expected_inserted_upcs=expected_upcs,
        job_inserted_upc_count=int(job_count) if job_count is not None else None,
        tracks_job_upc_inserts=bool(upc_audit["tracks_job_upc_inserts"]),
        barcode_pass=barcode_pass,
        barcode_tests=barcode_tests,
        error_count=len(errors),
        missing_catalog_issue_count=len(checks.get("db_issues_missing") or []),
        upc_mismatch_count=len(checks.get("db_upc_mismatch") or []),
        duplicate_job_upc_barcodes=duplicate_upc_barcodes,
    )
    overall_pass = len(assertion_failures) == 0

    audit = {
        "report_source": str(args.report) if args.job_id is None else f"job:{args.job_id}",
        "summary": "PASS" if overall_pass else "FAIL",
        "mode": checks.get("mode", "full"),
        "checks": {
            **checks,
            "error_count": len(errors),
            "barcode_lookup_pass": barcode_pass,
            "rollback_id": payload.get("rollback_id") or payload.get("job_id"),
            "updated_issues_report": expected_updated,
            "inserted_upcs_report": expected_upcs,
        },
        "assertion_failures": assertion_failures,
        "timings_seconds": {k: round(v, 3) if isinstance(v, float) else v for k, v in timings.items()},
        "db_failures": db_failures[:50],
        "barcode_lookup_sample": barcode_tests,
        "errors_sample": errors[:30],
    }

    out = resolve_output_path(args, DEFAULT_OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(audit, indent=2))
        return 0 if overall_pass else 1

    print("=" * 72)
    print(f"P103 GCD ENRICHMENT WRITE-BATCH AUDIT ({audit['mode'].upper()})")
    print("=" * 72)
    stage_counts = checks.get("stage_row_counts") or {}
    for k in (
        "updated_issues_report",
        "expected_inserted_upcs",
        "issues_found_in_db",
        "existing_or_present_gcd_upc_count",
        "job_inserted_upc_count",
    ):
        val = checks.get(k)
        if val is None and k == "updated_issues_report":
            val = expected_updated
        if val is None and k == "expected_inserted_upcs":
            val = expected_upcs
        if val is None and k == "job_inserted_upc_count":
            val = job_count
        if val is not None:
            print(f"  {k}: {val}")
    if checks.get("inserted_upcs_report") is not None and "expected_inserted_upcs" not in checks:
        print(f"  inserted_upcs_report: {checks['inserted_upcs_report']}")
    print(f"  barcode tests: {sum(1 for t in barcode_tests if t['pass'])}/{len(barcode_tests)} pass")
    print(f"  report_counts_ok: {checks.get('report_counts_ok')}")
    print(f"  error_count: {len(errors)} (limit 25)")
    if stage_counts:
        print("-" * 72)
        print("Stage row counts:")
        for label, count in stage_counts.items():
            print(f"  {label}: {count}")
    print("-" * 72)
    print("Timings (seconds):")
    for stage, secs in audit["timings_seconds"].items():
        if stage in ("total", "db_issue_existence_batches"):
            continue
        print(f"  {stage}: {secs}")
        if stage == "db_issue_existence" and isinstance(secs, (int, float)):
            batches = audit["timings_seconds"].get("db_issue_existence_batches")
            if batches is not None:
                print(f"    batches: {batches}")
            if secs > DB_ISSUE_EXISTENCE_TARGET_SECONDS:
                print(
                    f"    note: exceeds {DB_ISSUE_EXISTENCE_TARGET_SECONDS}s batched PK lookup target "
                    f"({secs}s)"
                )
    print(f"  total: {audit['timings_seconds'].get('total', 0)}")
    print("-" * 72)
    if assertion_failures:
        print("Failed assertions:")
        for line in assertion_failures:
            print(f"  {line}")
    else:
        print("Failed assertions: (none)")
    print("=" * 72)
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    print(f"Full audit: {out}")
    print("=" * 72)
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
