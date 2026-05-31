"""Seed manual collector preferences for owner 40 (P51-04B)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.owner_manual_preference_seed import seed_manual_preferences_for_owner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-user-id", type=int, default=40)
    args = parser.parse_args()
    with Session(get_engine()) as session:
        count = seed_manual_preferences_for_owner(session, owner_user_id=args.owner_user_id)
    print(f"seeded_or_refreshed_preferences={count} owner_user_id={args.owner_user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
