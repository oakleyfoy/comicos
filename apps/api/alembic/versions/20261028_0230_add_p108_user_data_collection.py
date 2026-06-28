"""P108 user data collections (real + test clones)."""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "20261028_0230"
down_revision = "20261027_0229"
branch_labels = None
depends_on = None

_COLLECTION_TABLES: tuple[tuple[str, str], ...] = (
    ("customer_order", "user_id"),
    ("inventory_copy", "user_id"),
    ("photo_import_session", "user_id"),
    ("retailer_sync_run", "owner_user_id"),
    ("retailer_order_snapshot", "owner_user_id"),
    ("pull_list", "owner_user_id"),
    ("daily_collector_action", "owner_user_id"),
    ("inventory_scan_session", "user_id"),
    ("intake_session", "user_id"),
    ("p80_mobile_scan", "owner_user_id"),
    ("recommendation_run_v2", "owner_user_id"),
    ("recommendation_score_v2", "owner_user_id"),
)


def _scoped_tables_present(conn) -> list[tuple[str, str]]:
    """Only alter tables that exist (production may have dropped legacy customer_order)."""
    names = set(sa.inspect(conn).get_table_names())
    return [(table, owner_col) for table, owner_col in _COLLECTION_TABLES if table in names]


def upgrade() -> None:
    op.create_table(
        "user_data_collection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("collection_type", sa.String(length=16), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_collection_id", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_collection_id"], ["user_data_collection.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_data_collection_owner_user_id", "user_data_collection", ["owner_user_id"])
    op.create_index("ix_user_data_collection_collection_type", "user_data_collection", ["collection_type"])
    op.create_index(
        "ix_user_data_collection_owner_active",
        "user_data_collection",
        ["owner_user_id", "deleted_at", "id"],
    )
    op.create_index(
        "ix_user_data_collection_owner_type",
        "user_data_collection",
        ["owner_user_id", "collection_type", "id"],
    )

    op.add_column(
        "user",
        sa.Column("active_collection_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_active_collection_id",
        "user",
        "user_data_collection",
        ["active_collection_id"],
        ["id"],
    )
    op.create_index("ix_user_active_collection_id", "user", ["active_collection_id"])

    conn = op.get_bind()
    scoped_tables = _scoped_tables_present(conn)

    for table, _ in scoped_tables:
        op.add_column(table, sa.Column("collection_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_collection_id",
            table,
            "user_data_collection",
            ["collection_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_collection_id", table, ["collection_id"])

    users = conn.execute(sa.text("SELECT id FROM user")).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    for (user_id,) in users:
        result = conn.execute(
            sa.text(
                """
                INSERT INTO user_data_collection
                    (owner_user_id, name, collection_type, is_default, created_at, updated_at)
                VALUES
                    (:uid, 'Oakley Real Collection', 'real', 1, :now, :now)
                """
            ),
            {"uid": user_id, "now": now},
        )
        collection_id = int(
            conn.execute(
                sa.text(
                    "SELECT id FROM user_data_collection WHERE owner_user_id = :uid ORDER BY id DESC LIMIT 1"
                ),
                {"uid": user_id},
            ).scalar_one()
        )
        for table, owner_col in scoped_tables:
            conn.execute(
                sa.text(f"UPDATE {table} SET collection_id = :cid WHERE {owner_col} = :uid"),
                {"cid": collection_id, "uid": user_id},
            )
        conn.execute(
            sa.text("UPDATE user SET active_collection_id = :cid WHERE id = :uid"),
            {"cid": collection_id, "uid": user_id},
        )


def downgrade() -> None:
    op.drop_constraint("fk_user_active_collection_id", "user", type_="foreignkey")
    op.drop_index("ix_user_active_collection_id", table_name="user")
    op.drop_column("user", "active_collection_id")

    conn = op.get_bind()
    scoped_tables = _scoped_tables_present(conn)
    for table, _ in reversed(scoped_tables):
        op.drop_index(f"ix_{table}_collection_id", table_name=table)
        op.drop_constraint(f"fk_{table}_collection_id", table, type_="foreignkey")
        op.drop_column(table, "collection_id")

    op.drop_index("ix_user_data_collection_owner_type", table_name="user_data_collection")
    op.drop_index("ix_user_data_collection_owner_active", table_name="user_data_collection")
    op.drop_index("ix_user_data_collection_collection_type", table_name="user_data_collection")
    op.drop_index("ix_user_data_collection_owner_user_id", table_name="user_data_collection")
    op.drop_table("user_data_collection")
