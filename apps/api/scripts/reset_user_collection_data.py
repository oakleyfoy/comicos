"""Delete one user's collection/order/import data (never users or retailer credentials)."""

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
from app.services.user_collection_reset import reset_user_collection_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset collection, orders, and import data for a single ComicOS user.",
    )
    parser.add_argument("--email", required=True, help="User email address (required).")
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help="Perform deletes. Without this flag the script only prints a dry-run summary.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Required when APP_ENV=production.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    app_env = (settings.app_env or "development").strip().lower()
    if app_env == "production" and not args.allow_production:
        print(
            "error: refusing to run in production without --allow-production",
            file=sys.stderr,
        )
        return 1

    database_url = (settings.database_url or "").strip()
    if not database_url:
        print("error: DATABASE_URL is missing", file=sys.stderr)
        return 1

    execute = bool(args.confirm_delete)
    mode = "EXECUTE" if execute else "DRY RUN"
    print(f"ComicOS user collection reset ({mode})")
    print(f"APP_ENV: {app_env}")
    print(f"Database: {database_url}")
    print(f"User email: {args.email}")
    print("Preserved: user account, retailer credentials, catalog, release intelligence, watchlists")
    print()

    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == args.email)).first()
        if user is None:
            print(f"error: no user with email {args.email!r}", file=sys.stderr)
            return 1
        result = reset_user_collection_data(session, user=user, execute=execute)

    print()
    print(f"User id {result.user_id} ({result.email})")
    print(f"Tables with matching rows: {len(result.table_summaries)}")
    print(f"Total rows {'to delete' if result.dry_run else 'deleted'}: {result.total_rows}")
    if result.dry_run:
        print()
        print("Dry run only. Re-run with --confirm-delete to delete rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
