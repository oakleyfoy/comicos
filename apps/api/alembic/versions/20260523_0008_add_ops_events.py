"""Add operations event log.

Revision ID: 20260523_0008
Revises: 20260523_0007
Create Date: 2026-05-23 16:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0008"
down_revision: str | None = "20260523_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ops_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(length=255), nullable=True),
        sa.Column("queue_name", sa.String(length=100), nullable=True),
        sa.Column("gmail_account_id", sa.Integer(), nullable=True),
        sa.Column("draft_import_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_import_id"], ["draft_import.id"]),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_account.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ops_event_draft_import_id"),
        "ops_event",
        ["draft_import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ops_event_event_type"),
        "ops_event",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ops_event_external_message_id"),
        "ops_event",
        ["external_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ops_event_gmail_account_id"),
        "ops_event",
        ["gmail_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_ops_event_job_id"), "ops_event", ["job_id"], unique=False)
    op.create_index(op.f("ix_ops_event_order_id"), "ops_event", ["order_id"], unique=False)
    op.create_index(op.f("ix_ops_event_status"), "ops_event", ["status"], unique=False)
    op.create_index(op.f("ix_ops_event_user_id"), "ops_event", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ops_event_user_id"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_status"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_order_id"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_job_id"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_gmail_account_id"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_external_message_id"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_event_type"), table_name="ops_event")
    op.drop_index(op.f("ix_ops_event_draft_import_id"), table_name="ops_event")
    op.drop_table("ops_event")
