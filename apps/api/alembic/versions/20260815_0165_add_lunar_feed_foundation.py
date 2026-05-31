"""add lunar feed foundation

Revision ID: 20260815_0165
Revises: 20260814_0163
Create Date: 2026-08-15 02:02:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260815_0165"
down_revision = "20260814_0163"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lunar_feed_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("run_uuid", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("file_period", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("foc_alerts_created", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_feed_run_owner_user_id", "lunar_feed_run", ["owner_user_id"])
    op.create_index("ix_lunar_feed_run_run_uuid", "lunar_feed_run", ["run_uuid"])
    op.create_index("ix_lunar_feed_run_source_type", "lunar_feed_run", ["source_type"])
    op.create_index("ix_lunar_feed_run_file_period", "lunar_feed_run", ["file_period"])
    op.create_index("ix_lunar_feed_run_status", "lunar_feed_run", ["status"])
    op.create_index("ix_lunar_feed_run_created_at", "lunar_feed_run", ["created_at"])
    op.create_index("ix_lunar_feed_run_owner_created", "lunar_feed_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_lunar_feed_run_owner_status", "lunar_feed_run", ["owner_user_id", "status", "id"])

    op.create_table(
        "lunar_feed_raw_row",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("row_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feed_run_id"], ["lunar_feed_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_feed_raw_row_feed_run_id", "lunar_feed_raw_row", ["feed_run_id"])
    op.create_index("ix_lunar_feed_raw_row_product_code", "lunar_feed_raw_row", ["product_code"])
    op.create_index("ix_lunar_feed_raw_row_run", "lunar_feed_raw_row", ["feed_run_id", "id"])

    op.create_table(
        "lunar_feed_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("record_identifier", sa.String(length=260), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feed_run_id"], ["lunar_feed_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_feed_error_feed_run_id", "lunar_feed_error", ["feed_run_id"])
    op.create_index("ix_lunar_feed_error_error_code", "lunar_feed_error", ["error_code"])
    op.create_index("ix_lunar_feed_error_run", "lunar_feed_error", ["feed_run_id", "created_at", "id"])

    op.create_table(
        "lunar_foc_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("feed_run_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("alert_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["feed_run_id"], ["lunar_feed_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_foc_alert_owner_user_id", "lunar_foc_alert", ["owner_user_id"])
    op.create_index("ix_lunar_foc_alert_feed_run_id", "lunar_foc_alert", ["feed_run_id"])
    op.create_index("ix_lunar_foc_alert_product_code", "lunar_foc_alert", ["product_code"])
    op.create_index("ix_lunar_foc_alert_foc_date", "lunar_foc_alert", ["foc_date"])
    op.create_index("ix_lunar_foc_alert_alert_status", "lunar_foc_alert", ["alert_status"])
    op.create_index("ix_lunar_foc_alert_owner_foc", "lunar_foc_alert", ["owner_user_id", "foc_date", "id"])


def downgrade() -> None:
    op.drop_index("ix_lunar_foc_alert_owner_foc", table_name="lunar_foc_alert")
    op.drop_index("ix_lunar_foc_alert_alert_status", table_name="lunar_foc_alert")
    op.drop_index("ix_lunar_foc_alert_foc_date", table_name="lunar_foc_alert")
    op.drop_index("ix_lunar_foc_alert_product_code", table_name="lunar_foc_alert")
    op.drop_index("ix_lunar_foc_alert_feed_run_id", table_name="lunar_foc_alert")
    op.drop_index("ix_lunar_foc_alert_owner_user_id", table_name="lunar_foc_alert")
    op.drop_table("lunar_foc_alert")
    op.drop_index("ix_lunar_feed_error_run", table_name="lunar_feed_error")
    op.drop_index("ix_lunar_feed_error_error_code", table_name="lunar_feed_error")
    op.drop_index("ix_lunar_feed_error_feed_run_id", table_name="lunar_feed_error")
    op.drop_table("lunar_feed_error")
    op.drop_index("ix_lunar_feed_raw_row_run", table_name="lunar_feed_raw_row")
    op.drop_index("ix_lunar_feed_raw_row_product_code", table_name="lunar_feed_raw_row")
    op.drop_index("ix_lunar_feed_raw_row_feed_run_id", table_name="lunar_feed_raw_row")
    op.drop_table("lunar_feed_raw_row")
    op.drop_index("ix_lunar_feed_run_owner_status", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_owner_created", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_created_at", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_status", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_file_period", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_source_type", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_run_uuid", table_name="lunar_feed_run")
    op.drop_index("ix_lunar_feed_run_owner_user_id", table_name="lunar_feed_run")
    op.drop_table("lunar_feed_run")
