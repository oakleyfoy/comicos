"""Diagnose creator/milestone/homage/market-demand signal buckets for recommendations."""

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


def _find_recommendation(items: list, title_query: str) -> dict | None:
    needle = title_query.strip().lower()
    for item in items:
        if needle in (item.title or "").lower():
            return {
                "found": True,
                "title": item.title,
                "recommendation_type": item.recommendation_type,
                "priority_score": float(item.priority_score),
                "confidence_score": float(item.confidence_score),
                "recommendation_rank": int(item.recommendation_rank),
                "source_systems": list(item.source_systems or []),
                "rationale": item.rationale,
            }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Signal bucket diagnostic for recommendations.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--title", default=None, help="Single title substring to diagnose")
    parser.add_argument(
        "--strict-title",
        default=None,
        help="Require close catalog match (series + issue); avoids loose TP/HC resolution",
    )
    parser.add_argument(
        "--include-books",
        action="store_true",
        help="Include trade paperback / hardcover catalog rows in selection",
    )
    parser.add_argument("--top", type=int, default=None, help="Diagnose top N latest recommendations")
    args = parser.parse_args()

    if not args.title and not args.top:
        print("error: provide --title or --top", file=sys.stderr)
        return 1

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
    from app.services.recommendation_catalog_quality import build_forward_release_title_index
    from app.services.recommendation_signal_bucket_diagnostic import (
        aggregate_bucket_counts,
        diagnose_title_signal_buckets,
    )
    from owner_lookup import resolve_owner_user_id

    top_n = min(max(int(args.top), 1), 50) if args.top else None

    with Session(get_engine()) as session:
        owner_user_id = resolve_owner_user_id(session, args.email)
        release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)

        if args.title:
            items, _ = list_latest_cross_system_recommendations(
                session,
                owner_user_id=owner_user_id,
                limit=250,
                offset=0,
            )
            rec = _find_recommendation(items, args.title)
            report = diagnose_title_signal_buckets(
                session,
                owner_user_id=owner_user_id,
                title_query=args.title,
                release_index=release_index,
                recommendation_row=rec,
                rationale=rec.get("rationale", "") if rec else "",
                include_books=args.include_books,
                strict_catalog_title=args.strict_title,
            )
            print(json.dumps(report, indent=2))
            return 0

        items, _ = list_latest_cross_system_recommendations(
            session,
            owner_user_id=owner_user_id,
            limit=top_n or 20,
            offset=0,
        )
        reports: list[dict] = []
        for item in items:
            reports.append(
                diagnose_title_signal_buckets(
                    session,
                    owner_user_id=owner_user_id,
                    title_query=item.title,
                    release_index=release_index,
                    recommendation_row={
                        "found": True,
                        "title": item.title,
                        "recommendation_type": item.recommendation_type,
                        "priority_score": float(item.priority_score),
                        "confidence_score": float(item.confidence_score),
                        "recommendation_rank": int(item.recommendation_rank),
                        "source_systems": list(item.source_systems or []),
                        "rationale": item.rationale,
                    },
                    rationale=item.rationale or "",
                    include_books=args.include_books,
                    strict_catalog_title=None,
                )
            )
        payload = {
            "mode": "top_n",
            "owner_user_id": owner_user_id,
            "email": args.email,
            "count": len(reports),
            "aggregate_bucket_counts": aggregate_bucket_counts(reports),
            "items": reports,
        }
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
