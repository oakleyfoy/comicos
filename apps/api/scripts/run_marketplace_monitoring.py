"""Production/cron entry: P88 marketplace monitoring."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="P88 marketplace saved-search monitoring")
    parser.add_argument("--dry-run", action="store_true", help="Search only; do not write listings or alerts.")
    parser.add_argument("--email", required=True, help="Owner user email")
    parser.add_argument("--saved-search-id", type=int, default=None, help="Run a single saved search id")
    parser.add_argument("--limit", type=int, default=None, help="Max active saved searches to run")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1

    from sqlmodel import Session

    from app.db.session import get_engine
    from app.services.marketplace.marketplace_monitoring_service import run_active_saved_searches
    from scripts.owner_lookup import resolve_owner_user_id

    engine = get_engine()
    with Session(engine) as session:
        try:
            owner_user_id = resolve_owner_user_id(session, args.email)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            print(f"dry-run: owner_user_id={owner_user_id} saved_search_id={args.saved_search_id}", flush=True)

        summary = run_active_saved_searches(
            session,
            owner_user_id=owner_user_id,
            saved_search_id=args.saved_search_id,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            session.commit()

    payload = {
        "searches_run": summary.searches_run,
        "listings_found": summary.listings_found,
        "new_listings": summary.new_listings,
        "price_drops": summary.price_drops,
        "below_fmv_alerts": summary.below_fmv_alerts,
        "watchlist_matches": summary.watchlist_matches,
        "errors": summary.errors,
    }
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
