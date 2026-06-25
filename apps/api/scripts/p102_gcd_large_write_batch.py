"""P102 large GCD write batch (catalog_import_job + rollback payload).

Usage:
  cd apps/api
  python scripts/p102_gcd_large_write_batch.py --diagnose
  python scripts/p102_gcd_large_write_batch.py \\
    --publisher DC --year-from 2009 --year-to 2026 --limit 2500 --confirm-write YES
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

print("p102_gcd_large_write_batch: script started", flush=True)


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P102 large GCD write batch (import job)")
    parser.add_argument("--diagnose", action="store_true", help="Verify DB/GCD/cache only; no writes")
    parser.add_argument("--publisher", default="DC")
    parser.add_argument("--year-from", type=int, default=2009)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--confirm-write", default=None)
    parser.add_argument("--gcd-db", default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--output", default="data/p102/gcd_large_write_batch_report.json")
    parser.add_argument("--progress-interval", type=int, default=250)
    parser.add_argument("--max-errors", type=int, default=25)
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Export catalog cache from Postgres before run (default: use existing cache)",
    )
    parser.add_argument(
        "--skip-cache-refresh",
        action="store_true",
        default=True,
        help="Default: do not refresh cache (ignored if --refresh-cache is set)",
    )
    parser.add_argument("--estimate-remaining", action="store_true")
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Emit detailed stage timing + rows/min + ETA for 10k/44k (default limit 500 if unset)",
    )
    parser.add_argument("--resume-job", type=int, default=None, help="Skip GCD ids from prior job report/rollback")
    parser.add_argument("--commit-batch-size", type=int, default=250)
    parser.add_argument("--slow-path", action="store_true", help="Use legacy per-row commit write path")
    parser.add_argument(
        "--fast-path",
        action="store_true",
        help="Use batched fast write path (default unless --slow-path)",
    )
    parser.add_argument(
        "--benchmark-dry-run",
        action="store_true",
        help="Measure GCD scan/classify/skip speed only (no Postgres writes)",
    )
    args = parser.parse_args()
    _log("args parsed")

    from p97_bootstrap import bootstrap_api_path

    bootstrap_api_path()
    _log("api path bootstrapped")

    from sqlmodel import Session, text  # noqa: E402

    from app.core.config import get_settings  # noqa: E402
    from app.db.session import get_engine  # noqa: E402
    from app.services.gcd_catalog_import_dashboard_service import (  # noqa: E402
        count_clean_candidates_for_scope,
        load_job_dashboard_dict,
        resolve_cache_path,
        resolve_gcd_path,
        run_gcd_large_write_batch_job,
    )
    from app.services.p101_catalog_cache_service import (  # noqa: E402
        DEFAULT_CACHE_PATH,
        export_catalog_cache,
    )
    from app.services.p102_gcd_modern_acquisition_write_service import WriteBatchFilters  # noqa: E402

    settings = get_settings()
    db_url_set = bool(str(settings.database_url or "").strip())
    _log(f"env DATABASE_URL present: {db_url_set} (via app settings)")
    if not db_url_set:
        _log("ERROR: DATABASE_URL / database_url not configured")
        return 2

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache or str(DEFAULT_CACHE_PATH))
    _log(f"GCD path: {gcd_path}")
    _log(f"GCD path exists: {gcd_path.exists()}")
    _log(f"Cache path: {cache_path}")
    _log(f"Cache path exists: {cache_path.exists()}")

    if args.diagnose:
        return _run_diagnose(
            gcd_path=gcd_path,
            cache_path=cache_path,
            publisher=args.publisher,
            year_from=args.year_from,
            year_to=args.year_to,
            get_engine=get_engine,
            Session=Session,
            text=text,
            count_clean_candidates_for_scope=count_clean_candidates_for_scope,
        )

    if args.slow_path and args.fast_path:
        _log("ERROR: use only one of --slow-path or --fast-path")
        return 2
    use_fast_path = not args.slow_path

    if args.benchmark_dry_run:
        return _run_benchmark_dry_run(
            args=args,
            gcd_path=gcd_path,
            cache_path=cache_path,
            get_engine=get_engine,
            Session=Session,
        )

    if args.limit is None or args.confirm_write is None:
        if args.benchmark and args.confirm_write == "YES":
            args.limit = 500
            _log("benchmark: default --limit 500")
        else:
            _log("ERROR: write mode requires --limit and --confirm-write YES")
            return 2
    if args.confirm_write != "YES":
        _log("Refusing: --confirm-write YES required")
        return 2

    if not gcd_path.exists():
        _log(f"ERROR: GCD DB missing: {gcd_path}")
        return 2
    if not cache_path.exists():
        _log(f"ERROR: Catalog cache missing: {cache_path} (run dryrun --refresh-cache once)")
        return 2

    if args.refresh_cache:
        _log("refresh-cache requested: exporting catalog cache from Postgres...")
        with Session(get_engine()) as session:
            n = export_catalog_cache(session, cache_path)
        _log(f"cache export complete: {n} issues")
    else:
        _log("skip-cache-refresh: using existing cache SQLite (default)")

    filters = WriteBatchFilters(
        publisher=args.publisher,
        year_from=args.year_from,
        year_to=args.year_to,
        limit=args.limit,
    )

    _log("connecting to Postgres...")
    t0 = time.perf_counter()
    with Session(get_engine()) as session:
        _log("Postgres session open; starting import job + write batch...")
        job = run_gcd_large_write_batch_job(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            confirm_write=args.confirm_write,
            progress_interval=args.progress_interval,
            max_errors=args.max_errors,
            commit_batch_size=args.commit_batch_size,
            benchmark=args.benchmark,
            resume_job_id=args.resume_job,
            use_fast_path=use_fast_path,
        )
        job_id = int(job.id or 0)
        _log(f"serializing job report for job_id={job_id} (in-session)...")
        t_ser = time.perf_counter()
        payload = load_job_dashboard_dict(session, job_id)
        serialize_sec = time.perf_counter() - t_ser
    elapsed = round(time.perf_counter() - t0, 1)
    payload["elapsed_seconds"] = elapsed
    report = payload.get("report") or {}
    perf = report.get("perf") or {}
    if perf:
        perf["job_serialize_sec"] = round(serialize_sec, 3)
        report["perf"] = perf
        payload["report"] = report

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = payload.get("report") or {}
    _log("=" * 72)
    _log("P102 LARGE GCD WRITE BATCH")
    _log(f"Job ID / Rollback ID: {payload.get('job_id')}")
    _log(f"Status: {payload.get('status')}")
    _log(f"Elapsed: {elapsed}s")
    _log(f"Inserted issues: {report.get('inserted_issues', payload.get('inserted_issues'))}")
    _log(f"Inserted UPCs: {report.get('inserted_upcs', payload.get('inserted_upcs'))}")
    _log(f"Skipped existing: {report.get('skipped_existing')}")
    _log(f"Skipped conflicts: {report.get('skipped_conflicts')}")
    _log(f"Errors: {len(report.get('errors') or [])}")
    if report.get("stopped_early"):
        _log(f"Stopped early: {report.get('stop_reason')}")
    perf = report.get("perf")
    if args.benchmark and perf:
        _log("--- BENCHMARK ---")
        _log(f"rows/min: {perf.get('rows_per_min')}")
        _log(f"preload_sec: {perf.get('preload_sec')}")
        _log(f"gcd_scan_classify_sec: {perf.get('gcd_scan_classify_sec')}")
        _log(f"skip_checks_sec: {perf.get('skip_checks_sec')}")
        _log(f"publisher_series_sec: {perf.get('publisher_series_sec')}")
        _log(f"issue_insert_sec: {perf.get('issue_insert_sec')}")
        _log(f"variant_insert_sec: {perf.get('variant_insert_sec')}")
        _log(f"upc_insert_sec: {perf.get('upc_insert_sec')}")
        _log(f"commit_sec: {perf.get('commit_sec')} (commits={perf.get('commits')})")
        _log(f"job_serialize_sec: {perf.get('job_serialize_sec')}")
        _log(f"estimated_sec_10k: {perf.get('estimated_sec_10k')}")
        _log(f"estimated_sec_44k: {perf.get('estimated_sec_44k')}")
    _log(f"Report: {out}")
    _log("=" * 72)

    if args.estimate_remaining:
        _log("counting remaining clean candidates (uses current cache)...")
        remaining = count_clean_candidates_for_scope(
            gcd_path=gcd_path,
            cache_path=cache_path,
            publisher=args.publisher,
            year_from=args.year_from,
            year_to=args.year_to,
        )
        next_limit = min(remaining, 10_000)
        _log("")
        _log("Overnight command (DO NOT RUN until approved):")
        _log(
            f"  python scripts/p102_gcd_large_write_batch.py --publisher {args.publisher} "
            f"--year-from {args.year_from} --year-to {args.year_to} --limit {next_limit} "
            f"--confirm-write YES"
        )
        _log(f"  Remaining clean_primary_candidate (cache snapshot): {remaining}")

    return 0 if payload.get("status") == "completed" else 1


def _run_benchmark_dry_run(*, args, gcd_path: Path, cache_path: Path, get_engine, Session) -> int:
    from app.services.p102_gcd_modern_acquisition_write_service import WriteBatchFilters  # noqa: E402
    from app.services.p102_gcd_write_batch_fast import (  # noqa: E402
        enrich_report_with_perf,
        run_p102_gcd_scan_benchmark_dry_run,
    )

    if not gcd_path.exists():
        _log(f"ERROR: GCD DB missing: {gcd_path}")
        return 2
    if not cache_path.exists():
        _log(f"ERROR: Catalog cache missing: {cache_path}")
        return 2
    limit = args.limit if args.limit is not None else 500
    filters = WriteBatchFilters(
        publisher=args.publisher,
        year_from=args.year_from,
        year_to=args.year_to,
        limit=limit,
    )
    gcd_skip: set[int] = set()
    if args.refresh_cache:
        from app.services.p101_catalog_cache_service import export_catalog_cache  # noqa: E402

        _log("refresh-cache: exporting catalog cache...")
        with Session(get_engine()) as session:
            export_catalog_cache(session, cache_path)
    with Session(get_engine()) as session:
        from app.services.p102_gcd_write_batch_fast import preload_write_guards  # noqa: E402
        from app.services.p102_gcd_modern_acquisition_write_service import FOCUS_PUBLISHER_NAMES  # noqa: E402

        pub_display = FOCUS_PUBLISHER_NAMES.get(filters.publisher, filters.publisher)
        guards = preload_write_guards(
            session,
            focus_publisher=filters.publisher,
            pub_display=pub_display,
            stage_log=_log,
        )
        gcd_skip = guards.gcd_imported
    _log(f"benchmark-dry-run: limit={limit} publisher={args.publisher} years={args.year_from}-{args.year_to}")
    t0 = time.perf_counter()
    report, timer = run_p102_gcd_scan_benchmark_dry_run(
        gcd_path=gcd_path,
        cache_path=cache_path,
        filters=filters,
        gcd_imported=gcd_skip,
    )
    elapsed = time.perf_counter() - t0
    payload = enrich_report_with_perf(report, timer, elapsed)
    payload["mode"] = "benchmark_dry_run"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    perf = payload.get("perf") or {}
    _log("=" * 72)
    _log("P102 BENCHMARK DRY RUN (no writes)")
    _log(f"Elapsed: {round(elapsed, 1)}s")
    _log(f"Would insert (clean_primary): issues={report.inserted_issues} upcs={report.inserted_upcs}")
    _log(f"gcd_rows_scanned: {perf.get('gcd_rows_scanned')}")
    _log(f"preload_sec: {perf.get('preload_sec')}")
    _log(f"gcd_scan_classify_sec: {perf.get('gcd_scan_classify_sec')}")
    _log(f"skip_checks_sec: {perf.get('skip_checks_sec')}")
    _log(f"rows_per_min (selection): {perf.get('rows_per_min')}")
    _log(f"estimated_sec_10k: {perf.get('estimated_sec_10k')}")
    _log(f"estimated_sec_44k: {perf.get('estimated_sec_44k')}")
    _log(f"Report: {out}")
    _log("=" * 72)
    return 0


def _run_diagnose(
    *,
    gcd_path: Path,
    cache_path: Path,
    publisher: str,
    year_from: int,
    year_to: int,
    get_engine,
    Session,
    text,
    count_clean_candidates_for_scope,
) -> int:
    _log("=== DIAGNOSE MODE (no writes) ===")
    t0 = time.perf_counter()

    _log("connecting to Postgres...")
    try:
        with Session(get_engine()) as session:
            one = session.exec(text("SELECT 1")).one()
            _log(f"Postgres OK: SELECT 1 -> {one}")
    except Exception as exc:
        _log(f"Postgres FAILED: {exc}")
        return 1

    if not gcd_path.exists():
        _log(f"GCD SQLite MISSING: {gcd_path}")
        return 1
    _log("opening GCD SQLite...")
    try:
        conn = sqlite3.connect(gcd_path, timeout=30)
        conn.execute("PRAGMA query_only = ON")
        gcd_issues = conn.execute("SELECT COUNT(*) FROM gcd_issue").fetchone()[0]
        _log(f"GCD SQLite OK: gcd_issue rows = {gcd_issues:,}")
        conn.close()
    except Exception as exc:
        _log(f"GCD SQLite FAILED: {exc}")
        return 1

    if not cache_path.exists():
        _log(f"Cache SQLite MISSING: {cache_path}")
        return 1
    _log("opening catalog cache SQLite...")
    try:
        conn = sqlite3.connect(cache_path, timeout=30)
        n_issues = conn.execute("SELECT COUNT(*) FROM catalog_issue_cache").fetchone()[0]
        n_upc = conn.execute("SELECT COUNT(*) FROM catalog_upc_cache").fetchone()[0]
        _log(f"Cache SQLite OK: catalog_issue_cache={n_issues:,} catalog_upc_cache={n_upc:,}")
        conn.close()
    except Exception as exc:
        _log(f"Cache SQLite FAILED: {exc}")
        return 1

    _log(f"counting clean_primary_candidate for {publisher} {year_from}-{year_to}...")
    try:
        clean = count_clean_candidates_for_scope(
            gcd_path=gcd_path,
            cache_path=cache_path,
            publisher=publisher,
            year_from=year_from,
            year_to=year_to,
        )
        _log(f"Clean candidates: {clean:,}")
    except Exception as exc:
        _log(f"Clean count FAILED: {exc}")
        return 1

    elapsed = round(time.perf_counter() - t0, 1)
    _log(f"=== DIAGNOSE OK ({elapsed}s) ===")
    if elapsed > 60:
        _log("WARN: diagnose exceeded 60s target")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
