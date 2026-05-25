"""P35-01 market source import runs.

Revision ID: 20260525_0048
Revises: 20260525_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0048"
down_revision: str | None = "20260525_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_source_import_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_source_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("imported_records", sa.Integer(), nullable=False),
        sa.Column("failed_records", sa.Integer(), nullable=False),
        sa.Column("skipped_records", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["market_source_id"], ["market_source.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_source_import_run_market_source_id"),
        "market_source_import_run",
        ["market_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_source_import_run_created_by_user_id"),
        "market_source_import_run",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_market_source_import_run_status"), "market_source_import_run", ["status"], unique=False)
    op.create_index(
        op.f("ix_market_source_import_run_created_at"),
        "market_source_import_run",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "market_source_import_run_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["market_source_import_run.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_source_import_run_event_import_run_id"),
        "market_source_import_run_event",
        ["import_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_source_import_run_event_event_type"),
        "market_source_import_run_event",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_source_import_run_event_new_status"),
        "market_source_import_run_event",
        ["new_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_source_import_run_event_created_at"),
        "market_source_import_run_event",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_source_import_run_event_created_at"), table_name="market_source_import_run_event")
    op.drop_index(op.f("ix_market_source_import_run_event_new_status"), table_name="market_source_import_run_event")
    op.drop_index(op.f("ix_market_source_import_run_event_event_type"), table_name="market_source_import_run_event")
    op.drop_index(op.f("ix_market_source_import_run_event_import_run_id"), table_name="market_source_import_run_event")
    op.drop_table("market_source_import_run_event")

    op.drop_index(op.f("ix_market_source_import_run_created_at"), table_name="market_source_import_run")
    op.drop_index(op.f("ix_market_source_import_run_status"), table_name="market_source_import_run")
    op.drop_index(op.f("ix_market_source_import_run_created_by_user_id"), table_name="market_source_import_run")
    op.drop_index(op.f("ix_market_source_import_run_market_source_id"), table_name="market_source_import_run")
    op.drop_table("market_source_import_run")
