"""Measure RSS + row counts for full recommendation rebuild (local or production DATABASE_URL)."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.cross_system_recommendation_engine import build_cross_system_candidates
from app.services.daily_action_engine import generate_daily_actions
from app.services.recommendation_pipeline_diagnostics import process_rss_mb
from app.services.unified_collector_intelligence import generate_unified_collector_recommendations


def main() -> int:
    owner_id = int(os.environ.get("OWNER_USER_ID", "0") or "0")
    with Session(get_engine()) as session:
        if owner_id <= 0:
            user = session.exec(select(User).order_by(User.id.asc())).first()
            if user is None or user.id is None:
                print("No users — set OWNER_USER_ID or register locally.", file=sys.stderr)
                return 1
            owner_id = int(user.id)

        from app.services.recommendation_title_index import RecommendationPipelineIndexCache

        index_cache = RecommendationPipelineIndexCache(owner_user_id=owner_id)
        report: dict[str, object] = {"owner_user_id": owner_id, "rss_start_mb": round(process_rss_mb(), 2)}
        generate_unified_collector_recommendations(
            session,
            owner_user_id=owner_id,
            pipeline_report=report,
            index_cache=index_cache,
        )
        generate_daily_actions(
            session,
            owner_user_id=owner_id,
            refresh_unified=False,
            pipeline_report=report,
            index_cache=index_cache,
        )
        from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations

        generate_cross_system_recommendations(
            session,
            owner_user_id=owner_id,
            refresh_upstream=False,
            pipeline_report=report,
            index_cache=index_cache,
        )
        candidates = build_cross_system_candidates(session, owner_user_id=owner_id, refresh_upstream=False)
        report["candidate_count"] = len(candidates)
        report["rss_end_mb"] = round(process_rss_mb(), 2)
        print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
