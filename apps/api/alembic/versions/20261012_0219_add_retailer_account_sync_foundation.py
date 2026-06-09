"""add retailer account sync foundation

Revision ID: 20261012_0219
Revises: 20261012_0218
Create Date: 2026-10-12 02:19:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0219"
down_revision = "20261012_0218"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retailer_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("retailer", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("username", sa.String(length=320), nullable=False),
        sa.Column("encrypted_password", sa.String(length=4096), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retailer_account_owner_user_id", "retailer_account", ["owner_user_id"])
    op.create_index("ix_retailer_account_retailer", "retailer_account", ["retailer"])
    op.create_index("ix_retailer_account_status", "retailer_account", ["status"])

    op.create_table(
        "retailer_sync_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("retailer_account_id", sa.Integer(), nullable=False),
        sa.Column("retailer", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orders_seen", sa.Integer(), nullable=False),
        sa.Column("orders_imported", sa.Integer(), nullable=False),
        sa.Column("items_seen", sa.Integer(), nullable=False),
        sa.Column("items_imported", sa.Integer(), nullable=False),
        sa.Column("items_updated", sa.Integer(), nullable=False),
        sa.Column("errors_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["retailer_account_id"], ["retailer_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retailer_sync_run_owner_user_id", "retailer_sync_run", ["owner_user_id"])
    op.create_index("ix_retailer_sync_run_retailer_account_id", "retailer_sync_run", ["retailer_account_id"])
    op.create_index("ix_retailer_sync_run_retailer", "retailer_sync_run", ["retailer"])
    op.create_index("ix_retailer_sync_run_status", "retailer_sync_run", ["status"])

    op.create_table(
        "retailer_order_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("retailer_account_id", sa.Integer(), nullable=False),
        sa.Column("retailer", sa.String(length=32), nullable=False),
        sa.Column("retailer_order_number", sa.String(length=128), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("order_status", sa.String(length=128), nullable=True),
        sa.Column("order_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("raw_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["retailer_account_id"], ["retailer_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "retailer",
            "retailer_order_number",
            name="uq_retailer_order_snapshot_identity",
        ),
    )
    op.create_index("ix_retailer_order_snapshot_owner_user_id", "retailer_order_snapshot", ["owner_user_id"])
    op.create_index("ix_retailer_order_snapshot_retailer_account_id", "retailer_order_snapshot", ["retailer_account_id"])
    op.create_index("ix_retailer_order_snapshot_retailer", "retailer_order_snapshot", ["retailer"])
    op.create_index("ix_retailer_order_snapshot_retailer_order_number", "retailer_order_snapshot", ["retailer_order_number"])

    op.create_table(
        "retailer_order_item_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("retailer_order_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("retailer", sa.String(length=32), nullable=False),
        sa.Column("retailer_order_number", sa.String(length=128), nullable=False),
        sa.Column("retailer_item_id", sa.String(length=128), nullable=True),
        sa.Column("product_url", sa.String(length=2048), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("cover_name", sa.String(length=255), nullable=True),
        sa.Column("variant_type", sa.String(length=255), nullable=True),
        sa.Column("cover_artist", sa.String(length=200), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("item_status", sa.String(length=128), nullable=True),
        sa.Column("shipped_qty", sa.Integer(), nullable=True),
        sa.Column("backordered_qty", sa.Integer(), nullable=True),
        sa.Column("unavailable_qty", sa.Integer(), nullable=True),
        sa.Column("returned_qty", sa.Integer(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("raw_item_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["retailer_order_snapshot_id"], ["retailer_order_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retailer_order_item_snapshot_owner_user_id", "retailer_order_item_snapshot", ["owner_user_id"])
    op.create_index(
        "ix_retailer_order_item_snapshot_retailer_order_snapshot_id",
        "retailer_order_item_snapshot",
        ["retailer_order_snapshot_id"],
    )
    op.create_index("ix_retailer_order_item_snapshot_retailer", "retailer_order_item_snapshot", ["retailer"])
    op.create_index(
        "ix_retailer_order_item_snapshot_retailer_order_number",
        "retailer_order_item_snapshot",
        ["retailer_order_number"],
    )
    op.create_index("ix_retailer_order_item_snapshot_retailer_item_id", "retailer_order_item_snapshot", ["retailer_item_id"])


def downgrade() -> None:
    op.drop_index("ix_retailer_order_item_snapshot_retailer_item_id", table_name="retailer_order_item_snapshot")
    op.drop_index("ix_retailer_order_item_snapshot_retailer_order_number", table_name="retailer_order_item_snapshot")
    op.drop_index("ix_retailer_order_item_snapshot_retailer", table_name="retailer_order_item_snapshot")
    op.drop_index(
        "ix_retailer_order_item_snapshot_retailer_order_snapshot_id",
        table_name="retailer_order_item_snapshot",
    )
    op.drop_index("ix_retailer_order_item_snapshot_owner_user_id", table_name="retailer_order_item_snapshot")
    op.drop_table("retailer_order_item_snapshot")

    op.drop_index("ix_retailer_order_snapshot_retailer_order_number", table_name="retailer_order_snapshot")
    op.drop_index("ix_retailer_order_snapshot_retailer", table_name="retailer_order_snapshot")
    op.drop_index("ix_retailer_order_snapshot_retailer_account_id", table_name="retailer_order_snapshot")
    op.drop_index("ix_retailer_order_snapshot_owner_user_id", table_name="retailer_order_snapshot")
    op.drop_table("retailer_order_snapshot")

    op.drop_index("ix_retailer_sync_run_status", table_name="retailer_sync_run")
    op.drop_index("ix_retailer_sync_run_retailer", table_name="retailer_sync_run")
    op.drop_index("ix_retailer_sync_run_retailer_account_id", table_name="retailer_sync_run")
    op.drop_index("ix_retailer_sync_run_owner_user_id", table_name="retailer_sync_run")
    op.drop_table("retailer_sync_run")

    op.drop_index("ix_retailer_account_status", table_name="retailer_account")
    op.drop_index("ix_retailer_account_retailer", table_name="retailer_account")
    op.drop_index("ix_retailer_account_owner_user_id", table_name="retailer_account")
    op.drop_table("retailer_account")
