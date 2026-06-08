"""P90-09A backfill import draft release lifecycle enrichment.

Usage (from apps/api):
  python scripts/backfill_import_release_lifecycle.py --dry-run
  python scripts/backfill_import_release_lifecycle.py --email user@example.com --dry-run
  python scripts/backfill_import_release_lifecycle.py --email user@example.com
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.asset_ledger import DraftImport
from app.schemas.ai import ParseOrderResponse
from app.services.import_release_lifecycle_service import apply_release_lifecycle_to_parse_order


def _resolve_user_id(session: Session, email: str | None) -> int | None:
    if not email:
        return None
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or user.id is None:
        raise SystemExit(f"No user found for email {email!r}")
    return user.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill import draft release lifecycle fields.")
    parser.add_argument("--email", default=None, help="Limit to drafts owned by this user email.")
    parser.add_argument("--dry-run", action="store_true", help="Compute only; do not write to DB.")
    args = parser.parse_args()

    engine = get_engine()
    summary: Counter[str] = Counter()
    unmatched_examples: list[str] = []
    with Session(engine) as session:
        user_id = _resolve_user_id(session, args.email)
        stmt = select(DraftImport)
        if user_id is not None:
            stmt = stmt.where(DraftImport.user_id == user_id)
        drafts = session.exec(stmt).all()

        for draft in drafts:
            summary["scanned"] += 1
            parsed = ParseOrderResponse.model_validate(draft.parsed_payload_json)
            enriched = apply_release_lifecycle_to_parse_order(
                parsed,
                session=session,
                owner_user_id=draft.user_id,
            )
            score_total = 0
            score_count = 0
            for item in enriched.items:
                status = item.release_lifecycle_status or "UNKNOWN"
                summary[status.lower()] += 1
                if item.catalog_match_matched:
                    summary["catalog_matched"] += 1
                elif item.catalog_match_possible:
                    summary["possible_match"] += 1
                else:
                    summary["catalog_unmatched"] += 1
                    if len(unmatched_examples) < 5:
                        unmatched_examples.append(
                            f"{item.publisher} | {item.title} #{item.issue_number}"
                        )
                if item.catalog_match_score is not None:
                    score_total += item.catalog_match_score
                    score_count += 1

            if score_count:
                summary["avg_score_total"] += score_total
                summary["avg_score_count"] += score_count

            if args.dry_run:
                continue

            draft.parsed_payload_json = enriched.model_dump(mode="json")
            summary["updated"] += 1
            session.add(draft)

        if not args.dry_run:
            session.commit()

    avg_score = 0.0
    if summary["avg_score_count"]:
        avg_score = summary["avg_score_total"] / summary["avg_score_count"]

    print(
        "summary:",
        f"scanned={summary['scanned']}",
        f"updated={summary['updated']}",
        f"preorder={summary['preorder']}",
        f"released_not_received={summary['released_not_received']}",
        f"overdue={summary['overdue']}",
        f"received={summary['received']}",
        f"unknown={summary['unknown']}",
        f"catalog_matched={summary['catalog_matched']}",
        f"catalog_unmatched={summary['catalog_unmatched']}",
        f"possible_match={summary['possible_match']}",
        f"avg_score={avg_score:.1f}",
        sep="\n  ",
    )
    examples = unmatched_examples
    if examples:
        print("top_unmatched_examples:")
        for line in examples:
            print(f"  - {line}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
