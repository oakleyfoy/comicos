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


def _json_safe_persist_audit(audit: dict[str, object]) -> dict[str, object]:
    """Drop non-JSON-serializable in-memory trace maps before stdout report."""
    safe = dict(audit)
    trace = safe.get("candidate_score_trace")
    if isinstance(trace, dict):
        safe["candidate_score_trace_count"] = len(trace)
        safe.pop("candidate_score_trace", None)
    return safe


def _json_safe_rebuild_stats(stats: dict[str, int | float | object]) -> dict[str, object]:
    out: dict[str, object] = dict(stats)
    audit = out.get("cross_system_persist_audit")
    if isinstance(audit, dict):
        out["cross_system_persist_audit"] = _json_safe_persist_audit(audit)
    return out


def _run_rebuild_pipeline(session, *, owner_user_id: int, timer: _QueryTimer) -> dict[str, int | float]:
    from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations
    from app.services.daily_action_engine import generate_daily_actions
    from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

    from app.services.recommendation_title_index import RecommendationPipelineIndexCache

    stage_seconds: dict[str, float] = {}
    pipeline_memory: dict[str, object] = {}
    index_cache = RecommendationPipelineIndexCache(owner_user_id=owner_user_id)

    started = _stage_start("unified_recommendations")
    unified_created = timer.run(
        "rebuild.generate_unified_collector_recommendations",
        lambda: generate_unified_collector_recommendations(
            session,
            owner_user_id=owner_user_id,
            pipeline_report=pipeline_memory,
            index_cache=index_cache,
        ),
    )
    stage_seconds["unified_recommendations"] = _stage_end("unified_recommendations", started)

    started = _stage_start("daily_actions")
    daily_created = timer.run(
        "rebuild.generate_daily_actions",
        lambda: generate_daily_actions(
            session,
            owner_user_id=owner_user_id,
            refresh_unified=False,
            pipeline_report=pipeline_memory,
            index_cache=index_cache,
        ),
    )
    stage_seconds["daily_actions"] = _stage_end("daily_actions", started)

    started = _stage_start("cross_system_recommendations")
    cross_timings: dict[str, float] = {}
    persist_audit: dict[str, object] = {}
    cross_created = timer.run(
        "rebuild.generate_cross_system_recommendations",
        lambda: generate_cross_system_recommendations(
            session,
            owner_user_id=owner_user_id,
            refresh_upstream=False,
            persist_timings=cross_timings,
            persist_audit=persist_audit,
            pipeline_report=pipeline_memory,
            index_cache=index_cache,
        ),
    )
    stage_seconds["cross_system_recommendations"] = _stage_end("cross_system_recommendations", started)
    session.expire_all()

    return {
        "cross_system_rows_inserted": int(cross_created),
        "daily_actions_rows_inserted": int(daily_created),
        "unified_rows_inserted": int(unified_created),
        "stage_elapsed_seconds": stage_seconds,
        "cross_system_build_timings_ms": cross_timings,
        "cross_system_persist_audit": persist_audit,
        "pipeline_memory": pipeline_memory,
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
    from app.services.cross_system_recommendation_engine import (
        RECOMMENDATION_PIPELINE_EPOCH,
        _latest_snapshot_rows,
    )
    from app.services.recommendation_ranking_diagnostics import (
        build_recommendation_ranking_audit,
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
                include_decisions=False,
            ),
        )
        reused_trace = None
        if rebuild_stats is not None:
            persist_audit = rebuild_stats.get("cross_system_persist_audit")
            if isinstance(persist_audit, dict):
                raw_trace = persist_audit.get("candidate_score_trace")
                if isinstance(raw_trace, dict):
                    reused_trace = raw_trace

        ranking_audit = timer.run(
            "compute.ranking_diagnostics",
            lambda: build_recommendation_ranking_audit(
                session,
                owner_user_id=owner_user_id,
                limit=top_limit,
                refresh=False,
                recompute_candidates=reused_trace is None,
                score_trace=reused_trace,
                include_decisions=False,
            ),
        )
        ranking_diag = diagnostics_from_audit(ranking_audit)
        top20 = ranking_audit.items[: min(20, len(ranking_audit.items))]
        spread_ms = None
        if rebuild_stats is not None:
            cross_timings = rebuild_stats.get("cross_system_build_timings_ms")
            if isinstance(cross_timings, dict):
                spread_ms = cross_timings.get("priority_spread")
        top20_conf = [float(r.confidence_score) for r in top20]
        distinct_conf = len({round(c, 4) for c in top20_conf}) if top20_conf else 0
        computed_conf = [
            float(r.computed_confidence_score)
            for r in top20
            if r.computed_confidence_score is not None
        ]
        distinct_computed_conf = len({round(c, 4) for c in computed_conf}) if computed_conf else 0
        spread_verification = {
            "recommendation_pipeline_epoch": RECOMMENDATION_PIPELINE_EPOCH,
            "priority_spread_module": "app.services.recommendation_priority_spread",
            "priority_spread_timing_ms": spread_ms,
            "confidence_spread_timing_ms": (
                cross_timings.get("confidence_spread")
                if rebuild_stats is not None and isinstance(rebuild_stats.get("cross_system_build_timings_ms"), dict)
                else None
            ),
            "top20_raw_populated": bool(top20) and all(r.raw_priority_score is not None for r in top20),
            "top20_normalized_populated": bool(top20)
            and all(r.normalized_priority_score is not None for r in top20),
            "top20_all_priority_100": bool(top20)
            and all(abs(float(r.priority_score) - 100.0) < 1e-9 for r in top20),
            "top20_distinct_confidence_count": distinct_conf,
            "top20_distinct_computed_confidence_count": distinct_computed_conf,
            "top20_all_confidence_1": bool(top20) and all(c >= 0.999 for c in top20_conf),
            "top20_persisted_matches_confidence": bool(top20)
            and all(
                r.computed_confidence_score is not None
                and r.normalized_confidence_score is not None
                and abs(float(r.confidence_score) - float(r.computed_confidence_score)) < 0.01
                and abs(float(r.computed_confidence_score) - float(r.normalized_confidence_score)) < 0.01
                for r in top20
            ),
            "top20_persisted_matches_spread": bool(top20)
            and all(
                r.computed_priority_score is not None
                and r.normalized_priority_score is not None
                and abs(float(r.priority_score) - float(r.computed_priority_score)) < 0.05
                and abs(float(r.computed_priority_score) - float(r.normalized_priority_score)) < 0.05
                for r in top20
            ),
            "pass": bool(top20)
            and all(r.raw_priority_score is not None for r in top20)
            and all(r.normalized_priority_score is not None for r in top20)
            and ranking_diag.distinct_score_count > 15
            and (ranking_diag.top_20_score_spread or 0.0) > 10.0
            and not all(abs(float(r.priority_score) - 100.0) < 1e-9 for r in top20)
            and all(
                r.computed_priority_score is not None
                and abs(float(r.priority_score) - float(r.computed_priority_score)) < 0.05
                for r in top20
            )
            and distinct_conf >= min(15, len(top20))
            and distinct_computed_conf >= min(15, len(top20))
            and not (bool(top20) and all(c >= 0.999 for c in top20_conf))
            and all(
                r.computed_confidence_score is not None
                and abs(float(r.confidence_score) - float(r.computed_confidence_score)) < 0.01
                for r in top20
            ),
        }

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
            "spread_verification": spread_verification,
            "top_20_score_trace": [
                {
                    "rank": row.rank,
                    "title": row.title,
                    "recommendation_type": row.recommendation_type,
                    "raw_priority_score": row.raw_priority_score,
                    "normalized_priority_score": row.normalized_priority_score,
                    "computed_priority_score": row.computed_priority_score,
                    "priority_score": row.priority_score,
                    "raw_confidence_score": row.raw_confidence_score,
                    "normalized_confidence_score": row.normalized_confidence_score,
                    "computed_confidence_score": row.computed_confidence_score,
                    "confidence_score": row.confidence_score,
                    "base_score": row.base_score,
                    "franchise_score": row.franchise_score,
                    "publisher_score": row.publisher_score,
                    "creator_score": row.creator_score,
                    "milestone_score": row.milestone_score,
                    "homage_score": row.homage_score,
                    "audience_score": row.audience_score,
                    "collector_ranking_boost": row.collector_ranking_boost,
                    "final_pre_spread_score": row.final_pre_spread_score,
                }
                for row in ranking_audit.items[:20]
            ],
            "intelligence_validation": (
                ranking_audit.intelligence.model_dump()
                if ranking_audit.intelligence is not None
                else None
            ),
            "top_latest_recommendations": top_rows,
            "query_timings_ms": timer.entries,
            "total_elapsed_ms": total_elapsed_ms,
        }
        if rebuild_stats is not None:
            safe_rebuild = _json_safe_rebuild_stats(rebuild_stats)
            report["rebuild"] = safe_rebuild
            audit = safe_rebuild.get("cross_system_persist_audit")
            if isinstance(audit, dict):
                report["cross_system_persist_audit"] = audit
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
