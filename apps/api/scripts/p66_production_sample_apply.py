"""Apply a fixed production sample set (10 issues). One transaction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.printing_backfill import apply_proposal, build_proposal, classify_confidence, load_lunar_reprint_index
from app.services.printing_intelligence import resolve_printing_schedule
from app.services.recommendation_decision_engine import build_recommendation_decision_context, decision_for_cross_system
from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from sqlmodel import select


SAMPLE_ISSUE_IDS = [7, 40, 38, 79, 132, 161, 391, 459, 462, 681]


def confidence_reason(proposal: dict) -> str:
    parts: list[str] = []
    if proposal.get("locg_first_print_release"):
        parts.append("LoCG first-print date available")
    if proposal.get("known_first_print_release"):
        parts.append("known_first_print registry")
    before = proposal.get("before_issue") or {}
    vu = (proposal.get("variant_updates") or [{}])[0]
    if vu.get("printing_release_date") and before.get("release_date") == vu["printing_release_date"]:
        parts.append("issue release_date matches Lunar reprint InStoreDate")
    if vu.get("printing_foc_date") and before.get("foc_date") == vu["printing_foc_date"]:
        parts.append("issue foc_date matches Lunar reprint FOCDate")
    if proposal.get("confidence") == "HIGH" and not parts:
        parts.append("reprint Lunar SKU linked; HIGH classifier")
    return "; ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    engine = get_engine()
    report: dict = {"issue_ids": SAMPLE_ISSUE_IDS, "dry_run": not args.apply, "samples": [], "applied": [], "verify": []}

    lunar_by_code: dict = {}

    with Session(engine) as session:
        lunar_by_code = load_lunar_reprint_index(session)
        for iid in SAMPLE_ISSUE_IDS:
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
                lunar_by_code=lunar_by_code,
            )
            if not proposal:
                continue
            vu = proposal["variant_updates"][0] if proposal.get("variant_updates") else {}
            report["samples"].append(
                {
                    "issue_id": iid,
                    "title": proposal["title"],
                    "publisher": proposal["publisher"],
                    "series": proposal["series"],
                    "variant_sku": vu.get("source_item_code"),
                    "detected_printing_badge": proposal.get("proposed_ui_badge_after_backfill"),
                    "current_issue_dates": proposal.get("before_issue"),
                    "proposed_issue_dates": proposal.get("after_issue"),
                    "proposed_variant_printing_dates": {
                        "printing_foc_date": vu.get("printing_foc_date"),
                        "printing_release_date": vu.get("printing_release_date"),
                        "printing_number": vu.get("printing_number"),
                        "printing_kind": vu.get("printing_kind"),
                    },
                    "confidence": proposal.get("confidence"),
                    "confidence_reason": confidence_reason(proposal),
                }
            )

    if args.apply:
        try:
            with Session(engine) as session:
                with session.begin():
                    lunar = load_lunar_reprint_index(session)
                    for sample in report["samples"]:
                        iid = sample["issue_id"]
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
                        if not proposal or proposal.get("confidence") != "HIGH":
                            continue
                        result = apply_proposal(session, proposal, force=False)
                        report["applied"].append({"issue_id": iid, **result})
        except Exception as exc:
            report["fatal_error"] = str(exc)
            print(json.dumps(report, indent=2, default=str))
            return 1

    with Session(engine) as session:
        ctx = build_recommendation_decision_context(session, owner_user_id=1)
        for sample in report["samples"]:
            iid = sample["issue_id"]
            issue = session.get(ReleaseIssue, iid)
            if issue is None:
                continue
            variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == iid)).all())
            sched = resolve_printing_schedule(issue, variants)
            title = sample["title"]
            rec = session.exec(
                select(CrossSystemRecommendation)
                .where(CrossSystemRecommendation.owner_user_id == 1)
                .where(CrossSystemRecommendation.title == title)
                .order_by(CrossSystemRecommendation.created_at.desc())
            ).first()
            badge = None
            if rec:
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
                badge = d.printing_badge.label if d.printing_badge else None
            orig = issue.original_release_date.isoformat() if issue.original_release_date else None
            report["verify"].append(
                {
                    "issue_id": iid,
                    "issue_release_date": issue.release_date.isoformat() if issue.release_date else None,
                    "issue_foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
                    "original_release_date": orig,
                    "schedule_badge": sched.printing_badge,
                    "decision_badge": badge,
                    "first_print_preserved": orig is None or orig == (issue.release_date.isoformat() if issue.release_date else None),
                }
            )

    text = json.dumps(report, indent=2, default=str)
    out = getattr(args, "json_out", "") or ""
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
