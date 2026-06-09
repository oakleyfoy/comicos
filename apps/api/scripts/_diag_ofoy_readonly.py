"""One-off read-only diagnostic for ofoy@att.net — delete after use if desired."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse


def _normalize_database_url_env() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgresql://"):
        os.environ["DATABASE_URL"] = "postgresql+pg8000://" + url[len("postgresql://") :]


_normalize_database_url_env()

from sqlalchemy import inspect as sa_inspect, text
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import User

EMAIL = "ofoy@att.net"


def main() -> None:
    engine = get_engine()
    settings = get_settings()
    url = settings.database_url
    parsed = urlparse(url.replace("postgresql+pg8000", "postgresql").replace("postgresql+psycopg2", "postgresql"))
    host = parsed.hostname or "(local)"
    dbname = (parsed.path or "").lstrip("/") or "(none)"
    if url.startswith("sqlite"):
        db_kind = "SQLite"
    elif "postgres" in url:
        db_kind = "Postgres"
    else:
        db_kind = "other"

    with Session(engine) as session:
        rev = session.exec(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        alembic_rev = rev[0] if rev else None

        user = session.exec(select(User).where(User.email == EMAIL)).first()
        uid = int(user.id) if user and user.id else None
        user_created = getattr(user, "created_at", None) if user else None

        def cnt_sql(table: str, where: str = "1=1", params: dict | None = None):
            try:
                if not sa_inspect(engine).has_table(table):
                    return "N/A (no table)"
                q = f"SELECT COUNT(*) FROM {table} WHERE {where}"
                row = session.execute(text(q), params or {}).one()
                return int(row[0])
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                return f"ERR: {type(exc).__name__}"

        def cnt_owner(table: str, owner_col: str = "owner_user_id"):
            if uid is None:
                return 0
            return cnt_sql(table, f"{owner_col} = :uid", {"uid": uid})

        def cnt_user_id(table: str, col: str = "user_id"):
            if uid is None:
                return 0
            return cnt_sql(table, f"{col} = :uid", {"uid": uid})

        counts = [
            ("inventory copies", cnt_user_id("inventory_copy")),
            ("orders", cnt_user_id("customer_order")),
            ("imports (draft_import)", cnt_user_id("draft_import")),
            (
                "confirmed imports (draft_import)",
                cnt_sql("draft_import", "user_id = :uid AND status = 'CONFIRMED'", {"uid": uid}) if uid else 0,
            ),
            ("marketplace opportunities", cnt_owner("p82_marketplace_acquisition_opportunity")),
            ("marketplace listings", cnt_owner("p88_marketplace_listing")),
            ("marketplace alerts", cnt_owner("p88_marketplace_alert")),
            ("sell candidates", cnt_owner("p89_sell_candidate")),
            ("market price snapshots", cnt_owner("p89_market_price_snapshot")),
            ("listing drafts", cnt_owner("p89_listing_draft")),
            ("managed listings", cnt_owner("p89_managed_listing")),
            ("collector alerts", cnt_owner("p90_collector_alert")),
            ("advisor snapshots", cnt_owner("p90_collector_advisor_snapshot")),
            ("FMV V2 snapshots", cnt_owner("p90_fmv_snapshot")),
            ("future pull list items", cnt_owner("p81_future_pull_list_item")),
            ("discovery alerts", cnt_owner("p81_discovery_alert")),
            ("collection gaps", cnt_owner("collection_gap")),
        ]

        inv_rows = session.exec(
            text(
                """
                SELECT u.id, u.email, COUNT(ic.id) AS inventory_count
                FROM "user" u
                LEFT JOIN inventory_copy ic ON ic.user_id = u.id
                GROUP BY u.id, u.email
                ORDER BY inventory_count DESC, u.id ASC
                LIMIT 20
                """
            )
        ).all()

        def extra_counts(user_id: int) -> tuple:
            return (
                cnt_sql("customer_order", "user_id = :uid", {"uid": user_id}),
                cnt_sql("p82_marketplace_acquisition_opportunity", "owner_user_id = :uid", {"uid": user_id}),
                cnt_sql("p89_sell_candidate", "owner_user_id = :uid", {"uid": user_id}),
                cnt_sql("p90_collector_advisor_snapshot", "owner_user_id = :uid", {"uid": user_id}),
            )

        orphan_specs = [
            ("inventory_copy", "user_id"),
            ("customer_order", "user_id"),
            ("p82_marketplace_acquisition_opportunity", "owner_user_id"),
            ("p89_sell_candidate", "owner_user_id"),
            ("p89_market_price_snapshot", "owner_user_id"),
            ("p89_listing_draft", "owner_user_id"),
            ("p89_managed_listing", "owner_user_id"),
            ("p90_collector_alert", "owner_user_id"),
            ("p90_collector_advisor_snapshot", "owner_user_id"),
        ]
        orphans: list[tuple[str, int]] = []
        for table, col in orphan_specs:
            if not sa_inspect(engine).has_table(table):
                continue
            n = int(
                session.exec(
                    text(
                        f"""
                        SELECT COUNT(*) FROM {table} t
                        WHERE t.{col} IS NOT NULL
                          AND NOT EXISTS (SELECT 1 FROM "user" u WHERE u.id = t.{col})
                        """
                    )
                ).one()[0]
            )
            if n:
                orphans.append((table, n))

        # user with max inventory who is not uid 41
        top_data_user = None
        for row in inv_rows:
            if int(row[2]) > 0 and int(row[0]) != (uid or -1):
                top_data_user = (int(row[0]), str(row[1]), int(row[2]))
                break

    print("DATABASE:")
    print(f"  host: {host}")
    print(f"  database: {dbname}")
    print(f"  kind: {db_kind}")
    print(f"  alembic_revision: {alembic_rev}")
    print(f"  url_redacted: {re.sub(r':[^:@/]+@', ':***@', url.split('?')[0][:140])}")
    print()
    print("USER:")
    print(f"  email: {EMAIL}")
    print(f"  id: {uid} (local dev expectation: 41; production historical: 1)")
    print(f"  created_at: {user_created}")
    print()
    print("COUNTS:")
    for name, c in counts:
        print(f"  {name} | {c}")
    print()
    print("TOP USERS BY DATA:")
    print("  user_id | email | inventory_count | order_count | marketplace_opportunity_count | sell_candidate_count | advisor_snapshot_count")
    for row in inv_rows:
        user_id, email, inv = int(row[0]), str(row[1]), int(row[2])
        o, m, s, a = extra_counts(user_id)
        print(f"  {user_id} | {email} | {inv} | {o} | {m} | {s} | {a}")
    print()
    print("ORPHANS (owner not in user):")
    if orphans:
        for t, n in orphans:
            print(f"  {t} | {n}")
    else:
        print("  none")
    print()
    print("ROOT CAUSE HINT:")
    inv_count = counts[0][1] if isinstance(counts[0][1], int) else 0
    if top_data_user and inv_count == 0:
        print(f"  Data may live under user {top_data_user[0]} ({top_data_user[1]}) with {top_data_user[2]} inventory copies")
    elif inv_count == 0:
        print("  No inventory for this user; top users also mostly empty in this DB")


if __name__ == "__main__":
    main()
