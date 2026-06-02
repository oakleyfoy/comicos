"""Verify cross-system recommendation generation for a production owner (requires DATABASE_URL)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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
    """Return a User model instance from session.exec result (Row or User)."""
    if row is None:
        return None
    unwrapped = scalar_value(row)
    if unwrapped is None:
        return None
    if hasattr(unwrapped, "_mapping"):
        return unwrapped[0]
    return unwrapped


def _input_diagnostics(session, *, owner_user_id: int) -> dict[str, int]:
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

    inv = session.exec(select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).one()
    pull = session.exec(
        select(func.count()).select_from(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)
    ).one()
    releases = session.exec(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ).one()
    gaps = len(latest_collection_gap_rows(session, owner_user_id=owner_user_id))
    acq = len(latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id))
    grade = len(_latest_grade_rows(session, owner_user_id=owner_user_id))
    hold_sell = len(_latest_hold_sell_rows(session, owner_user_id=owner_user_id))
    sell = len(_latest_sell_candidate_rows(session, owner_user_id=owner_user_id))
    rebalance = len(_latest_rebalance_rows(session, owner_user_id=owner_user_id))
    generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    unified = len(_latest_recommendation_rows(session, owner_user_id=owner_user_id))
    return {
        "inventory_copies": _scalar_int(inv),
        "pull_list_decisions": _scalar_int(pull),
        "release_issues": _scalar_int(releases),
        "collection_gaps": gaps,
        "acquisition_opportunity_rows": acq,
        "grade_before_sell_rows": grade,
        "hold_sell_rows": hold_sell,
        "sell_candidate_rows": sell,
        "portfolio_rebalance_rows": rebalance,
        "unified_collector_recommendation_rows": unified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify cross-system recommendations for an owner email.")
    parser.add_argument("--email", default="ofoy@att.net")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Refuse localhost DATABASE_URL (use Render External Database URL in DATABASE_URL).",
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
        _latest_snapshot_rows,
        build_cross_system_candidates,
        generate_cross_system_recommendations,
    )

    with Session(get_engine()) as session:
        user_row = session.exec(select(User).where(User.email == args.email)).one_or_none()
        user = _unwrap_user(user_row)
        if user is None:
            print(json.dumps({"ok": False, "error": "user_not_found", "email": args.email}, indent=2))
            return 1
        if user.id is None:
            print(json.dumps({"ok": False, "error": "user_missing_id", "email": args.email}, indent=2))
            return 1
        owner_user_id = int(user.id)

        before_total = session.exec(
            select(func.count())
            .select_from(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        ).one()
        before_latest = session.exec(
            select(func.max(CrossSystemRecommendation.created_at)).where(
                CrossSystemRecommendation.owner_user_id == owner_user_id
            )
        ).one()
        daily_count = session.exec(
            select(func.count())
            .select_from(DailyCollectorAction)
            .where(DailyCollectorAction.owner_user_id == owner_user_id)
        ).one()
        snapshot_before = len(_latest_snapshot_rows(session, owner_user_id=owner_user_id))

        created = generate_cross_system_recommendations(session, owner_user_id=owner_user_id)

        after_total = session.exec(
            select(func.count())
            .select_from(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        ).one()
        after_latest = session.exec(
            select(func.max(CrossSystemRecommendation.created_at)).where(
                CrossSystemRecommendation.owner_user_id == owner_user_id
            )
        ).one()
        items, snapshot_after = list_latest_cross_system_recommendations(
            session, owner_user_id=owner_user_id, limit=200, offset=0
        )
        candidates = build_cross_system_candidates(session, owner_user_id=owner_user_id)
        inputs = _input_diagnostics(session, owner_user_id=owner_user_id)

        before_latest_ts = scalar_value(before_latest)
        after_latest_ts = scalar_value(after_latest)

        top10 = [
            {
                "recommendation_rank": i.recommendation_rank,
                "recommendation_type": i.recommendation_type,
                "title": i.title,
                "priority_score": i.priority_score,
                "confidence_score": i.confidence_score,
                "source_systems": i.source_systems,
                "rationale": i.rationale,
            }
            for i in items[:10]
        ]

        report = {
            "ok": True,
            "user": {"id": owner_user_id, "email": user.email},
            "cross_system_recommendation": {
                "row_count_before": _scalar_int(before_total),
                "row_count_after": _scalar_int(after_total),
                "latest_created_at_before": before_latest_ts.isoformat() if before_latest_ts else None,
                "latest_created_at_after": after_latest_ts.isoformat() if after_latest_ts else None,
                "snapshot_size_before": snapshot_before,
                "snapshot_size_after": _scalar_int(snapshot_after),
                "rows_inserted_this_run": _scalar_int(created),
            },
            "daily_collector_action_row_count": _scalar_int(daily_count),
            "candidate_count_after_build": len(candidates),
            "top_10_recommendations": top10,
            "input_diagnostics": inputs,
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
