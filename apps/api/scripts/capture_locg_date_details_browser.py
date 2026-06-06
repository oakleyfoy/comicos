"""Playwright browser capture: LoCG release date list + per-issue detail pages."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

SYNC_BROWSER = "BROWSER"


@dataclass
class PilotSummary:
    date: str
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    db_issues: int = 0
    db_variants: int = 0
    skipped_missing_parent: int = 0
    variant_upsert_failures: int = 0
    elapsed_seconds: float = 0.0
    raw_path: str = ""
    list_page_loaded: bool = False
    list_issues_found: int = 0
    list_variants_found: int = 0
    list_variants_persisted: int = 0
    detail_pages_attempted: int = 0
    detail_pages_succeeded: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    variants_created: int = 0
    creators_created: int = 0
    characters_created: int = 0
    with_pull_count: int = 0
    with_want_count: int = 0
    with_foc_date: int = 0
    with_upc: int = 0
    with_distributor_sku: int = 0
    with_cover_image: int = 0
    errors_count: int = 0
    error_sample: list[str] = field(default_factory=list)
    top_10_by_pull_count: list[dict[str, object]] = field(default_factory=list)
    top_10_by_variant_count: list[dict[str, object]] = field(default_factory=list)
    missing_from_lunar_count: int = 0
    sync_run_id: int | None = None
    status: str = "FAILED"
    dry_run: bool = False
    crosswalk_skipped: bool = True
    crosswalk_seconds: float | None = None
    performance_audit: dict[str, object] = field(default_factory=dict)
    max_issues_cap: int | None = None


def resolve_run_crosswalk(*, run_crosswalk: bool, skip_crosswalk: bool) -> bool:
    """Crosswalk is off by default; only --run-crosswalk enables it."""
    if run_crosswalk and skip_crosswalk:
        raise ValueError("cannot use both --run-crosswalk and --skip-crosswalk")
    return run_crosswalk


def _pilot_summary_for_stdout(summary: PilotSummary) -> dict[str, object]:
    """Avoid dumping hundreds of per-issue timing rows on the default (concise) path."""
    data = dict(summary.__dict__)
    audit = dict(data.get("performance_audit") or {})
    audit.pop("per_issue_timings", None)
    data["performance_audit"] = audit
    return data


def _init_validation_sqlite_schema() -> None:
    from sqlmodel import SQLModel

    from app.db.session import get_engine
    from app.models.external_catalog import (  # noqa: F401
        ExternalCatalogCharacter,
        ExternalCatalogCreator,
        ExternalCatalogIssue,
        ExternalCatalogMatch,
        ExternalCatalogSource,
        ExternalCatalogSyncRun,
        ExternalCatalogVariant,
    )

    SQLModel.metadata.create_all(get_engine())


def _field_coverage(rows: list) -> dict[str, int]:
    def has_upc(row) -> bool:
        imp = row.importance_signals_json or {}
        return bool(imp.get("upc"))

    def has_sku(row) -> bool:
        imp = row.importance_signals_json or {}
        return bool(imp.get("distributor_sku"))

    return {
        "with_pull_count": sum(1 for r in rows if r.pull_count is not None),
        "with_want_count": sum(1 for r in rows if r.want_count is not None),
        "with_foc_date": sum(1 for r in rows if r.foc_date is not None),
        "with_upc": sum(1 for r in rows if has_upc(r)),
        "with_distributor_sku": sum(1 for r in rows if has_sku(r)),
        "with_cover_image": sum(1 for r in rows if r.cover_image_url),
    }


def _safe_close_session(session) -> None:
    if session is None:
        return
    try:
        session.close()
    except Exception as exc:  # noqa: BLE001
        print(f"warning: session close: {exc}", file=sys.stderr, flush=True)


def _prepare_final_summary_fields(
    summary: PilotSummary,
    *,
    page_date: date,
    session,
    run,
    browser_counters,
    run_crosswalk: bool,
    raw_dir: Path | None,
    run_started: float,
) -> None:
    from app.services.external_catalog.locg_capture_runner import (
        default_raw_path,
        merge_run_warnings,
        skipped_missing_parent_count,
        variant_upsert_failure_count,
    )
    from app.services.external_catalog.sync_service import count_locg_release_date_persistence

    summary.elapsed_seconds = time.perf_counter() - run_started
    summary.crosswalk_skipped = not run_crosswalk
    if raw_dir is not None:
        summary.raw_path = str(raw_dir)
    elif not summary.raw_path:
        summary.raw_path = default_raw_path(summary.date)
    if browser_counters is not None:
        vsk = browser_counters.variant_skipped_reason_counts
        summary.skipped_missing_parent = skipped_missing_parent_count(vsk)
        summary.variant_upsert_failures = variant_upsert_failure_count(vsk)
        for warning in browser_counters.post_capture_warnings:
            if warning not in summary.warnings:
                summary.warnings.append(warning)
    merge_run_warnings(run, summary.warnings)
    if session is not None:
        try:
            counts = count_locg_release_date_persistence(session, release_date=page_date)
            summary.db_issues = counts["issues"]
            summary.db_variants = counts["variants"]
        except Exception as exc:  # noqa: BLE001
            summary.failures.append(f"db count: {exc}")
    for err in summary.error_sample:
        if err in summary.warnings:
            continue
        if err not in summary.failures:
            summary.failures.append(err)


def _finalize_exit_code(
    summary: PilotSummary,
    *,
    max_issues: int | None,
    hard_failure: bool,
) -> int:
    from app.services.external_catalog.locg_capture_runner import resolve_capture_exit_code

    return resolve_capture_exit_code(
        run_status=summary.status,
        list_page_loaded=summary.list_page_loaded,
        list_issues_found=summary.list_issues_found,
        detail_pages_succeeded=summary.detail_pages_succeeded,
        max_issues=max_issues,
        hard_failure=hard_failure,
    )


def _print_required_final_summary(summary: PilotSummary) -> None:
    from app.services.external_catalog.locg_capture_runner import print_final_capture_summary

    parent_queue = summary.list_issues_found
    if summary.max_issues_cap is not None:
        parent_queue = min(parent_queue, summary.max_issues_cap)
    print_final_capture_summary(
        page_date=summary.date,
        run_status=summary.status,
        parent_queue=parent_queue,
        parent_captured=summary.detail_pages_succeeded,
        db_issues=summary.db_issues,
        db_variants=summary.db_variants,
        skipped_missing_parent=summary.skipped_missing_parent,
        variant_upsert_failures=summary.variant_upsert_failures,
        warnings=summary.warnings,
        failures=summary.failures,
        elapsed_seconds=summary.elapsed_seconds,
        crosswalk_skipped=summary.crosswalk_skipped,
        raw_path=summary.raw_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--email", default="")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-issues", type=int, default=None)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
        help="Fixed throttle: sleep before/after each detail goto (default 0). Ignored when --adaptive-delay.",
    )
    parser.add_argument(
        "--adaptive-delay",
        action="store_true",
        help="Random pre-goto delay between min/max; bump +0.5s on 429/Cloudflare, -0.25s after 20 clean pages.",
    )
    parser.add_argument(
        "--min-delay-seconds",
        type=float,
        default=0.75,
        help="Adaptive delay floor (default 0.75).",
    )
    parser.add_argument(
        "--max-delay-seconds",
        type=float,
        default=1.5,
        help="Adaptive delay ceiling (default 1.5).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--verbose-variant-persist",
        action="store_true",
        help="Print each variant upsert to console (default: trace file + summary only).",
    )
    parser.add_argument(
        "--timing-table",
        action="store_true",
        help="Print full per-issue timing table and performance JSON after capture (default: concise).",
    )
    parser.add_argument("--save-raw", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument(
        "--skip-crosswalk",
        action="store_true",
        help="Skip owner-wide crosswalk rebuild after capture (default when --run-crosswalk is not set).",
    )
    parser.add_argument(
        "--run-crosswalk",
        action="store_true",
        help="Rebuild external catalog crosswalk after capture (slow; scans full LoCG catalog).",
    )
    args = parser.parse_args()
    run_started = time.perf_counter()
    hard_failure = False

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    page_date = date.fromisoformat(args.date)
    summary = PilotSummary(date=page_date.isoformat(), dry_run=args.dry_run)
    summary.max_issues_cap = args.max_issues
    session = None
    run = None
    browser_counters = None
    raw_dir: Path | None = None
    run_crosswalk = not args.skip_crosswalk and args.run_crosswalk

    def _exit_with_summary() -> int:
        _prepare_final_summary_fields(
            summary,
            page_date=page_date,
            session=session,
            run=run,
            browser_counters=browser_counters,
            run_crosswalk=run_crosswalk,
            raw_dir=raw_dir,
            run_started=run_started,
        )
        _print_required_final_summary(summary)
        _safe_close_session(session)
        return _finalize_exit_code(summary, max_issues=args.max_issues, hard_failure=hard_failure)

    if args.production and not os.environ.get("DATABASE_URL", "").strip():
        summary.failures.append("DATABASE_URL required for --production")
        summary.status = "FAILED"
        hard_failure = True
        return _exit_with_summary()
    if args.min_delay_seconds > args.max_delay_seconds:
        summary.failures.append("--min-delay-seconds must be <= --max-delay-seconds")
        summary.status = "FAILED"
        hard_failure = True
        return _exit_with_summary()
    try:
        run_crosswalk = resolve_run_crosswalk(
            run_crosswalk=args.run_crosswalk,
            skip_crosswalk=args.skip_crosswalk,
        )
        summary.crosswalk_skipped = not run_crosswalk
    except ValueError as exc:
        summary.failures.append(str(exc))
        summary.status = "FAILED"
        hard_failure = True
        return _exit_with_summary()

    headless = not args.headful
    if args.headless:
        headless = True

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not args.dry_run and not db_url:
        db_path = os.path.join(ROOT, ".locg_browser_validation.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        _init_validation_sqlite_schema()

    from app.services.external_catalog.character_extract import expand_characters_from_raw
    from app.services.external_catalog.crosswalk import MATCH_MISSING, rebuild_external_catalog_crosswalk
    from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
    from app.services.external_catalog.locg_browser import (
        LocgBrowserBlockedError,
        build_merged_issue_dict,
        parse_detail_page_html,
        run_playwright_capture,
        stub_to_detail_seed,
    )
    from app.services.external_catalog.league_of_comic_geeks import merge_detail_into_seed
    from app.services.external_catalog.locg_capture_timing import (
        CaptureTimingAudit,
        IssueCaptureTiming,
        log_issue_timing,
    )
    from app.services.external_catalog.normalization import normalize_locg_issue
    from app.services.external_catalog.locg_browser_finalize import finalize_browser_capture_sync_run
    from app.services.external_catalog.locg_capture_runner import (
        default_raw_path,
        print_final_capture_summary,
        resolve_capture_exit_code,
        skipped_missing_parent_count,
        variant_upsert_failure_count,
    )
    from app.services.external_catalog.sync_service import count_locg_release_date_persistence
    from app.services.external_catalog.sync_service import (
        SYNC_COMPLETE_WITH_WARNINGS,
        SYNC_COMPLETED,
        SYNC_FAILED,
        SYNC_PARTIAL,
        create_sync_run,
        ensure_locg_source,
        fail_sync_run,
        fail_sync_run_preserving_counters,
        should_skip_browser_resume,
        upsert_characters,
        upsert_creators,
        upsert_external_issue,
        LocgVariantPersistStats,
        upsert_locg_list_variant_rows,
        upsert_variants,
    )
    from app.services.external_catalog.sync_service import SyncCounters

    if args.save_raw:
        raw_dir = Path(ROOT).parent.parent / "data" / "locg_browser_capture" / page_date.isoformat()

    counters = SyncCounters()
    owner_user_id = 1
    captured_issue_ids: list[int] = []

    if not args.dry_run:
        from sqlmodel import Session

        from app.db.session import get_engine

        session = Session(get_engine())
        ensure_locg_source(session)
        run = create_sync_run(
            session,
            source_name=LOCG_SOURCE_NAME,
            sync_type=SYNC_BROWSER,
            start_date=page_date,
            end_date=page_date,
        )
        if args.email:
            from owner_lookup import resolve_owner_user_id

            try:
                owner_user_id = resolve_owner_user_id(session, args.email)
            except Exception as exc:  # noqa: BLE001
                summary.failures.append(f"owner lookup: {exc}")
                summary.status = SYNC_FAILED
                hard_failure = True
                if run is not None:
                    fail_sync_run_preserving_counters(
                        session, run=run, counters=counters, message=str(exc)
                    )
                return _exit_with_summary()

    def should_skip(url: str) -> bool:
        if not args.resume or session is None:
            return False
        return should_skip_browser_resume(
            session, source_url=url, refresh_existing=args.refresh_existing
        )

    timing_audit = CaptureTimingAudit()
    adaptive_controller = None
    if args.adaptive_delay:
        from app.services.external_catalog.locg_adaptive_delay import AdaptiveDelayController

        adaptive_controller = AdaptiveDelayController(
            min_delay_seconds=args.min_delay_seconds,
            max_delay_seconds=args.max_delay_seconds,
        )
        print(
            "Adaptive throttle enabled: "
            f"min={args.min_delay_seconds}s max={args.max_delay_seconds}s",
            flush=True,
        )
    elif args.delay_seconds > 0:
        print(f"Fixed throttle: {args.delay_seconds}s before/after detail goto", flush=True)

    def process_issue(stub, detail_html: str, issue_timing: IssueCaptureTiming) -> None:
        t_parse = time.perf_counter()
        seed = stub_to_detail_seed(stub)
        detail = parse_detail_page_html(detail_html)
        detail["source_url"] = stub.source_url
        merged = merge_detail_into_seed(seed, detail)
        merged["characters"] = expand_characters_from_raw(merged)
        issue_timing.parser_seconds = round(time.perf_counter() - t_parse, 3)
        issue_timing.image_parse_seconds = 0.0

        t_norm = time.perf_counter()
        norm = normalize_locg_issue(merged, source_name=LOCG_SOURCE_NAME)
        issue_timing.parser_seconds = round(issue_timing.parser_seconds + (time.perf_counter() - t_norm), 3)

        if args.dry_run:
            log_issue_timing(issue_timing)
            return
        assert session is not None
        from app.services.external_catalog.sync_service import _safe_session_rollback

        t_db = time.perf_counter()
        try:
            row, created, updated = upsert_external_issue(session, norm, overwrite_nulls_only=True)
        except Exception as exc:
            _safe_session_rollback(session)
            counters.errors_count += 1
            if len(counters.error_sample) < 20:
                counters.error_sample.append(f"parent upsert {stub.source_url}: {exc}")
            log_issue_timing(issue_timing)
            return
        issue_timing.db_upsert_seconds = round(time.perf_counter() - t_db, 3)
        if created:
            counters.issues_created += 1
        elif updated:
            counters.issues_updated += 1
        t_var = time.perf_counter()
        try:
            v_created, v_updated = upsert_variants(session, row, norm.variants)
            counters.variants_created += v_created + v_updated
        except Exception as exc:
            _safe_session_rollback(session)
            counters.errors_count += 1
            if len(counters.error_sample) < 20:
                counters.error_sample.append(f"detail variants {stub.source_url}: {exc}")
        issue_timing.variant_parse_seconds = round(time.perf_counter() - t_var, 3)
        t_cr = time.perf_counter()
        try:
            counters.creators_created += upsert_creators(session, row, norm.creators)
        except Exception as exc:
            _safe_session_rollback(session)
            counters.errors_count += 1
            if len(counters.error_sample) < 20:
                counters.error_sample.append(f"creators {stub.source_url}: {exc}")
        issue_timing.creator_parse_seconds = round(time.perf_counter() - t_cr, 3)
        t_ch = time.perf_counter()
        try:
            counters.characters_created += upsert_characters(session, row, merged.get("characters") or [])
        except Exception as exc:
            _safe_session_rollback(session)
            counters.errors_count += 1
            if len(counters.error_sample) < 20:
                counters.error_sample.append(f"characters {stub.source_url}: {exc}")
        issue_timing.character_parse_seconds = round(time.perf_counter() - t_ch, 3)
        captured_issue_ids.append(int(row.id or 0))
        log_issue_timing(issue_timing)

    def persist_list_variants(rows, *, list_html=None, page_date=None) -> LocgVariantPersistStats:
        if args.dry_run or session is None:
            return LocgVariantPersistStats()
        trace_path = None
        if raw_dir is not None:
            trace_path = raw_dir / "variant_persist_trace.jsonl"
        stats = upsert_locg_list_variant_rows(
            session,
            rows,
            list_html=list_html,
            page_date=page_date,
            debug_trace_path=trace_path,
            verbose_console=args.verbose_variant_persist,
        )
        if stats.first_variant_failure:
            print(
                "\n=== FIRST VARIANT FAILURE (root transaction abort) ===",
                flush=True,
            )
            print(json.dumps(stats.first_variant_failure, indent=2, default=str), flush=True)
        return stats

    browser_counters = None
    capture_exception: BaseException | None = None

    def _apply_browser_summary(bc) -> None:
        summary.list_page_loaded = bc.list_page_loaded
        summary.list_issues_found = bc.list_issues_found
        summary.list_variants_found = bc.list_variants_found
        summary.list_variants_persisted = bc.list_variants_persisted
        summary.detail_pages_attempted = bc.detail_pages_attempted
        summary.detail_pages_succeeded = bc.detail_pages_succeeded
        summary.errors_count = max(counters.errors_count, bc.errors_count)
        merged_errors = list(counters.error_sample)
        for msg in bc.error_sample:
            if len(merged_errors) >= 10:
                break
            if msg not in merged_errors:
                merged_errors.append(msg)
        summary.error_sample = merged_errors[:10]

    def _post_capture_finalize(exc: BaseException | None = None) -> str | None:
        if args.dry_run or session is None or run is None or browser_counters is None:
            return None
        summary.issues_created = counters.issues_created
        summary.issues_updated = counters.issues_updated
        summary.variants_created = counters.variants_created
        summary.creators_created = counters.creators_created
        summary.characters_created = counters.characters_created
        post_warnings = list(browser_counters.post_capture_warnings)
        status = finalize_browser_capture_sync_run(
            session,
            run=run,
            page_date=page_date,
            browser=browser_counters,
            process_counters=counters,
            max_issues=args.max_issues,
            post_warnings=post_warnings,
            capture_exception=exc,
        )
        summary.sync_run_id = run.id
        summary.status = status
        summary.crosswalk_skipped = not run_crosswalk
        summary.crosswalk_seconds = None
        if run_crosswalk:
            t_xw = time.perf_counter()
            crosswalk_counts = rebuild_external_catalog_crosswalk(
                session, owner_user_id=owner_user_id
            )
            summary.crosswalk_seconds = round(time.perf_counter() - t_xw, 3)
            timing_audit.crosswalk_end_seconds = summary.crosswalk_seconds
            summary.missing_from_lunar_count = int(crosswalk_counts.get("missing_from_lunar", 0))
        return status

    try:
        browser_counters, timing_audit = run_playwright_capture(
            page_date=page_date,
            headless=headless,
            delay_seconds=args.delay_seconds,
            max_issues=args.max_issues,
            dry_run=args.dry_run,
            save_raw_dir=raw_dir,
            process_issue=process_issue,
            should_skip_url=should_skip if args.resume else None,
            persist_list_variants=persist_list_variants,
            timing_audit=timing_audit,
            adaptive_delay=adaptive_controller,
        )
        _apply_browser_summary(browser_counters)

        if not args.dry_run and session is not None:
            _post_capture_finalize(None)

            from sqlmodel import select

            from app.models.external_catalog import ExternalCatalogIssue

            if captured_issue_ids:
                rows = session.exec(
                    select(ExternalCatalogIssue).where(
                        ExternalCatalogIssue.id.in_(captured_issue_ids)
                    )
                ).all()
            else:
                rows = session.exec(
                    select(ExternalCatalogIssue).where(
                        ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
                        ExternalCatalogIssue.release_date == page_date,
                    )
                ).all()
            cov = _field_coverage(rows)
            summary.with_pull_count = cov["with_pull_count"]
            summary.with_want_count = cov["with_want_count"]
            summary.with_foc_date = cov["with_foc_date"]
            summary.with_upc = cov["with_upc"]
            summary.with_distributor_sku = cov["with_distributor_sku"]
            summary.with_cover_image = cov["with_cover_image"]
            sorted_pull = sorted(rows, key=lambda r: (r.pull_count or 0), reverse=True)
            sorted_var = sorted(rows, key=lambda r: (r.variant_count or 0), reverse=True)
            summary.top_10_by_pull_count = [
                {
                    "title": r.title,
                    "pull_count": r.pull_count,
                    "want_count": r.want_count,
                    "source_url": r.source_url,
                }
                for r in sorted_pull[:10]
            ]
            summary.top_10_by_variant_count = [
                {
                    "title": r.title,
                    "variant_count": r.variant_count,
                    "source_url": r.source_url,
                }
                for r in sorted_var[:10]
            ]
        else:
            summary.status = "DRY_RUN" if args.dry_run else summary.status

        summary.performance_audit = timing_audit.build_summary(
            include_per_issue_timings=args.timing_table
        )
        if args.timing_table:
            print("\n--- Per-issue timing table ---")
            for row in timing_audit.issue_timings:
                if row.skipped:
                    continue
                row.finalize()
                print(
                    f"{row.issue_title[:50]:<50} "
                    f"goto={row.page_goto_seconds:5.1f}s "
                    f"wait={row.additional_wait_seconds:5.1f}s "
                    f"(pre={row.pre_goto_sleep_seconds:.1f} post={row.post_load_wait_timeout_seconds:.1f} "
                    f"sel={row.selector_wait_seconds:.1f}) "
                    f"html={row.html_extraction_seconds:4.1f}s "
                    f"parse={row.parser_seconds:4.1f}s "
                    f"db={row.db_upsert_seconds:4.1f}s "
                    f"ready={row.ready_detected} "
                    f"method={row.readiness_method} "
                    f"total={row.total_issue_seconds:5.1f}s"
                )
            print("\n--- Timing breakdown ---")
            for line in summary.performance_audit.get("timing_breakdown_percentages", []):
                print(line)
            print("\n--- Timing summary JSON ---")
            print(json.dumps(summary.performance_audit, indent=2, default=str))
        else:
            pa = summary.performance_audit
            print(
                "\n--- Capture timing (concise; use --timing-table for per-issue rows) ---",
                flush=True,
            )
            print(
                f"issues_timed={pa.get('issues_processed', len(timing_audit.issue_timings))} "
                f"avg_issue_s={pa.get('avg_issue_seconds')} "
                f"total_runtime_s={pa.get('total_runtime_seconds')} "
                f"cloudflare_waits={pa.get('cloudflare_wait_count')}",
                flush=True,
            )

    except RuntimeError as exc:
        capture_exception = exc
        msg = str(exc)
        summary.errors_count += 1
        summary.error_sample = [msg]
        print(msg, file=sys.stderr)
        if "below expected threshold" in msg:
            summary.status = "DISCOVERY_FAILED"
            summary.failures.append(msg)
            hard_failure = True
            if session is not None and run is not None:
                fail_sync_run_preserving_counters(
                    session, run=run, counters=counters, message=msg
                )
        elif session is not None and run is not None and browser_counters is not None:
            _apply_browser_summary(browser_counters)
            status = _post_capture_finalize(exc)
            summary.status = status or summary.status
        elif session is not None and run is not None:
            summary.status = SYNC_FAILED
            summary.failures.append(msg)
            hard_failure = True
            fail_sync_run_preserving_counters(
                session, run=run, counters=counters, message=msg
            )
        else:
            summary.status = SYNC_FAILED
            summary.failures.append(msg)
            hard_failure = True
    except LocgBrowserBlockedError as exc:
        msg = str(exc)
        summary.errors_count += 1
        summary.error_sample = [msg]
        summary.status = "BLOCKED"
        summary.failures.append(msg)
        hard_failure = True
        if session is not None and run is not None:
            fail_sync_run_preserving_counters(
                session, run=run, counters=counters, message=msg
            )
        print(msg, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        capture_exception = exc
        msg = str(exc)
        summary.errors_count += 1
        summary.error_sample = [msg]
        print(msg, file=sys.stderr)
        if session is not None and run is not None and browser_counters is not None:
            _apply_browser_summary(browser_counters)
            status = _post_capture_finalize(exc)
            summary.status = status or SYNC_FAILED
            if summary.status == SYNC_FAILED:
                summary.failures.append(msg)
                hard_failure = True
        elif session is not None and run is not None:
            summary.status = SYNC_FAILED
            summary.failures.append(msg)
            hard_failure = True
            fail_sync_run_preserving_counters(
                session, run=run, counters=counters, message=msg
            )
        else:
            summary.status = SYNC_FAILED
            summary.failures.append(msg)
            hard_failure = True

    print(
        json.dumps(_pilot_summary_for_stdout(summary), indent=2, default=str),
        flush=True,
    )
    return _exit_with_summary()


if __name__ == "__main__":
    raise SystemExit(main())
