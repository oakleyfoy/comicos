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
from app.models.catalog_master import CatalogIssue, CatalogUpc  # noqa: E402
from app.services.catalog_issue_link_service import resolve_catalog_issue_link  # noqa: E402
from app.services.gcd_barcode_import_service import GCD_SOURCE  # noqa: E402
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
) -> tuple[dict[str, Any], list[str], list[dict]]:
    t0 = time.perf_counter()
    report_summary, report_failures = _confirm_report_counts(
        {"written_rows": written, "updated_issues": expected_updated, "inserted_upcs": expected_upcs},
        rollback,
    )
    timings["confirm_report_counts"] = time.perf_counter() - t0

    pilot_ids = sorted({int(r["catalog_issue_id"]) for r in written if r.get("catalog_issue_id")})

    t0 = time.perf_counter()
    issues_found = 0
    for iid in pilot_ids:
        if session.get(CatalogIssue, iid) is not None:
            issues_found += 1
    timings["db_issue_existence"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    pilot_gcd_upc_count = _count_gcd_upcs_for_issue_ids(session, pilot_ids)
    timings["db_gcd_upc_count_for_updated_issues"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sample = _barcode_sample(written, sample_size)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0

    db_failures = list(report_failures)
    if issues_found != expected_updated:
        db_failures.append(f"issues_found_in_db {issues_found} != updated_issues {expected_updated}")
    if pilot_gcd_upc_count != expected_upcs:
        db_failures.append(f"pilot_gcd_upc_count {pilot_gcd_upc_count} != inserted_upcs {expected_upcs}")

    checks = {
        "mode": "fast",
        "report_counts_ok": report_summary["report_counts_ok"],
        "issues_found_in_db": issues_found,
        "pilot_gcd_upc_count": pilot_gcd_upc_count,
        "db_ok": not db_failures,
        "barcode_sample_size": len(sample),
    }
    return checks, db_failures, barcode_tests


def run_full_audit(
    session: Session,
    report: dict[str, Any],
    rollback: dict[str, Any],
    sample_size: int,
    timings: dict[str, float],
) -> tuple[dict[str, Any], list[str], list[dict]]:
    t0 = time.perf_counter()
    report_summary, report_failures = _confirm_report_counts(report, rollback)
    timings["confirm_report_counts"] = time.perf_counter() - t0

    written = report.get("written_rows") or []
    expected_updated = int(report.get("updated_issues", len(written)))
    expected_upcs = int(report.get("inserted_upcs", 0))

    t0 = time.perf_counter()
    missing_issues: list[int] = []
    bad_upcs: list[int] = []
    for row in written:
        iid = int(row.get("catalog_issue_id") or 0)
        if session.get(CatalogIssue, iid) is None:
            missing_issues.append(iid)
        if row.get("inserted_upc") and row.get("barcode"):
            from app.services.catalog_ingestion_service import normalize_upc

            norm = normalize_upc(str(row["barcode"]))
            upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == norm)).first()
            if upc is None or int(upc.issue_id or 0) != iid:
                bad_upcs.append(iid)
    timings["per_row_db_scan"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sample = _barcode_sample(written, sample_size)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0

    db_failures = list(report_failures)
    if missing_issues:
        db_failures.append(f"missing catalog_issue ids: {missing_issues[:10]}")
    if bad_upcs:
        db_failures.append(f"upc mismatch issue ids: {bad_upcs[:10]}")

    checks = {
        "mode": "full",
        "report_counts_ok": report_summary["report_counts_ok"],
        "db_issues_missing": missing_issues,
        "db_upc_mismatch": bad_upcs,
        "db_ok": not missing_issues and not bad_upcs and not report_failures,
        "barcode_sample_size": len(sample),
        "updated_issues_report": expected_updated,
        "inserted_upcs_report": expected_upcs,
    }
    return checks, db_failures, barcode_tests


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
            checks, db_failures, barcode_tests = run_fast_audit(
                session,
                written,
                rollback,
                expected_updated,
                expected_upcs,
                args.sample_size,
                timings,
            )
        else:
            checks, db_failures, barcode_tests = run_full_audit(
                session,
                report,
                rollback,
                args.sample_size,
                timings,
            )

    timings["total"] = time.perf_counter() - t_main

    barcode_pass = all(t["pass"] for t in barcode_tests)
    overall_pass = (
        checks.get("report_counts_ok", False)
        and checks.get("db_ok", False)
        and barcode_pass
        and len(errors) <= 25
    )

    audit = {
        "report_source": str(args.report) if args.job_id is None else f"job:{args.job_id}",
        "summary": "PASS" if overall_pass else "FAIL",
        "mode": checks.get("mode", "full"),
        "checks": {
            **checks,
            "error_count": len(errors),
            "barcode_lookup_pass": barcode_pass,
            "rollback_id": payload.get("rollback_id") or payload.get("job_id"),
        },
        "timings_seconds": {k: round(v, 3) for k, v in timings.items()},
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
    for k in ("updated_issues_report", "inserted_upcs_report", "issues_found_in_db", "pilot_gcd_upc_count"):
        if k in checks:
            print(f"  {k}: {checks[k]}")
    print(f"  barcode tests: {sum(1 for t in barcode_tests if t['pass'])}/{len(barcode_tests)} pass")
    print(f"  report_counts_ok: {checks.get('report_counts_ok')}")
    print("-" * 72)
    print("Timings (seconds):")
    for stage, secs in audit["timings_seconds"].items():
        if stage != "total":
            print(f"  {stage}: {secs}")
    print(f"  total: {audit['timings_seconds'].get('total', 0)}")
    print("=" * 72)
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    print(f"Full audit: {out}")
    print("=" * 72)
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
