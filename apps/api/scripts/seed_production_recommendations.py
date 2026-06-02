"""Production-safe release ingest + recommendation pipeline bootstrap for one owner.

Requires DATABASE_URL (Render External URL when run locally). Lunar remote import requires
LUNAR_USERNAME and LUNAR_PASSWORD on the API service or in the shell environment.

Does not delete users, inventory, or orders. Lunar/release import is idempotent via release_import.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

T = TypeVar("T")
SLOW_STAGE_SECONDS = 60.0


class SeedProgress:
    """Line-buffered stdout progress for long production seed runs."""

    def __init__(self) -> None:
        self._pipeline_start = time.monotonic()
        self.stage_timings: list[dict[str, Any]] = []

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def elapsed(self) -> float:
        return time.monotonic() - self._pipeline_start

    def log(
        self,
        message: str,
        *,
        stage: int | None = None,
        rows: int | None = None,
    ) -> None:
        prefix = f"[{stage}] " if stage is not None else ""
        row_suffix = f" rows={rows}" if rows is not None else ""
        print(
            f"{self._timestamp()} {prefix}{message}{row_suffix} elapsed={self.elapsed():.1f}s",
            flush=True,
        )

    def run_step(
        self,
        stage: int,
        label: str,
        fn: Callable[[], T],
        *,
        rows: int | None = None,
    ) -> T:
        self.log(f"START {label}", stage=stage, rows=rows)
        started = time.monotonic()
        try:
            result = fn()
        except Exception:
            elapsed = time.monotonic() - started
            self.log(f"FAILED {label} stage_secs={elapsed:.1f}", stage=stage)
            raise
        elapsed = time.monotonic() - started
        self.log(f"END {label} stage_secs={elapsed:.1f}", stage=stage)
        if elapsed >= SLOW_STAGE_SECONDS:
            self.log(
                f"SLOW STAGE (>{int(SLOW_STAGE_SECONDS)}s): {label} took {elapsed:.1f}s",
                stage=stage,
                rows=rows,
            )
        self.stage_timings.append(
            {
                "stage": stage,
                "label": label,
                "seconds": round(elapsed, 2),
                "rows": rows,
                "slow": elapsed >= SLOW_STAGE_SECONDS,
            }
        )
        return result


def scalar_value(value: object | None) -> object | None:
    if value is None:
        return None
    if hasattr(value, "_mapping"):
        return value[0]
    if isinstance(value, tuple):
        return value[0]
    return value


def scalar_int(value: object | None) -> int:
    return int(scalar_value(value) or 0)


def unwrap_user(row: object | None):
    if row is None:
        return None
    user = scalar_value(row)
    if user is not None and hasattr(user, "_mapping"):
        return user[0]
    return user


def _db_host(url: str) -> str | None:
    m = re.search(r"@([^:/]+)", url)
    return m.group(1).lower() if m else None


def _count_release_issues(session, *, owner_user_id: int) -> int:
    from sqlalchemy import func, select

    from app.models.release_intelligence import ReleaseIssue

    return scalar_int(
        session.exec(
            select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
        ).one()
    )


def _lunar_run_summary(session, *, owner_user_id: int) -> dict[str, Any]:
    from sqlmodel import select

    from app.models.lunar_feed import LunarFeedRun

    runs = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
    ).all()
    last = runs[0] if runs else None
    return {
        "total_runs": len(runs),
        "last_run_id": int(last.id) if last and last.id else None,
        "last_run_status": last.status if last else None,
        "last_run_completed_at": last.completed_at.isoformat() if last and last.completed_at else None,
    }


def _pipeline_metrics(session, *, owner_user_id: int, refresh_unified: bool = False) -> dict[str, int]:
    from sqlalchemy import func, select

    from app.models import InventoryCopy
    from app.models.pull_list import PullListDecision
    from app.models.release_intelligence import ReleaseIssue
    from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
    from app.services.collection_gaps import latest_collection_gap_rows
    from app.services.grade_before_sell import _latest_rows as _latest_grade_rows
    from app.services.hold_sell_intelligence import _latest_hold_sell_rows
    from app.services.portfolio_rebalancing import _latest_rows as _latest_rebalance_rows
    from app.services.sell_candidates import _latest_sell_candidate_rows
    from app.services.unified_collector_intelligence import (
        _latest_recommendation_rows,
        generate_unified_collector_recommendations,
    )

    inv = session.exec(
        select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)
    ).one()
    pull = session.exec(
        select(func.count()).select_from(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)
    ).one()
    releases = session.exec(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ).one()
    if refresh_unified:
        generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    unified = len(_latest_recommendation_rows(session, owner_user_id=owner_user_id))
    return {
        "inventory_copies": scalar_int(inv),
        "pull_list_decisions": scalar_int(pull),
        "release_issues": scalar_int(releases),
        "collection_gaps": len(latest_collection_gap_rows(session, owner_user_id=owner_user_id)),
        "acquisition_opportunity_rows": len(latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)),
        "grade_before_sell_rows": len(_latest_grade_rows(session, owner_user_id=owner_user_id)),
        "hold_sell_rows": len(_latest_hold_sell_rows(session, owner_user_id=owner_user_id)),
        "sell_candidate_rows": len(_latest_sell_candidate_rows(session, owner_user_id=owner_user_id)),
        "portfolio_rebalance_rows": len(_latest_rebalance_rows(session, owner_user_id=owner_user_id)),
        "unified_collector_recommendation_rows": unified,
    }


def _run_release_intelligence_refresh_with_logging(
    session,
    *,
    owner_user_id: int,
    progress: SeedProgress,
) -> dict[str, Any]:
    from app.services.auto_watchlist_agent import run_auto_watchlists
    from app.services.future_buy_queue import build_future_buy_queue
    from app.services.industry_scanner_automation import run_industry_scanner_refresh
    from app.services.key_issue_agent import detect_key_issues
    from app.services.new_number_one_agent import detect_new_number_ones
    from app.services.run_continuity_agent import run_continuity_detection
    from app.services.spec_recommendation_agent import run_spec_recommendations
    from app.services.spec_scoring_agent import run_spec_scoring
    from app.services.variant_intelligence_agent import detect_variant_signals

    substeps: list[tuple[str, Callable[[], None]]] = [
        ("detect_new_number_ones", lambda: detect_new_number_ones(session, owner_user_id=owner_user_id)),
        ("detect_key_issues", lambda: detect_key_issues(session, owner_user_id=owner_user_id)),
        ("detect_variant_signals", lambda: detect_variant_signals(session, owner_user_id=owner_user_id)),
        ("run_continuity_detection", lambda: run_continuity_detection(session, owner_user_id=owner_user_id)),
        ("run_auto_watchlists", lambda: run_auto_watchlists(session, owner_user_id=owner_user_id)),
        ("run_spec_scoring", lambda: run_spec_scoring(session, owner_user_id=owner_user_id)),
        ("run_spec_recommendations", lambda: run_spec_recommendations(session, owner_user_id=owner_user_id)),
        ("build_future_buy_queue", lambda: build_future_buy_queue(session, owner_user_id=owner_user_id)),
        (
            "run_industry_scanner_refresh",
            lambda: run_industry_scanner_refresh(
                session, owner_user_id=owner_user_id, trigger_type="LUNAR_REFRESH"
            ),
        ),
    ]
    for name, fn in substeps:
        progress.run_step(2, f"release_intelligence/{name}", fn)

    return {
        "release_signals_refreshed": True,
        "watchlist_refreshed": True,
        "continuity_refreshed": True,
        "spec_scoring_refreshed": True,
        "spec_recommendations_refreshed": True,
        "future_buy_queue_available": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed release catalog and run recommendation pipeline for one owner.")
    parser.add_argument("--email", default="ofoy@att.net")
    parser.add_argument("--production", action="store_true", help="Refuse localhost DATABASE_URL.")
    parser.add_argument(
        "--skip-lunar-import",
        action="store_true",
        help="Skip Lunar CSV import even when release_issues=0 (diagnostics + downstream only).",
    )
    parser.add_argument(
        "--force-lunar-import",
        action="store_true",
        help="Run Lunar remote import even when release_issues>0 (idempotent re-import).",
    )
    parser.add_argument(
        "--diagnose-only",
        action="store_true",
        help="Print release/Lunar diagnostics only; do not mutate recommendations.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print(json.dumps({"ok": False, "error": "missing_database_url"}, indent=2))
        return 1
    host = _db_host(database_url) or ""
    if args.production and host in {"localhost", "127.0.0.1"}:
        print(json.dumps({"ok": False, "error": "database_url_is_localhost"}, indent=2))
        return 1

    from sqlalchemy import func, select
    from sqlmodel import Session

    from app.db.session import get_engine
    from app.models import User
    from app.services.acquisition_opportunities import persist_acquisition_opportunities
    from app.services.collection_gaps import persist_collection_gaps
    from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
    from app.services.cross_system_recommendation_engine import (
        build_cross_system_candidates,
        generate_cross_system_recommendations,
    )
    from app.services.daily_action_engine import generate_daily_actions
    from app.services.lunar_credentials import get_credential_status
    from app.services.pull_list_automation import refresh_owner_pull_list
    from app.services.recommendation_v2_engine import generate_recommendations_v2
    from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

    report: dict[str, Any] = {"ok": True, "email": args.email, "steps": {}}
    progress = SeedProgress()
    progress.log(f"seed_production_recommendations start email={args.email} db_host={host or 'unknown'}")

    with Session(get_engine()) as session:
        user = unwrap_user(session.exec(select(User).where(User.email == args.email)).one_or_none())
        if user is None:
            print(json.dumps({"ok": False, "error": "user_not_found", "email": args.email}, indent=2), flush=True)
            return 1
        if user.id is None:
            print(json.dumps({"ok": False, "error": "user_missing_id", "email": args.email}, indent=2), flush=True)
            return 1
        owner_user_id = int(user.id)
        report["owner_user_id"] = owner_user_id
        progress.log(f"resolved owner_user_id={owner_user_id}")

        release_count = progress.run_step(
            0,
            "count_release_issues",
            lambda: _count_release_issues(session, owner_user_id=owner_user_id),
        )
        lunar_diag = _lunar_run_summary(session, owner_user_id=owner_user_id)
        creds = get_credential_status()
        progress.log(
            "bootstrap pipeline_metrics (read-only counts)",
            rows=release_count,
        )
        pipeline_before = progress.run_step(
            0,
            "pipeline_metrics_before",
            lambda: _pipeline_metrics(session, owner_user_id=owner_user_id),
            rows=release_count,
        )
        report["diagnostics_before"] = {
            "release_issues": release_count,
            "lunar": lunar_diag,
            "lunar_credentials_available": creds.credential_available,
            "lunar_username_masked": creds.username_masked,
            "pipeline": pipeline_before,
        }

        if args.diagnose_only:
            report["progress"] = {"stage_timings": progress.stage_timings}
            print(json.dumps(report, indent=2), flush=True)
            return 0

        should_import = (
            not args.skip_lunar_import
            and creds.credential_available
            and (release_count == 0 or args.force_lunar_import)
        )
        lunar_ran_intelligence_refresh = False

        if should_import:
            try:
                from app.services.lunar_feed_downloader import download_latest_monthly_products_csv
                from app.services.lunar_feed_import import import_lunar_csv_bytes

                def _lunar_import() -> Any:
                    downloaded = progress.run_step(
                        1,
                        "Lunar download CSV",
                        lambda: download_latest_monthly_products_csv(),
                    )
                    progress.log(
                        f"Lunar file={downloaded.file_name} period={downloaded.file_period} "
                        f"bytes={len(downloaded.content_bytes)}",
                        stage=1,
                    )
                    return progress.run_step(
                        1,
                        "Lunar parse import and release refresh",
                        lambda: import_lunar_csv_bytes(
                            session,
                            owner_user_id=owner_user_id,
                            file_name=downloaded.file_name,
                            content_bytes=downloaded.content_bytes,
                            file_period=downloaded.file_period,
                            source_type="REMOTE",
                            source_url=downloaded.source_url,
                        ),
                        rows=len(downloaded.content_bytes),
                    )

                summary = _lunar_import()
                report["steps"]["lunar_import"] = summary.model_dump()
                lunar_ran_intelligence_refresh = summary.status in {"COMPLETED", "PARTIAL"}
                progress.log(
                    f"Lunar import status={summary.status} records_processed={summary.records_processed}",
                    stage=1,
                    rows=summary.records_processed,
                )
            except Exception as exc:  # noqa: BLE001
                report["ok"] = False
                report["steps"]["lunar_import"] = {"error": str(exc)}
                report["progress"] = {"stage_timings": progress.stage_timings}
                print(json.dumps(report, indent=2), flush=True)
                return 1
        else:
            skip_reason = "skip_lunar_import_flag"
            if not creds.credential_available:
                skip_reason = "lunar_credentials_missing"
            elif release_count > 0 and not args.force_lunar_import:
                skip_reason = "release_issues_already_present"
            report["steps"]["lunar_import"] = {"skipped": True, "reason": skip_reason}
            progress.log(f"SKIP Lunar import reason={skip_reason}", stage=1)

        release_count_after = progress.run_step(
            1,
            "count_release_issues_after_import",
            lambda: _count_release_issues(session, owner_user_id=owner_user_id),
        )
        report["release_issues_after_import"] = release_count_after

        if release_count_after == 0:
            report["ok"] = False
            report["error"] = "release_catalog_empty_after_import"
            report["progress"] = {"stage_timings": progress.stage_timings}
            print(json.dumps(report, indent=2), flush=True)
            return 1

        if lunar_ran_intelligence_refresh:
            progress.log(
                "SKIP release intelligence refresh (already executed inside Lunar import)",
                stage=2,
                rows=release_count_after,
            )
            report["steps"]["release_intelligence_refresh"] = {
                "skipped": True,
                "reason": "already_ran_in_lunar_import",
            }
        else:
            refresh_summary = progress.run_step(
                2,
                "Release intelligence refresh",
                lambda: _run_release_intelligence_refresh_with_logging(
                    session, owner_user_id=owner_user_id, progress=progress
                ),
                rows=release_count_after,
            )
            report["steps"]["release_intelligence_refresh"] = refresh_summary

        def _v2_progress(message: str) -> None:
            progress.log(message, stage=3, rows=release_count_after)

        v2_run = progress.run_step(
            3,
            "Recommendation V2",
            lambda: generate_recommendations_v2(
                session,
                owner_user_id=owner_user_id,
                progress_callback=_v2_progress,
            ),
            rows=release_count_after,
        )
        report["steps"]["recommendation_v2"] = {
            "run_id": int(v2_run.id or 0),
            "status": v2_run.status,
            "issues_scored": v2_run.issues_scored,
            "variants_scored": v2_run.variants_scored,
            "recommendations_created": v2_run.recommendations_created,
        }

        pull_refresh = progress.run_step(
            4,
            "Pull-list generation",
            lambda: refresh_owner_pull_list(session, owner_user_id=owner_user_id),
            rows=release_count_after,
        )
        report["steps"]["pull_list_refresh"] = asdict(pull_refresh)
        progress.log(
            f"pull_list releases_processed={pull_refresh.releases_processed} "
            f"decisions_created={pull_refresh.decisions_created}",
            stage=4,
            rows=pull_refresh.releases_processed,
        )

        gaps_created = progress.run_step(
            5,
            "Collection gaps",
            lambda: persist_collection_gaps(session, owner_user_id=owner_user_id),
            rows=pipeline_before.get("inventory_copies"),
        )
        report["steps"]["collection_gaps"] = {"rows_appended": gaps_created}

        acq_created = progress.run_step(
            6,
            "Acquisition opportunities",
            lambda: persist_acquisition_opportunities(session, owner_user_id=owner_user_id),
            rows=pipeline_before.get("inventory_copies"),
        )
        report["steps"]["acquisition_opportunities"] = {"rows_appended": acq_created}

        unified_created = progress.run_step(
            7,
            "Unified recommendations",
            lambda: generate_unified_collector_recommendations(session, owner_user_id=owner_user_id),
            rows=release_count_after,
        )
        report["steps"]["unified_collector_recommendations"] = {"rows_appended": unified_created}

        cross_created = progress.run_step(
            8,
            "Cross-system recommendations",
            lambda: generate_cross_system_recommendations(session, owner_user_id=owner_user_id),
            rows=release_count_after,
        )
        report["steps"]["cross_system_recommendations"] = {"rows_appended": cross_created}

        daily_created = progress.run_step(
            8,
            "Daily actions (after cross-system)",
            lambda: generate_daily_actions(session, owner_user_id=owner_user_id),
        )
        report["steps"]["daily_actions"] = {"rows_appended": daily_created}

        def _finalize_reads() -> tuple[int, int]:
            _, snapshot_size = list_latest_cross_system_recommendations(
                session, owner_user_id=owner_user_id, limit=200, offset=0
            )
            candidates = build_cross_system_candidates(session, owner_user_id=owner_user_id)
            return snapshot_size, len(candidates)

        snapshot_size, candidate_count = progress.run_step(
            9,
            "Commit and finalize",
            lambda: _finalize_reads(),
        )
        progress.run_step(
            9,
            "session.commit",
            lambda: session.commit() or None,
        )

        report["diagnostics_after"] = {
            "release_issues": release_count_after,
            "pipeline": progress.run_step(
                9,
                "pipeline_metrics_after",
                lambda: _pipeline_metrics(session, owner_user_id=owner_user_id, refresh_unified=False),
                rows=release_count_after,
            ),
            "candidate_count_after_build": candidate_count,
            "cross_system_snapshot_size": snapshot_size,
        }

        passed = (
            release_count_after > 0
            and (unified_created > 0 or candidate_count > 0)
            and snapshot_size > 0
        )
        report["pass"] = passed
        report["progress"] = {
            "stage_timings": progress.stage_timings,
            "total_elapsed_seconds": round(progress.elapsed(), 2),
        }
        if not passed:
            report["ok"] = False
            report["hint"] = (
                "If snapshot still empty, confirm Lunar catalog has upcoming FOC rows, "
                "pull-list decisions were created, and collection/acquisition engines produced candidates."
            )

    progress.log("seed_production_recommendations complete")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
