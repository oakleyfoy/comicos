"""Measure release index match rate and enrichment coverage for an owner."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _db_host(url: str) -> str | None:
    m = re.search(r"@([^:/]+)", url)
    return m.group(1).lower() if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrichment coverage and title index audit.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1
    host = _db_host(database_url) or ""
    if args.production and host in {"localhost", "127.0.0.1"}:
        print("error: production mode requires non-localhost DATABASE_URL", file=sys.stderr)
        return 1

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    scripts_dir = os.path.join(ROOT, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from sqlmodel import Session

    from app.db.session import get_engine
    from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
    from app.services.cross_system_recommendation_engine import (
        build_cross_system_candidates,
        generate_cross_system_recommendations,
    )
    from app.services.recommendation_catalog_quality import build_forward_release_title_index
    from app.services.recommendation_enrichment_diagnostics import (
        build_enrichment_diagnostics_for_candidate,
        title_index_resolution_stats,
    )
    from app.services.recommendation_forward_window import _key_signals_by_issue
    from app.services.recommendation_title_normalize import normalize_recommendation_title_key
    from owner_lookup import resolve_owner_user_id

    limit = min(max(int(args.limit), 1), 500)

    with Session(get_engine()) as session:
        owner_user_id = resolve_owner_user_id(session, args.email)
        if args.rebuild:
            generate_cross_system_recommendations(
                session,
                owner_user_id=owner_user_id,
                refresh_upstream=True,
            )

        release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
        candidates = build_cross_system_candidates(
            session,
            owner_user_id=owner_user_id,
            refresh_upstream=False,
        )
        resolution = title_index_resolution_stats(candidates=candidates, release_index=release_index)

        issue_ids = []
        for cand in candidates:
            from app.services.recommendation_title_index import resolve_release_pair

            pair = resolve_release_pair(cand.title, release_index)
            if pair and pair[0].id:
                issue_ids.append(int(pair[0].id))
        issue_ids = list(dict.fromkeys(issue_ids))
        signals_by_issue = _key_signals_by_issue(session, issue_ids=issue_ids)
        from sqlmodel import select

        from app.models.release_intelligence import ReleaseVariant

        variants_by_issue: dict[int, list] = {}
        if issue_ids:
            for variant in session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all():
                variants_by_issue.setdefault(int(variant.issue_id), []).append(variant)

        cand_by_key = {
            (c.recommendation_type.strip().upper(), c.title_key): c for c in candidates
        }

        items, _total = list_latest_cross_system_recommendations(
            session,
            owner_user_id=owner_user_id,
            limit=limit,
            offset=0,
        )

        records: list[dict] = []
        creator_reasons: Counter[str] = Counter()
        milestone_reasons: Counter[str] = Counter()
        for item in items:
            norm_key = (
                item.recommendation_type.strip().upper(),
                normalize_recommendation_title_key(item.title),
            )
            cand = cand_by_key.get(norm_key)
            bd = getattr(cand, "collector_score_breakdown", None) if cand else None
            diag = build_enrichment_diagnostics_for_candidate(
                session,
                title=item.title,
                recommendation_type=item.recommendation_type,
                rationale=item.rationale or (cand.rationale if cand else ""),
                release_index=release_index,
                variants_by_issue=variants_by_issue,
                collector_score_breakdown=bd,
            )
            if diag.creator_zero_reason:
                creator_reasons[diag.creator_zero_reason] += 1
            if diag.milestone_zero_reason:
                milestone_reasons[diag.milestone_zero_reason] += 1
            records.append(
                {
                    "title": diag.title,
                    "recommendation_type": diag.recommendation_type,
                    "title_key": diag.title_key,
                    "release_index_key": diag.release_index_key,
                    "release_matched": diag.release_matched,
                    "enrichment_attempted": diag.enrichment_attempted,
                    "enrichment_successful": diag.enrichment_successful,
                    "creator_score": diag.creator_score,
                    "milestone_score": diag.milestone_score,
                    "creator_zero_reason": diag.creator_zero_reason,
                    "milestone_zero_reason": diag.milestone_zero_reason,
                }
            )

        enrichment_success = sum(1 for r in records if r["enrichment_successful"])
        enrichment_attempted = sum(1 for r in records if r["enrichment_attempted"])
        report = {
            "owner_user_id": owner_user_id,
            "email": args.email,
            "title_index_resolution": resolution,
            "listed_recommendations": len(records),
            "enrichment_attempted_count": enrichment_attempted,
            "enrichment_successful_count": enrichment_success,
            "enrichment_success_rate_pct": round(
                100.0 * enrichment_success / len(records), 2
            )
            if records
            else 0.0,
            "creator_score_zero_reasons": dict(creator_reasons),
            "milestone_score_zero_reasons": dict(milestone_reasons),
            "recommendation_records": records,
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
