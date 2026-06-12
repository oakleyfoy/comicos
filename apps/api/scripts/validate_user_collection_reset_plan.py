"""Validate FK-safe delete plan for collection reset (dry-run only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import User
from app.services.user_collection_reset import build_reset_delete_plan
from app.services.user_collection_reset_plan import CollectionResetPlanError
from app.services.user_collection_reset_scope import build_user_collection_scope


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print and validate collection reset delete plan for a user.")
    parser.add_argument("--email", required=True, help="User email address.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    if (settings.app_env or "development").strip().lower() == "production":
        print("error: validation script is dev-only; refuse to run in production", file=sys.stderr)
        return 1

    try:
        plan = build_reset_delete_plan(validate=True)
    except CollectionResetPlanError as exc:
        print("Collection reset plan validation failed:", file=sys.stderr)
        for issue in exc.issues:
            print(f"  [{issue.kind}] {issue.message}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == args.email)).first()
        if user is None:
            print(f"error: no user with email {args.email!r}", file=sys.stderr)
            return 1
        scope = build_user_collection_scope(session, user_id=int(user.id))
        from sqlalchemy import func, select as sa_select

        engine = session.get_bind()
        with engine.connect() as connection:
            print(f"User {user.id} ({user.email})")
            print(f"Plan steps: {len(plan)}")
            print()
            print("order\ttable\tscoped_rows\tscope_reason\tdepends_on")
            total = 0
            for step in plan:
                count = int(
                    connection.execute(
                        sa_select(func.count()).select_from(step.model.__table__).where(step.predicate(scope))
                    ).scalar_one()
                )
                total += count
                depends = ",".join(step.depends_on) if step.depends_on else "-"
                print(f"{step.order}\t{step.table_name}\t{count}\t{step.scope_reason}\t{depends}")
            print()
            print(f"Total scoped rows: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
