"""P90-02 FMV V2 snapshot runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.fmv_v2_service import generate_fmv_v2_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description="P90 FMV Intelligence V2 runner")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing")
    parser.add_argument("--email", type=str, default="", help="Limit to owner email")
    parser.add_argument("--limit", type=int, default=0, help="Max owners to process (0 = all)")
    args = parser.parse_args()

    engine = get_engine()
    with Session(engine) as session:
        query = select(User)
        if args.email.strip():
            query = query.where(User.email == args.email.strip())
        users = list(session.exec(query).all())
        if args.limit > 0:
            users = users[: args.limit]
        if not users:
            print("No users matched.")
            return 1
        for user in users:
            assert user.id is not None
            summary = generate_fmv_v2_snapshots(
                session,
                owner_user_id=int(user.id),
                dry_run=bool(args.dry_run),
            )
            if not args.dry_run:
                session.commit()
            print(
                f"owner={user.email} dry_run={args.dry_run} "
                f"snapshots_created={summary['snapshots_created']} "
                f"snapshots_updated={summary.get('snapshots_updated', 0)} "
                f"high_confidence={summary['high_confidence']} "
                f"medium_confidence={summary['medium_confidence']} "
                f"low_confidence={summary['low_confidence']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
