"""Read-only production verification for cross-system recommendations (requires DATABASE_URL)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from typing import TypeVar

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

T = TypeVar("T")


def _db_host(url: str) -> str | None:
    m = re.search(r"@([^:/]+)", url)
    return m.group(1).lower() if m else None


def scalar_value(value: object | None) -> object | None:
    if value is None:
        return None
    if hasattr(value, "_mapping"):
        return value[0]
    if isinstance(value, tuple):
        return value[0]
    return value


def _scalar_int(value: object | None) -> int:
    return int(scalar_value(value) or 0)


def _unwrap_user(row: object | None):
    if row is None:
        return None
    unwrapped = scalar_value(row)
    if unwrapped is None:
        return None
    if hasattr(unwrapped, "_mapping"):
        return unwrapped[0]
    return unwrapped


class _QueryTimer:
    def __init__(self) -> None:
        self.entries: list[dict[str, float | str]] = []

    def run(self, name: str, fn: Callable[[], T]) -> T:
        started = time.monotonic()
        result = fn()
        duration_ms = round((time.monotonic() - started) * 1000.0, 2)
        self.entries.append({"query": name, "duration_ms": duration_ms})
        print(f"timing {name} {duration_ms:.1f}ms", file=sys.stderr, flush=True)
        return result


def _stage_start(name: str) -> float:
    print(f"START {name}", file=sys.stderr, flush=True)
    return time.monotonic()


def _stage_end(name: str, started: float) -> float:
    elapsed_s = time.monotonic() - started
    print(f"END {name} elapsed={elapsed_s:.2f}s", file=sys.stderr, flush=True)
    return elapsed_s


def _run_rebuild_pipeline(session, *, owner_user_id: int, timer: _QueryTimer) -> dict[str, int | float]:
    from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations
    from app.services.daily_action_engine import generate_daily_actions
    from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

    stage_seconds: dict[str, float] = {}

    started = _stage_start("unified_recommendations")
    unified_created = timer.run(
        "rebuild.generate_unified_collector_recommendations",
        lambda: generate_unified_collector_recommendations(session, owner_user_id=owner_user_id),
    )
    stage_seconds["unified_recommendations"] = _stage_end("unified_recommendations", started)

    started = _stage_start("daily_actions")
    daily_created = timer.run(
        "rebuild.generate_daily_actions",
        lambda: generate_daily_actions(
            session, owner_user_id=owner_user_id, refresh_unified=False
        ),
    )
    stage_seconds["daily_actions"] = _stage_end("daily_actions", started)

    started = _stage_start("cross_system_recommendations")
    cross_timings: dict[str, float] = {}
    cross_created = timer.run(
        "rebuild.generate_cross_system_recommendations",
        lambda: generate_cross_system_recommendations(
            session,
            owner_user_id=owner_user_id,
            refresh_upstream=False,
            persist_timings=cross_timings,
        ),
    )
    stage_seconds["cross_system_recommendations"] = _stage_end("cross_system_recommendations", started)

    return {
        "cross_system_rows_inserted": int(cross_created),
        "daily_actions_rows_inserted": int(daily_created),
        "unified_rows_inserted": int(unified_created),
        "stage_elapsed_seconds": stage_seconds,
        "cross_system_build_timings_ms": cross_timings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect cross-system recommendations for an owner (read-only by default).",
    )
    parser.add_argument("--email", default="ofoy@att.net")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Refuse localhost DATABASE_URL (use Render External Database URL in DATABASE_URL).",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate unified, daily, and cross-system recommendations before inspection.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of latest snapshot rows to include in the report (default 20).",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: set DATABASE_URL to the Render External Database URL before running", file=sys.stderr)
        return 1
    host = _db_host(database_url) or ""
    if args.production and host in {"localhost", "127.0.0.1"}:
        print(
            "error: DATABASE_URL points at localhost; export Render External Database URL "
            "(Remove-Item Env:COMICOS_API_ENV_ROOT if a local .env is being loaded).",
            file=sys.stderr,
        )
        return 1

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from sqlalchemy import func, select
    from sqlmodel import Session

    from app.db.session import get_engine
    from app.models import User
    from app.models.cross_system_recommendation import CrossSystemRecommendation
    from app.models.daily_action_engine import DailyCollectorAction
    from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
    from app.services.cross_system_recommendation_engine import _latest_snapshot_rows
    from app.services.recommendation_ranking_diagnostics import (
        audit_from_listed_items,
        diagnostics_from_audit,
    )

    timer = _QueryTimer()
    pipeline_started = time.monotonic()
    top_limit = min(max(int(args.top), 1), 100)

    with Session(get_engine()) as session:
        user_row = timer.run(
            "lookup.user_by_email",
            lambda: session.exec(select(User).where(User.email == args.email)).one_or_none(),
        )
        user = _unwrap_user(user_row)
        if user is None:
            print(json.dumps({"ok": False, "error": "user_not_found", "email": args.email}, indent=2))
            return 1
        if user.id is None:
            print(json.dumps({"ok": False, "error": "user_missing_id", "email": args.email}, indent=2))
            return 1
        owner_user_id = int(user.id)

        rebuild_stats: dict[str, int | float] | None = None
        if args.rebuild:
            print("START rebuild_pipeline", file=sys.stderr, flush=True)
            rebuild_started = time.monotonic()
            rebuild_stats = _run_rebuild_pipeline(session, owner_user_id=owner_user_id, timer=timer)
            rebuild_elapsed = time.monotonic() - rebuild_started
            print(f"END rebuild_pipeline elapsed={rebuild_elapsed:.2f}s", file=sys.stderr, flush=True)

        cross_total = timer.run(
            "count.cross_system_recommendation",
            lambda: session.exec(
                select(func.count())
                .select_from(CrossSystemRecommendation)
                .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            ).one(),
        )
        cross_latest_created = timer.run(
            "max.cross_system_recommendation.created_at",
            lambda: session.exec(
                select(func.max(CrossSystemRecommendation.created_at)).where(
                    CrossSystemRecommendation.owner_user_id == owner_user_id
                )
            ).one(),
        )
        daily_count = timer.run(
            "count.daily_collector_action",
            lambda: session.exec(
                select(func.count())
                .select_from(DailyCollectorAction)
                .where(DailyCollectorAction.owner_user_id == owner_user_id)
            ).one(),
        )
        snapshot = timer.run(
            "read.latest_cross_system_snapshot",
            lambda: _latest_snapshot_rows(session, owner_user_id=owner_user_id),
        )
        items, list_total = timer.run(
            "read.list_latest_cross_system_recommendations",
            lambda: list_latest_cross_system_recommendations(
                session,
                owner_user_id=owner_user_id,
                limit=top_limit,
                offset=0,
            ),
        )
        ranking_audit = timer.run(
            "compute.ranking_diagnostics",
            lambda: audit_from_listed_items(items, total_count=list_total),
        )
        ranking_diag = diagnostics_from_audit(ranking_audit)

        latest_created_ts = scalar_value(cross_latest_created)
        top_rows = [
            {
                "recommendation_rank": i.recommendation_rank,
                "recommendation_type": i.recommendation_type,
                "title": i.title,
                "priority_score": i.priority_score,
                "confidence_score": i.confidence_score,
                "created_at": i.created_at.isoformat() if hasattr(i.created_at, "isoformat") else str(i.created_at),
            }
            for i in items[:top_limit]
        ]

        total_elapsed_ms = round((time.monotonic() - pipeline_started) * 1000.0, 2)
        print(f"timing total {total_elapsed_ms:.1f}ms", file=sys.stderr, flush=True)

        report: dict[str, object] = {
            "ok": True,
            "mode": "rebuild" if args.rebuild else "read_only",
            "owner_user_id": owner_user_id,
            "user_email": user.email,
            "cross_system_recommendation_row_count": _scalar_int(cross_total),
            "latest_snapshot_size": len(snapshot),
            "latest_recommendation_timestamp": latest_created_ts.isoformat() if latest_created_ts else None,
            "daily_collector_action_row_count": _scalar_int(daily_count),
            "ranking_diagnostics": {
                "sort_order_valid": ranking_diag.sort_order_valid,
                "appears_alphabetical_by_title": ranking_diag.appears_alphabetical_by_title,
                "distinct_score_count": ranking_diag.distinct_score_count,
                "top_20_score_spread": ranking_diag.top_20_score_spread,
            },
            "top_20_score_trace": [
                {
                    "rank": row.rank,
                    "title": row.title,
                    "recommendation_type": row.recommendation_type,
                    "raw_priority_score": row.raw_priority_score,
                    "normalized_priority_score": row.normalized_priority_score,
                    "priority_score": row.priority_score,
                    "confidence_score": row.confidence_score,
                }
                for row in ranking_audit.items[:20]
            ],
            "top_latest_recommendations": top_rows,
            "query_timings_ms": timer.entries,
            "total_elapsed_ms": total_elapsed_ms,
        }
        if rebuild_stats is not None:
            report["rebuild"] = rebuild_stats
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
