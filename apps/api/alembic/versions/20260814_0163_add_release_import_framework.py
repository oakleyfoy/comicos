"""add release import framework

Revision ID: 20260814_0163
Revises: 20260813_0162
Create Date: 2026-08-14 02:02:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260814_0163"
down_revision = "20260813_0162"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "release_import_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("import_uuid", sa.String(length=64), nullable=False),
        sa.Column("import_type", sa.String(length=16), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_import_run_owner_user_id", "release_import_run", ["owner_user_id"])
    op.create_index("ix_release_import_run_import_uuid", "release_import_run", ["import_uuid"])
    op.create_index("ix_release_import_run_import_type", "release_import_run", ["import_type"])
    op.create_index("ix_release_import_run_status", "release_import_run", ["status"])
    op.create_index("ix_release_import_run_created_at", "release_import_run", ["created_at"])
    op.create_index("ix_release_import_run_owner_created", "release_import_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_release_import_run_owner_status", "release_import_run", ["owner_user_id", "status", "id"])

    op.create_table(
        "release_import_file",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=260), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["release_import_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_import_file_import_run_id", "release_import_file", ["import_run_id"])
    op.create_index("ix_release_import_file_file_type", "release_import_file", ["file_type"])
    op.create_index("ix_release_import_file_run_created", "release_import_file", ["import_run_id", "created_at", "id"])

    op.create_table(
        "release_import_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column("record_identifier", sa.String(length=260), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["release_import_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_import_error_import_run_id", "release_import_error", ["import_run_id"])
    op.create_index("ix_release_import_error_error_code", "release_import_error", ["error_code"])
    op.create_index("ix_release_import_error_run_created", "release_import_error", ["import_run_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_release_import_error_run_created", table_name="release_import_error")
    op.drop_index("ix_release_import_error_error_code", table_name="release_import_error")
    op.drop_index("ix_release_import_error_import_run_id", table_name="release_import_error")
    op.drop_table("release_import_error")
    op.drop_index("ix_release_import_file_run_created", table_name="release_import_file")
    op.drop_index("ix_release_import_file_file_type", table_name="release_import_file")
    op.drop_index("ix_release_import_file_import_run_id", table_name="release_import_file")
    op.drop_table("release_import_file")
    op.drop_index("ix_release_import_run_owner_status", table_name="release_import_run")
    op.drop_index("ix_release_import_run_owner_created", table_name="release_import_run")
    op.drop_index("ix_release_import_run_created_at", table_name="release_import_run")
    op.drop_index("ix_release_import_run_status", table_name="release_import_run")
    op.drop_index("ix_release_import_run_import_type", table_name="release_import_run")
    op.drop_index("ix_release_import_run_import_uuid", table_name="release_import_run")
    op.drop_index("ix_release_import_run_owner_user_id", table_name="release_import_run")
    op.drop_table("release_import_run")
