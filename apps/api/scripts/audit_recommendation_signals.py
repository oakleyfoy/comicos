"""Audit top recommendations: signal contribution and ratio discipline."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit recommendation signals for an owner.")
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

    from sqlalchemy import select
    from sqlmodel import Session

    from app.db.session import get_engine
    from owner_lookup import resolve_owner_user_id as _resolve_owner_user_id
    from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
    from app.services.cross_system_recommendation_engine import (
        build_cross_system_candidates,
        generate_cross_system_recommendations,
    )
    from app.services.recommendation_decision_engine import (
        build_recommendation_decision_context,
        decision_for_cross_system,
    )
    from app.services.collector_ratio_strategy import parse_ratio_from_label

    limit = min(max(int(args.limit), 1), 500)

    with Session(get_engine()) as session:
        try:
            owner_user_id = _resolve_owner_user_id(session, args.email)
        except LookupError:
            print(f"error: no user for {args.email}", file=sys.stderr)
            return 1
        except (TypeError, ValueError) as exc:
            print(f"error: could not resolve user id for {args.email}: {exc}", file=sys.stderr)
            return 1

        if args.rebuild:
            generate_cross_system_recommendations(session, owner_user_id=owner_user_id, refresh_upstream=True)

        items, _total = list_latest_cross_system_recommendations(
            session,
            owner_user_id=owner_user_id,
            limit=limit,
            offset=0,
        )
        ctx = build_recommendation_decision_context(session, owner_user_id=owner_user_id)
        candidates = build_cross_system_candidates(session, owner_user_id=owner_user_id, refresh_upstream=False)
        cand_by_title = {(c.recommendation_type.upper(), c.title_key): c for c in candidates}

        rows: list[dict] = []
        for item in items:
            decision = decision_for_cross_system(
                recommendation_type=item.recommendation_type,
                title=item.title,
                priority_score=float(item.priority_score),
                confidence_score=float(item.confidence_score),
                rationale=item.rationale,
                source_systems=item.source_systems,
                estimated_value=item.estimated_value,
                session=session,
                owner_user_id=owner_user_id,
                ctx=ctx,
            )
            bd = None
            key = (item.recommendation_type.strip().upper(), item.title.strip().lower())
            cand = cand_by_title.get(key)
            if cand is not None:
                bd = getattr(cand, "collector_score_breakdown", None)

            matrix = decision.signal_matrix.model_dump() if decision.signal_matrix else {}
            rows.append(
                {
                    "title": item.title,
                    "priority": float(item.priority_score),
                    "confidence": float(item.confidence_score),
                    "action": decision.action,
                    "final_score": bd.final_score if bd else None,
                    "collector_boost": bd.ranking_boost if bd else None,
                    "milestone_score": bd.milestone_score if bd else 0.0,
                    "creator_score": bd.creator_score if bd else 0.0,
                    "homage_score": bd.homage_score if bd else 0.0,
                    "franchise_score": bd.franchise_score if bd else 0.0,
                    "publisher_score": bd.publisher_score if bd else 0.0,
                    "audience_score": bd.audience_score if bd else 0.0,
                    "market_demand_score": bd.historical_demand_score if bd else 0.0,
                    "continuity_score": bd.continuity_score if bd else 0.0,
                    "signal_flags": matrix,
                    "cover_purchase_plan": [p.model_dump() for p in decision.cover_purchase_plan],
                    "suppressed_variants": [s.model_dump() for s in decision.suppressed_variants],
                }
            )

        def _top(field: str, n: int = 25) -> list[dict]:
            ranked = sorted(rows, key=lambda r: float(r.get(field) or 0.0), reverse=True)
            return [
                {"title": r["title"], "score": r.get(field), "priority": r["priority"]}
                for r in ranked[:n]
                if float(r.get(field) or 0.0) > 0
            ]

        high_ratio_recommended = 0
        high_ratio_suppressed = 0
        for r in rows:
            for p in r.get("cover_purchase_plan") or []:
                ratio = parse_ratio_from_label(str(p.get("cover_label", "")))
                if ratio is not None and ratio >= 50 and int(p.get("recommended_quantity") or 0) > 0:
                    high_ratio_recommended += 1
            high_ratio_suppressed += len(r.get("suppressed_variants") or [])

        summary = {
            "owner_user_id": owner_user_id,
            "email": args.email,
            "listed_count": len(rows),
            "creator_score_gt_0": sum(1 for r in rows if float(r.get("creator_score") or 0) > 0),
            "milestone_score_gt_0": sum(1 for r in rows if float(r.get("milestone_score") or 0) > 0),
            "homage_score_gt_0": sum(1 for r in rows if float(r.get("homage_score") or 0) > 0),
            "market_demand_score_gt_0": sum(1 for r in rows if float(r.get("market_demand_score") or 0) > 0),
            "high_ratio_recommended": high_ratio_recommended,
            "high_ratio_suppressed": high_ratio_suppressed,
            "top_25_by_creator_score": _top("creator_score"),
            "top_25_by_milestone_score": _top("milestone_score"),
            "top_25_by_homage_score": _top("homage_score"),
            "top_25_by_collector_boost": _top("collector_boost"),
        }

        report = {"summary": summary, "items": rows}
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
