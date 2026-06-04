"""Diagnose creator/milestone/homage/market-demand signal buckets for recommendations."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _db_host(url: str) -> str | None:
    m = re.search(r"@([^:/]+)", url)
    return m.group(1).lower() if m else None


def _attach_performance(report: dict, caches) -> dict:
    report["performance"] = caches.performance_payload()
    return report


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
    parser.add_argument(
        "--perf-audit",
        action="store_true",
        help="Emit detailed performance_audit JSON (step timings, query counts)",
    )
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
    from app.services.recommendation_catalog_quality import build_forward_release_title_index
    from app.services.recommendation_signal_bucket_diagnostic import (
        aggregate_bucket_counts,
        diagnose_title_signal_buckets,
    )
    from app.services.recommendation_signal_bucket_fast import (
        SignalBucketDiagnosticCaches,
        fetch_stored_recommendation_by_title,
        fetch_top_stored_recommendations,
    )
    from app.services.recommendation_signal_bucket_perf import (
        DiagnosticPerfRecorder,
        attach_query_counter,
    )
    from owner_lookup import resolve_owner_user_id

    top_n = min(max(int(args.top), 1), 50) if args.top else None
    perf = DiagnosticPerfRecorder() if args.perf_audit else None
    caches = SignalBucketDiagnosticCaches()
    engine = get_engine()
    if perf is not None:
        attach_query_counter(engine, perf)

    with Session(engine) as session:
        owner_user_id = resolve_owner_user_id(session, args.email)

        if args.title:
            rec, _cand = fetch_stored_recommendation_by_title(
                session,
                owner_user_id=owner_user_id,
                title_query=args.title,
                caches=caches,
            )
            release_index: dict = {}
            report = diagnose_title_signal_buckets(
                session,
                owner_user_id=owner_user_id,
                title_query=args.title,
                release_index=release_index,
                recommendation_row=rec,
                rationale=rec.get("rationale", "") if rec else "",
                include_books=args.include_books,
                strict_catalog_title=args.strict_title,
                perf=perf,
                caches=caches,
                use_title_index_resolve=False,
            )
            _attach_performance(report, caches)
            if perf is not None:
                report["performance_audit"] = perf.build_report()
            print(json.dumps(report, indent=2))
            return 0

        rec_limit = top_n or 20
        release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
        caches.title_index_build_count = 1
        stored = fetch_top_stored_recommendations(
            session,
            owner_user_id=owner_user_id,
            limit=rec_limit,
            caches=caches,
        )
        reports: list[dict] = []
        for rec in stored:
            reports.append(
                diagnose_title_signal_buckets(
                    session,
                    owner_user_id=owner_user_id,
                    title_query=rec["title"],
                    release_index=release_index,
                    recommendation_row=rec,
                    rationale=rec.get("rationale", "") or "",
                    include_books=args.include_books,
                    strict_catalog_title=None,
                    perf=None,
                    caches=caches,
                    use_title_index_resolve=True,
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
        _attach_performance(payload, caches)
        if perf is not None:
            payload["performance_audit"] = perf.build_report()
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
