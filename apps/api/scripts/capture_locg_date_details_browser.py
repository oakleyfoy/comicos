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
    performance_audit: dict[str, object] = field(default_factory=dict)


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
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if args.production and not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required for --production", file=sys.stderr)
        return 1
    if args.min_delay_seconds > args.max_delay_seconds:
        print("error: --min-delay-seconds must be <= --max-delay-seconds", file=sys.stderr)
        return 1

    page_date = date.fromisoformat(args.date)
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
    from app.services.external_catalog.sync_service import (
        SYNC_COMPLETED,
        SYNC_FAILED,
        SYNC_PARTIAL,
        complete_sync_run,
        create_sync_run,
        ensure_locg_source,
        fail_sync_run,
        should_skip_browser_resume,
        upsert_characters,
        upsert_creators,
        upsert_external_issue,
        LocgVariantPersistStats,
        upsert_locg_list_variant_rows,
        upsert_variants,
    )
    from app.services.external_catalog.sync_service import SyncCounters

    summary = PilotSummary(date=page_date.isoformat(), dry_run=args.dry_run)
    raw_dir = None
    if args.save_raw:
        raw_dir = Path(ROOT).parent.parent / "data" / "locg_browser_capture" / page_date.isoformat()

    session = None
    run = None
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

            owner_user_id = resolve_owner_user_id(session, args.email)

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
        summary.list_page_loaded = browser_counters.list_page_loaded
        summary.list_issues_found = browser_counters.list_issues_found
        summary.list_variants_found = browser_counters.list_variants_found
        summary.list_variants_persisted = browser_counters.list_variants_persisted
        summary.detail_pages_attempted = browser_counters.detail_pages_attempted
        summary.detail_pages_succeeded = browser_counters.detail_pages_succeeded
        summary.errors_count = browser_counters.errors_count
        summary.error_sample = browser_counters.error_sample[:10]

        if not args.dry_run and session is not None:
            summary.issues_created = counters.issues_created
            summary.issues_updated = counters.issues_updated
            summary.variants_created = counters.variants_created
            summary.creators_created = counters.creators_created
            summary.characters_created = counters.characters_created
            counters.pages_scanned = 1 if summary.list_page_loaded else 0
            counters.errors_count = summary.errors_count
            counters.error_sample = summary.error_sample
            status = SYNC_PARTIAL if summary.errors_count else SYNC_COMPLETED
            if summary.detail_pages_succeeded < summary.list_issues_found and args.max_issues is None:
                status = SYNC_PARTIAL
            assert run is not None
            complete_sync_run(session, run=run, counters=counters, status=status)
            summary.sync_run_id = run.id
            summary.status = status

            t_xw = time.perf_counter()
            crosswalk_counts = rebuild_external_catalog_crosswalk(
                session, owner_user_id=owner_user_id
            )
            timing_audit.crosswalk_end_seconds = round(time.perf_counter() - t_xw, 3)
            summary.missing_from_lunar_count = int(crosswalk_counts.get("missing_from_lunar", 0))

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

        summary.performance_audit = timing_audit.build_summary()
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
        if "locg capture certification failed" in str(exc).lower():
            summary.errors_count += 1
            summary.error_sample = [str(exc)]
            summary.status = "CERTIFICATION_FAILED"
            print(str(exc), file=sys.stderr)
            if session is not None and run is not None:
                fail_sync_run(session, run=run, message=str(exc))
            return 4
        if "below expected threshold" in str(exc):
            summary.errors_count += 1
            summary.error_sample = [str(exc)]
            summary.status = "DISCOVERY_FAILED"
            print(str(exc), file=sys.stderr)
            if session is not None and run is not None:
                fail_sync_run(session, run=run, message=str(exc))
            return 3
        raise
    except LocgBrowserBlockedError as exc:
        summary.errors_count += 1
        summary.error_sample = [str(exc)]
        summary.status = "BLOCKED"
        if session is not None and run is not None:
            fail_sync_run(session, run=run, message=str(exc))
        print(json.dumps(summary.__dict__, indent=2, default=str))
        return 2
    except Exception as exc:  # noqa: BLE001
        summary.errors_count += 1
        summary.error_sample = [str(exc)]
        if session is not None and run is not None:
            fail_sync_run(session, run=run, message=str(exc))
        print(json.dumps(summary.__dict__, indent=2, default=str))
        raise

    print(json.dumps(summary.__dict__, indent=2, default=str))
    return 0 if summary.errors_count == 0 and summary.list_page_loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
