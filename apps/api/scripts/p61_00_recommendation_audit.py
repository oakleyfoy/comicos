"""P61-00: export Top Recommendations audit JSON + optional markdown report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _export_top20_candidates(session, *, owner_user_id: int, limit: int = 20) -> dict:
    from app.services.cross_system_recommendation_engine import (
        _confidence_for_persist,
        _priority_for_persist,
        build_cross_system_candidates,
    )

    cands = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=False,
    )
    cands.sort(key=lambda c: (-float(c.priority_score), c.title_key))
    top = cands[:limit]
    rows = []
    for i, c in enumerate(top, 1):
        bd = getattr(c, "collector_score_breakdown", None)
        rows.append(
            {
                "rank": i,
                "title": c.title,
                "recommendation_type": c.recommendation_type,
                "priority_score": round(float(c.priority_score), 2),
                "confidence_score": round(float(c.confidence_score), 4),
                "raw_priority_score": round(float(c.raw_priority_score or c.priority_score), 2),
                "normalized_priority_score": round(
                    float(c.normalized_priority_score or c.priority_score), 2
                ),
                "computed_priority_score": round(float(_priority_for_persist(c)), 2),
                "raw_confidence_score": round(float(c.raw_confidence_score or c.confidence_score), 4),
                "normalized_confidence_score": round(
                    float(c.normalized_confidence_score or c.confidence_score), 4
                ),
                "computed_confidence_score": round(float(_confidence_for_persist(c)), 4),
                "base_score": bd.base_score if bd else None,
                "franchise_score": bd.franchise_score if bd else None,
                "publisher_score": bd.publisher_score if bd else None,
                "creator_score": bd.creator_score if bd else None,
                "milestone_score": bd.milestone_score if bd else None,
                "homage_score": bd.homage_score if bd else None,
                "audience_score": bd.audience_score if bd else None,
                "collector_ranking_boost": bd.ranking_boost if bd else None,
                "final_pre_spread_score": bd.final_score if bd else None,
            }
        )
    youngblood = [
        {
            "title": c.title,
            "priority_score": float(c.priority_score),
            "candidate_order": cands.index(c) + 1,
        }
        for c in cands
        if "youngblood" in c.title.lower()
    ]
    return {
        "candidate_pool_size": len(cands),
        "top_n": rows,
        "youngblood_in_pool": youngblood,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P61-00 recommendation audit export")
    parser.add_argument("--email", default="ofoy@att.net")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument(
        "--fallback-email",
        default="",
        help="If primary owner has no release rows, also export candidate top-N for this email.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1

    from sqlalchemy import func, select
    from sqlmodel import Session

    from app.db.session import get_engine
    from app.models import User
    from app.models.release_intelligence import ReleaseIssue
    from app.services.recommendation_ranking_diagnostics import (
        build_recommendation_ranking_audit,
        diagnostics_from_audit,
    )

    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == args.email)).one_or_none()
        if user is None or user.id is None:
            print(json.dumps({"ok": False, "error": "user_not_found"}))
            return 1
        owner_user_id = int(user.id)
        release_count = int(
            session.exec(
                select(func.count())
                .select_from(ReleaseIssue)
                .where(ReleaseIssue.owner_user_id == owner_user_id)
            ).one()
            or 0
        )

        audit = build_recommendation_ranking_audit(
            session,
            owner_user_id=owner_user_id,
            limit=args.top,
            refresh=False,
        )
        diag = diagnostics_from_audit(audit)
        candidate_export = None
        if release_count > 0:
            candidate_export = _export_top20_candidates(
                session, owner_user_id=owner_user_id, limit=args.top
            )
        elif args.fallback_email:
            fb = session.exec(select(User).where(User.email == args.fallback_email)).one_or_none()
            if fb and fb.id:
                candidate_export = _export_top20_candidates(
                    session, owner_user_id=int(fb.id), limit=args.top
                )
                candidate_export["fallback_owner_email"] = args.fallback_email

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "test_owner_email": args.email,
            "test_owner_user_id": owner_user_id,
            "release_issue_count": release_count,
            "persisted_ranking_audit": json.loads(audit.model_dump_json()),
            "ranking_diagnostics": json.loads(diag.model_dump_json()),
            "live_candidate_export": candidate_export,
        }
        print(json.dumps(payload, indent=2))

        if args.write_report:
            report_path = os.path.join(REPO_ROOT, "docs", "P61_00_RECOMMENDATION_AUDIT_REPORT.md")
            # Report body is maintained in-repo; script prints JSON for regeneration workflows.
            print(f"wrote_json_only; edit {report_path} from payload or extend --write-report", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
