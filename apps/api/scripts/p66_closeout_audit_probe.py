"""Read-only P66 closeout probes against DATABASE_URL."""

from __future__ import annotations

import json
import os
import sys

from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.services.printing_backfill import candidate_issue_ids, load_lunar_reprint_index, build_proposal
from app.models.release_intelligence import ReleaseSeries
from app.services.printing_intelligence import PRINTING_KIND_FIRST, resolve_printing_schedule
from app.services.recommendation_decision_engine import (
    build_recommendation_decision_context,
    decision_for_cross_system,
)
from app.models.cross_system_recommendation import CrossSystemRecommendation


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print(json.dumps({"error": "DATABASE_URL not set"}))
        return 1

    engine = get_engine()
    out: dict = {}

    with engine.connect() as conn:
        out["alembic_version"] = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        issue_cols = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='release_issue' AND column_name IN ('original_release_date','original_foc_date')"
            )
        ).fetchall()
        var_cols = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='release_variant' AND column_name LIKE 'printing%'"
            )
        ).fetchall()
        out["release_issue_p66_columns"] = sorted(r[0] for r in issue_cols)
        out["release_variant_p66_columns"] = sorted(r[0] for r in var_cols)

    with Session(engine) as session:
        issue = session.get(ReleaseIssue, 1278)
        if issue:
            variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == 1278)).all())
            sched = resolve_printing_schedule(issue, variants)
            out["tigress_1278"] = {
                "title": issue.title,
                "release_date": issue.release_date.isoformat() if issue.release_date else None,
                "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
                "original_release_date": issue.original_release_date.isoformat() if issue.original_release_date else None,
                "schedule_badge": sched.printing_badge,
                "variants": [
                    {
                        "id": v.id,
                        "code": v.source_item_code,
                        "printing_kind": v.printing_kind,
                        "printing_number": v.printing_number,
                        "printing_release_date": v.printing_release_date.isoformat() if v.printing_release_date else None,
                        "printing_foc_date": v.printing_foc_date.isoformat() if v.printing_foc_date else None,
                    }
                    for v in variants
                ],
            }
            rec = session.exec(
                select(CrossSystemRecommendation)
                .where(CrossSystemRecommendation.owner_user_id == 1)
                .where(CrossSystemRecommendation.title.ilike("%Tigress Island%"))
                .order_by(CrossSystemRecommendation.created_at.desc())
            ).first()
            if rec:
                ctx = build_recommendation_decision_context(session, owner_user_id=1)
                d = decision_for_cross_system(
                    session=session,
                    owner_user_id=1,
                    ctx=ctx,
                    recommendation_type=rec.recommendation_type,
                    title=rec.title,
                    priority_score=rec.priority_score,
                    confidence_score=rec.confidence_score,
                    rationale=rec.rationale,
                    source_systems=list(rec.source_systems or []),
                    estimated_value=rec.estimated_value,
                )
                out["tigress_decision"] = {
                    "title": rec.title,
                    "printing_badge": d.printing_badge.label if d.printing_badge else None,
                    "original_release_date": d.original_release_date.isoformat() if d.original_release_date else None,
                    "printing_release_date": d.printing_release_date.isoformat() if d.printing_release_date else None,
                    "printing_foc_date": d.printing_foc_date.isoformat() if d.printing_foc_date else None,
                }

        lunar = load_lunar_reprint_index(session)
        ids = candidate_issue_ids(session, owner_user_id=1, lunar_by_code=lunar)
        pollution_failures: list[dict] = []
        high_remaining = 0
        for iid in ids:
            pair = session.exec(
                select(ReleaseIssue, ReleaseSeries)
                .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
                .where(ReleaseIssue.id == iid)
            ).first()
            if not pair:
                continue
            issue, series = pair
            variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == iid)).all())
            proposal = build_proposal(
                session,
                owner_user_id=int(issue.owner_user_id),
                issue=issue,
                series=series,
                variants=variants,
                lunar_by_code=lunar,
            )
            if proposal and proposal.get("confidence") == "HIGH" and proposal.get("would_change_issue_dates"):
                high_remaining += 1
            reprint = [v for v in variants if (v.printing_kind or PRINTING_KIND_FIRST) != PRINTING_KIND_FIRST]
            polluted = False
            for v in reprint:
                if (
                    v.printing_release_date
                    and issue.release_date == v.printing_release_date
                    and issue.original_release_date != issue.release_date
                ):
                    polluted = True
                if v.printing_foc_date and issue.foc_date == v.printing_foc_date:
                    polluted = True
            if polluted:
                pollution_failures.append({"issue_id": iid, "title": issue.title})

        out["owner1_reprint_candidates"] = len(ids)
        out["high_confidence_would_change_remaining"] = high_remaining
        out["issue_row_pollution_failures"] = pollution_failures

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
