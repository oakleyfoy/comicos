"""add P62 buy queue intelligence tables

Revision ID: 20260606_0221
Revises: 20260605_0220
Create Date: 2026-06-06 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260606_0221"
down_revision = "20260605_0220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buy_queue_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buy_queue_snapshot_owner_date", "buy_queue_snapshot", ["owner_user_id", "snapshot_date", "id"])
    op.create_index(op.f("ix_buy_queue_snapshot_owner_user_id"), "buy_queue_snapshot", ["owner_user_id"])

    op.create_table(
        "buy_queue_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("spec_score", sa.Float(), nullable=False),
        sa.Column("buy_reason", sa.Text(), nullable=False),
        sa.Column("quantity_recommended", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["buy_queue_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_buy_queue_item_snapshot_priority", "buy_queue_item", ["snapshot_id", "priority_score", "id"])
    op.create_index("ix_buy_queue_item_owner_status", "buy_queue_item", ["owner_user_id", "status", "id"])
    op.create_index(op.f("ix_buy_queue_item_snapshot_id"), "buy_queue_item", ["snapshot_id"])
    op.create_index(op.f("ix_buy_queue_item_owner_user_id"), "buy_queue_item", ["owner_user_id"])


def downgrade() -> None:
    op.drop_table("buy_queue_item")
    op.drop_table("buy_queue_snapshot")
