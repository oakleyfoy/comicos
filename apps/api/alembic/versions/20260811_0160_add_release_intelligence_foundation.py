"""add release intelligence foundation

Revision ID: 20260811_0160
Revises: 20260810_0159
Create Date: 2026-08-11 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260811_0160"
down_revision = "20260810_0159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "release_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("series_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "publisher",
            "series_name",
            "series_type",
            name="uq_release_series_owner_identity",
        ),
    )
    op.create_index("ix_release_series_owner_user_id", "release_series", ["owner_user_id"])
    op.create_index("ix_release_series_publisher", "release_series", ["publisher"])
    op.create_index("ix_release_series_series_name", "release_series", ["series_name"])
    op.create_index("ix_release_series_status", "release_series", ["status"])
    op.create_index("ix_release_series_created_at", "release_series", ["created_at"])
    op.create_index("ix_release_series_owner_created", "release_series", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_release_series_publisher_series", "release_series", ["publisher", "series_name", "id"])

    op.create_table(
        "release_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_uuid", sa.String(length=64), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("cover_price", sa.Float(), nullable=False),
        sa.Column("release_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["series_id"], ["release_series.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "release_uuid", name="uq_release_issue_owner_uuid"),
    )
    op.create_index("ix_release_issue_owner_user_id", "release_issue", ["owner_user_id"])
    op.create_index("ix_release_issue_release_uuid", "release_issue", ["release_uuid"])
    op.create_index("ix_release_issue_series_id", "release_issue", ["series_id"])
    op.create_index("ix_release_issue_issue_number", "release_issue", ["issue_number"])
    op.create_index("ix_release_issue_foc_date", "release_issue", ["foc_date"])
    op.create_index("ix_release_issue_release_date", "release_issue", ["release_date"])
    op.create_index("ix_release_issue_release_status", "release_issue", ["release_status"])
    op.create_index("ix_release_issue_created_at", "release_issue", ["created_at"])
    op.create_index("ix_release_issue_owner_release_date", "release_issue", ["owner_user_id", "release_date", "id"])
    op.create_index("ix_release_issue_owner_foc_date", "release_issue", ["owner_user_id", "foc_date", "id"])
    op.create_index("ix_release_issue_series_number", "release_issue", ["series_id", "issue_number", "id"])

    op.create_table(
        "release_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("variant_name", sa.String(length=160), nullable=False),
        sa.Column("ratio_value", sa.Integer(), nullable=True),
        sa.Column("variant_type", sa.String(length=48), nullable=False),
        sa.Column("cover_artist", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id", "variant_name", "variant_type", name="uq_release_variant_identity"),
    )
    op.create_index("ix_release_variant_issue_id", "release_variant", ["issue_id"])
    op.create_index("ix_release_variant_ratio_value", "release_variant", ["ratio_value"])
    op.create_index("ix_release_variant_variant_type", "release_variant", ["variant_type"])
    op.create_index("ix_release_variant_created_at", "release_variant", ["created_at"])
    op.create_index("ix_release_variant_issue_created", "release_variant", ["issue_id", "created_at", "id"])

    op.create_table(
        "release_key_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("signal_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_key_signal_owner_user_id", "release_key_signal", ["owner_user_id"])
    op.create_index("ix_release_key_signal_issue_id", "release_key_signal", ["issue_id"])
    op.create_index("ix_release_key_signal_signal_type", "release_key_signal", ["signal_type"])
    op.create_index("ix_release_key_signal_created_at", "release_key_signal", ["created_at"])
    op.create_index("ix_release_key_signal_issue_type", "release_key_signal", ["issue_id", "signal_type", "id"])
    op.create_index("ix_release_key_signal_owner_created", "release_key_signal", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "release_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_release_agent_execution_uuid"),
    )
    op.create_index("ix_release_agent_execution_owner_user_id", "release_agent_execution", ["owner_user_id"])
    op.create_index("ix_release_agent_execution_agent_code", "release_agent_execution", ["agent_code"])
    op.create_index("ix_release_agent_execution_execution_uuid", "release_agent_execution", ["execution_uuid"])
    op.create_index("ix_release_agent_execution_status", "release_agent_execution", ["status"])
    op.create_index("ix_release_agent_execution_created_at", "release_agent_execution", ["created_at"])
    op.create_index("ix_release_agent_execution_owner_started", "release_agent_execution", ["owner_user_id", "started_at", "id"])
    op.create_index("ix_release_agent_execution_agent_started", "release_agent_execution", ["agent_code", "started_at", "id"])


def downgrade() -> None:
    op.drop_table("release_agent_execution")
    op.drop_table("release_key_signal")
    op.drop_table("release_variant")
    op.drop_table("release_issue")
    op.drop_table("release_series")
