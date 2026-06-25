"""Post-write audit for P102 GCD write batches."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models.catalog_master import CatalogIssue, CatalogUpc  # noqa: E402
from app.models.catalog_p97 import CatalogImportJob  # noqa: E402
from app.services.catalog_issue_link_service import resolve_catalog_issue_link  # noqa: E402
from app.services.gcd_barcode_import_service import GCD_SOURCE  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import load_job_dashboard_dict  # noqa: E402
from app.services.recognition.catalog_matcher import load_catalog_issue_identity  # noqa: E402

DEFAULT_REPORT = Path("data/p102/gcd_large_write_batch_report.json")
OUT = Path("data/p102/gcd_large_write_batch_audit.json")


def _load_report(path: Path, job_id: int | None) -> dict:
    if job_id is not None:
        with Session(get_engine()) as session:
            job = session.get(CatalogImportJob, job_id)
            if job is None:
                raise SystemExit(f"Job {job_id} not found")
            return load_job_dashboard_dict(session, job_id)
    if not path.exists():
        raise SystemExit(f"Report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _gcd_id_for_issue(issue: CatalogIssue) -> int | None:
    bucket = (issue.external_source_ids or {}).get(GCD_SOURCE) or {}
    if not isinstance(bucket, dict):
        return None
    for key in bucket:
        if str(key).isdigit():
            return int(key)
    return None


def _extract_report_fields(payload: dict) -> tuple[dict, list[dict], int, int, int, int, list]:
    report = payload.get("report") or payload
    written = report.get("written_rows") or []
    expected_issues = int(report.get("inserted_issues", payload.get("inserted_issues", len(written))))
    expected_upcs = int(report.get("inserted_upcs", payload.get("inserted_upcs", 0)))
    skipped_existing = int(report.get("skipped_existing", 0))
    skipped_conflicts = int(report.get("skipped_conflicts", 0))
    errors = report.get("errors") or []
    return report, written, expected_issues, expected_upcs, skipped_existing, skipped_conflicts, errors


def _barcode_sample(written: list[dict], sample_size: int) -> list[dict]:
    barcode_pool = [r for r in written if r.get("inserted_upc") and r.get("barcode")]
    n = min(sample_size, len(barcode_pool))
    if n < len(barcode_pool):
        return random.sample(barcode_pool, n)
    return barcode_pool


def _run_barcode_sample_tests(session: Session, sample: list[dict]) -> list[dict]:
    barcode_tests: list[dict] = []
    for wr in sample:
        bc = str(wr["barcode"])
        expected_id = int(wr["catalog_issue_id"])
        link = resolve_catalog_issue_link(session, barcode=bc)
        ok = link.catalog_issue_id == expected_id and link.method == "upc"
        barcode_tests.append(
            {
                "barcode": bc,
                "expected_catalog_issue_id": expected_id,
                "lookup_issue_id": link.catalog_issue_id,
                "lookup_method": link.method,
                "pass": ok,
            }
        )
    return barcode_tests


def _confirm_report_counts(
    written: list[dict],
    expected_issues: int,
    expected_upcs: int,
) -> tuple[dict[str, Any], list[str]]:
    """Validate report JSON internal consistency (no DB)."""
    failures: list[str] = []
    written_with_id = [r for r in written if r.get("catalog_issue_id")]
    upc_rows_in_report = sum(1 for r in written if r.get("inserted_upc"))
    unique_issue_ids = {int(r["catalog_issue_id"]) for r in written_with_id}

    if len(written) != expected_issues:
        failures.append(f"written_rows length {len(written)} != inserted_issues {expected_issues}")
    if len(unique_issue_ids) != expected_issues:
        failures.append(
            f"unique catalog_issue_id in written_rows {len(unique_issue_ids)} != inserted_issues {expected_issues}",
        )
    if upc_rows_in_report != expected_upcs:
        failures.append(f"inserted_upc flags in written_rows {upc_rows_in_report} != inserted_upcs {expected_upcs}")

    summary = {
        "written_rows_count": len(written),
        "unique_issue_ids_in_report": len(unique_issue_ids),
        "inserted_upc_flags_in_report": upc_rows_in_report,
        "inserted_issues_report": expected_issues,
        "inserted_upcs_report": expected_upcs,
        "report_counts_ok": not failures,
    }
    return summary, failures


def _count_gcd_upcs_for_issue_ids(session: Session, issue_ids: list[int]) -> int:
    if not issue_ids:
        return 0
    count = session.exec(
        select(func.count())
        .select_from(CatalogUpc)
        .where(CatalogUpc.issue_id.in_(issue_ids))
        .where(CatalogUpc.source == GCD_SOURCE),
    ).one()
    if isinstance(count, tuple):
        count = count[0]
    return int(count)


def _duplicates_within_inserted_ids(session: Session, issue_ids: list[int]) -> tuple[list[str], int]:
    """Duplicate (series_id, normalized_issue_number) groups among inserted ids only."""
    if not issue_ids:
        return [], 0
    rows = session.exec(
        select(
            CatalogIssue.id,
            CatalogIssue.series_id,
            CatalogIssue.normalized_issue_number,
            CatalogIssue.issue_number,
        ).where(CatalogIssue.id.in_(issue_ids)),
    ).all()
    by_key: defaultdict[tuple[int, str], list[int]] = defaultdict(list)
    for row in rows:
        by_key[(int(row.series_id), str(row.normalized_issue_number))].append(int(row.id))

    dup_fail: list[str] = []
    for key, ids in by_key.items():
        if len(ids) <= 1:
            continue
        sample_id = ids[0]
        identity = load_catalog_issue_identity(session, sample_id)
        series_label = identity.series if identity else f"series_id={key[0]}"
        dup_fail.append(f"duplicate within batch: {series_label} #{key[1]} ids={ids}")

    missing = len(issue_ids) - len(rows)
    if missing:
        dup_fail.append(f"missing catalog_issue rows for {missing} ids from report")
    return dup_fail, len(rows)


def run_fast_audit(
    session: Session,
    written: list[dict],
    expected_issues: int,
    expected_upcs: int,
    barcode_samples: int,
    timings: dict[str, float],
) -> tuple[dict, list[str], list[str], list[dict]]:
    t0 = time.perf_counter()
    report_summary, report_failures = _confirm_report_counts(written, expected_issues, expected_upcs)
    timings["confirm_report_counts"] = time.perf_counter() - t0

    pilot_ids = sorted({int(r["catalog_issue_id"]) for r in written if r.get("catalog_issue_id")})

    t0 = time.perf_counter()
    pilot_gcd_upc_count = _count_gcd_upcs_for_issue_ids(session, pilot_ids)
    timings["db_gcd_upc_count_for_inserted_issues"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    dup_fail, issues_found = _duplicates_within_inserted_ids(session, pilot_ids)
    timings["duplicate_check_within_batch"] = time.perf_counter() - t0
    report_summary["issues_found_in_db"] = issues_found

    t0 = time.perf_counter()
    sample = _barcode_sample(written, barcode_samples)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0
    report_summary["barcode_sample_size"] = len(sample)

    db_checks_fail = list(report_failures)
    if pilot_gcd_upc_count != expected_upcs:
        db_checks_fail.append(f"pilot_gcd_upc_count {pilot_gcd_upc_count} != inserted_upcs {expected_upcs}")

    checks_extra = {
        "mode": "fast",
        "report_counts_ok": report_summary["report_counts_ok"],
        "pilot_gcd_upc_count": pilot_gcd_upc_count,
        "issues_found_in_db": issues_found,
        "db_issue_rows_ok": report_summary["report_counts_ok"] and issues_found == expected_issues and not dup_fail,
        "upc_barcodes_resolved_in_db": pilot_gcd_upc_count == expected_upcs,
    }
    return checks_extra, dup_fail, db_checks_fail, barcode_tests


def run_full_audit(
    session: Session,
    written: list[dict],
    expected_issues: int,
    expected_upcs: int,
    barcode_samples: int,
    timings: dict[str, float],
) -> tuple[dict, list[str], list[str], list[dict]]:
    t0 = time.perf_counter()
    pilot_ids = [int(r["catalog_issue_id"]) for r in written if r.get("catalog_issue_id")]
    pilot_gcd_upc_count = _count_gcd_upcs_for_issue_ids(session, pilot_ids)
    timings["pilot_gcd_upc_count"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    barcodes_in_report = [r.get("barcode") for r in written if r.get("inserted_upc")]
    upc_rows_for_barcodes = 0
    for bc in barcodes_in_report:
        if not bc:
            continue
        if session.exec(select(CatalogUpc).where(CatalogUpc.upc == bc)).first() is not None:
            upc_rows_for_barcodes += 1
    timings["scan_all_report_barcodes"] = time.perf_counter() - t0

    dup_fail: list[str] = []
    db_checks_fail: list[str] = []

    t0 = time.perf_counter()
    for wr in written:
        iid = int(wr["catalog_issue_id"])
        issue = session.get(CatalogIssue, iid)
        if issue is None:
            db_checks_fail.append(f"missing catalog_issue_id={iid}")
            continue
        gcd_id = _gcd_id_for_issue(issue)
        exp_gcd = int(wr["gcd_issue_id"])
        if gcd_id != exp_gcd:
            db_checks_fail.append(f"issue {iid} gcd_id {gcd_id} != expected {exp_gcd}")

        dup_count = session.exec(
            select(func.count())
            .select_from(CatalogIssue)
            .where(CatalogIssue.series_id == issue.series_id)
            .where(CatalogIssue.normalized_issue_number == issue.normalized_issue_number),
        ).one()
        if isinstance(dup_count, tuple):
            dup_count = dup_count[0]
        if int(dup_count) > 1:
            identity = load_catalog_issue_identity(session, iid)
            dup_fail.append(
                f"duplicate: {identity.series if identity else '?'} #{issue.issue_number} count={dup_count}",
            )
    timings["per_row_issue_and_catalog_dup_scan"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sample = _barcode_sample(written, barcode_samples)
    barcode_tests = _run_barcode_sample_tests(session, sample)
    timings["barcode_sample_tests"] = time.perf_counter() - t0

    checks_extra = {
        "mode": "full",
        "pilot_gcd_upc_count": int(pilot_gcd_upc_count),
        "upc_barcodes_resolved_in_db": upc_rows_for_barcodes,
        "db_issue_rows_ok": len(written) == expected_issues and not db_checks_fail,
    }
    return checks_extra, dup_fail, db_checks_fail, barcode_tests


def main() -> int:
    parser = argparse.ArgumentParser(description="P102 write-batch post audit")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--barcode-samples", type=int, default=25)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Scoped audit: report counts, UPC count on inserted issue ids only, batch-local duplicates, barcode samples",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    timings: dict[str, float] = {}
    t_main = time.perf_counter()
    t_load = time.perf_counter()
    payload = _load_report(Path(args.report), args.job_id)
    timings["load_report"] = time.perf_counter() - t_load

    report, written, expected_issues, expected_upcs, skipped_existing, skipped_conflicts, errors = _extract_report_fields(
        payload,
    )
    max_errors = 25

    with Session(get_engine()) as session:
        if args.fast:
            checks_extra, dup_fail, db_checks_fail, barcode_tests = run_fast_audit(
                session,
                written,
                expected_issues,
                expected_upcs,
                args.barcode_samples,
                timings,
            )
        else:
            checks_extra, dup_fail, db_checks_fail, barcode_tests = run_full_audit(
                session,
                written,
                expected_issues,
                expected_upcs,
                args.barcode_samples,
                timings,
            )

    timings["total"] = time.perf_counter() - t_main

    checks = {
        "inserted_issues": expected_issues,
        "inserted_upcs_report": expected_upcs,
        "skipped_existing": skipped_existing,
        "skipped_conflicts": skipped_conflicts,
        "error_count": len(errors),
        "written_rows_count": len(written),
        "no_series_issue_duplicates": len(dup_fail) == 0,
        "barcode_lookup_pass": all(t["pass"] for t in barcode_tests),
        "errors_within_limit": len(errors) <= max_errors,
        "job_id": payload.get("job_id"),
        "rollback_id": payload.get("rollback_id"),
        **checks_extra,
    }

    if args.fast:
        overall_pass = (
            checks.get("report_counts_ok", False)
            and checks.get("db_issue_rows_ok", False)
            and checks.get("pilot_gcd_upc_count") == expected_upcs
            and checks["no_series_issue_duplicates"]
            and checks["barcode_lookup_pass"]
            and checks["errors_within_limit"]
            and not report.get("stopped_early")
        )
    else:
        overall_pass = (
            checks.get("db_issue_rows_ok", False)
            and checks.get("pilot_gcd_upc_count") == expected_upcs
            and checks.get("upc_barcodes_resolved_in_db") == expected_upcs
            and checks["no_series_issue_duplicates"]
            and checks["barcode_lookup_pass"]
            and checks["errors_within_limit"]
            and not report.get("stopped_early")
        )

    audit = {
        "report_source": str(args.report) if args.job_id is None else f"job:{args.job_id}",
        "summary": "PASS" if overall_pass else "FAIL",
        "mode": checks_extra.get("mode", "full"),
        "checks": checks,
        "timings_seconds": {k: round(v, 3) for k, v in timings.items()},
        "duplicate_failures": dup_fail[:50],
        "db_failures": db_checks_fail[:50],
        "barcode_lookup_sample": barcode_tests,
        "errors_sample": errors[:30],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(audit, indent=2))
        return 0 if overall_pass else 1

    print("=" * 72)
    print(f"P102 GCD WRITE-BATCH AUDIT ({audit['mode'].upper()})")
    print("=" * 72)
    for k in (
        "inserted_issues",
        "inserted_upcs_report",
        "skipped_existing",
        "skipped_conflicts",
        "error_count",
        "pilot_gcd_upc_count",
    ):
        if k in checks:
            print(f"  {k}: {checks[k]}")
    if args.fast:
        print(f"  report_counts_ok: {checks.get('report_counts_ok')}")
        print(f"  issues_found_in_db: {checks.get('issues_found_in_db')}")
    print(f"  barcode tests: {sum(1 for t in barcode_tests if t['pass'])}/{len(barcode_tests)} pass")
    print(f"  duplicates: {len(dup_fail)}")
    print(f"  rollback_id: {checks.get('rollback_id')}")
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
