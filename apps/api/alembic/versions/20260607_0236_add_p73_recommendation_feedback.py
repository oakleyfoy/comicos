"""add P73 recommendation outcome tracking

Revision ID: 20260607_0236
Revises: 20260607_0235
Create Date: 2026-06-07 02:36:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0236"
down_revision = "20260607_0235"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p73_recommendation_outcome",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("series", sa.String(length=256), nullable=False),
        sa.Column("issue", sa.String(length=32), nullable=False),
        sa.Column("variant", sa.String(length=128), nullable=False),
        sa.Column("recommendation_type", sa.String(length=32), nullable=False),
        sa.Column("recommendation_category", sa.String(length=32), nullable=False),
        sa.Column("created_date", sa.Date(), nullable=False),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("attribution_outcome", sa.String(length=32), nullable=True),
        sa.Column("attribution_accurate", sa.Boolean(), nullable=True),
        sa.Column("source_table", sa.String(length=64), nullable=True),
        sa.Column("source_row_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_outcome_owner_created",
        "p73_recommendation_outcome",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_p73_rec_outcome_rec_id",
        "p73_recommendation_outcome",
        ["owner_user_id", "recommendation_id", "id"],
    )

    op.create_table(
        "p73_recommendation_action_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_source", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["outcome_id"], ["p73_recommendation_outcome.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_event_outcome_created",
        "p73_recommendation_action_event",
        ["outcome_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p73_rec_event_outcome_created", table_name="p73_recommendation_action_event")
    op.drop_table("p73_recommendation_action_event")
    op.drop_index("ix_p73_rec_outcome_rec_id", table_name="p73_recommendation_outcome")
    op.drop_index("ix_p73_rec_outcome_owner_created", table_name="p73_recommendation_outcome")
    op.drop_table("p73_recommendation_outcome")
