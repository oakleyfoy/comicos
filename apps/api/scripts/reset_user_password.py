"""Reset a ComicOS user password (requires DATABASE_URL)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session, select

from app.core.security import get_password_hash
from app.db.session import get_engine
from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset password for an existing user by email.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True, help="New password (min 8 characters per API rules).")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("error: password must be at least 8 characters", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == args.email)).first()
        if user is None:
            print(f"error: no user with email {args.email!r}", file=sys.stderr)
            return 1
        user.password_hash = get_password_hash(args.password)
        session.add(user)
        session.commit()
        print(f"ok: password updated for user_id={user.id} email={args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
