"""add lunar scheduler

Revision ID: 20260816_0166
Revises: 20260815_0165
Create Date: 2026-08-16 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260816_0166"
down_revision = "20260815_0165"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lunar_schedule_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_type", sa.String(length=24), nullable=False),
        sa.Column("schedule_time", sa.String(length=8), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_imported_file_name", sa.String(length=260), nullable=False),
        sa.Column("last_imported_file_period", sa.String(length=32), nullable=False),
        sa.Column("last_imported_checksum", sa.String(length=64), nullable=False),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_schedule_config_owner", "lunar_schedule_config", ["owner_user_id"], unique=True)
    op.create_index("ix_lunar_schedule_config_next_run", "lunar_schedule_config", ["next_run_at", "enabled", "id"])

    op.create_table(
        "lunar_scheduled_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("run_uuid", sa.String(length=64), nullable=False),
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=True),
        sa.Column("file_period", sa.String(length=32), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("records_imported", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_scheduled_run_owner_created", "lunar_scheduled_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_lunar_scheduled_run_owner_status", "lunar_scheduled_run", ["owner_user_id", "status", "id"])
    op.create_index(op.f("ix_lunar_scheduled_run_run_uuid"), "lunar_scheduled_run", ["run_uuid"], unique=False)
    op.create_index(op.f("ix_lunar_scheduled_run_trigger_type"), "lunar_scheduled_run", ["trigger_type"], unique=False)
    op.create_index(op.f("ix_lunar_scheduled_run_status"), "lunar_scheduled_run", ["status"], unique=False)
    op.create_index(op.f("ix_lunar_scheduled_run_created_at"), "lunar_scheduled_run", ["created_at"], unique=False)

    op.create_table(
        "lunar_scheduled_run_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scheduled_run_id", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scheduled_run_id"], ["lunar_scheduled_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lunar_scheduled_run_error_run", "lunar_scheduled_run_error", ["scheduled_run_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_lunar_scheduled_run_error_run", table_name="lunar_scheduled_run_error")
    op.drop_table("lunar_scheduled_run_error")
    op.drop_index(op.f("ix_lunar_scheduled_run_created_at"), table_name="lunar_scheduled_run")
    op.drop_index(op.f("ix_lunar_scheduled_run_status"), table_name="lunar_scheduled_run")
    op.drop_index(op.f("ix_lunar_scheduled_run_trigger_type"), table_name="lunar_scheduled_run")
    op.drop_index(op.f("ix_lunar_scheduled_run_run_uuid"), table_name="lunar_scheduled_run")
    op.drop_index("ix_lunar_scheduled_run_owner_status", table_name="lunar_scheduled_run")
    op.drop_index("ix_lunar_scheduled_run_owner_created", table_name="lunar_scheduled_run")
    op.drop_table("lunar_scheduled_run")
    op.drop_index("ix_lunar_schedule_config_next_run", table_name="lunar_schedule_config")
    op.drop_index("ix_lunar_schedule_config_owner", table_name="lunar_schedule_config")
    op.drop_table("lunar_schedule_config")
