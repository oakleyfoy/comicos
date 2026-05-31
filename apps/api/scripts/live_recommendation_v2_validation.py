"""Live Recommendation V2 validation for owner catalog (e.g. owner 40 Lunar)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.recommendation_v2_comparison import compare_v1_v2_recommendations  # noqa: E402
from app.services.recommendation_v2_dashboard import build_recommendations_v2_dashboard  # noqa: E402
from app.services.recommendation_v2_engine import generate_recommendations_v2  # noqa: E402
from app.services.spec_recommendation_agent import run_spec_recommendations  # noqa: E402
from app.services.spec_scoring_agent import run_spec_scoring  # noqa: E402


def _print_bucket(title: str, items: list) -> None:
    print(f"\n=== {title} ({len(items)}) ===")
    for row in items[:25]:
        print(f"  {row.total_score:5.1f}  {row.series_name} #{row.issue_number}  [{row.recommendation_type}]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-user-id", type=int, default=40)
    args = parser.parse_args()
    owner_user_id = args.owner_user_id

    with Session(get_engine()) as session:
        run_spec_scoring(session, owner_user_id=owner_user_id)
        run_spec_recommendations(session, owner_user_id=owner_user_id)
        run = generate_recommendations_v2(session, owner_user_id=owner_user_id)
        dashboard = build_recommendations_v2_dashboard(session, owner_user_id=owner_user_id, limit=25)
        comparison = compare_v1_v2_recommendations(session, owner_user_id=owner_user_id, limit=100)

    print(json.dumps({"run_uuid": run.run_uuid, "recommendations_created": run.recommendations_created}, indent=2))
    _print_bucket("Must Buy", dashboard.must_buy)
    _print_bucket("Strong Buy", dashboard.strong_buy)
    _print_bucket("Watch", dashboard.watch)
    _print_bucket("Pass", dashboard.pass_tier)
    _print_bucket("Investment #1", dashboard.investment_number_ones)
    _print_bucket("Start Run", dashboard.start_run)
    _print_bucket("Key Issues", dashboard.key_issues)
    _print_bucket("Ratio Variants", dashboard.ratio_variants)
    _print_bucket("User Preference Matches", dashboard.user_preference_matches)
    print(f"\nV1 vs V2: moved_up={comparison.books_moved_up} moved_down={comparison.books_moved_down}")
    for entry in comparison.entries[:10]:
        print(f"  rank {entry.v1_rank}->{entry.v2_rank}  {entry.series_name} #{entry.issue_number}: {entry.movement_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
