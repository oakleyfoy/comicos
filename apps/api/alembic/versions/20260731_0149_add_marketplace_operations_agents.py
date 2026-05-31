"""add marketplace operations agents

Revision ID: 20260731_0149
Revises: 20260730_0148
Create Date: 2026-07-31 01:49:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260731_0149"
down_revision = "20260730_0148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("agent_execution_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("recommendation_status", sa.String(length=24), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_execution_id"], ["agent_execution.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listing.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_account.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplace_definition.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_marketplace_recommendation_uuid"),
    )
    op.create_index("ix_marketplace_recommendation_recommendation_uuid", "marketplace_recommendation", ["recommendation_uuid"])
    op.create_index("ix_marketplace_recommendation_recommendation_type", "marketplace_recommendation", ["recommendation_type"])
    op.create_index("ix_marketplace_recommendation_recommendation_status", "marketplace_recommendation", ["recommendation_status"])
    op.create_index("ix_marketplace_recommendation_listing_id", "marketplace_recommendation", ["listing_id"])
    op.create_index("ix_marketplace_recommendation_inventory_copy_id", "marketplace_recommendation", ["inventory_copy_id"])
    op.create_index("ix_marketplace_recommendation_marketplace_id", "marketplace_recommendation", ["marketplace_id"])
    op.create_index("ix_marketplace_recommendation_created_at", "marketplace_recommendation", ["created_at"])

    op.create_table(
        "marketplace_recommendation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("evidence_source", sa.String(length=160), nullable=False),
        sa.Column("evidence_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["marketplace_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketplace_recommendation_evidence_recommendation_id",
        "marketplace_recommendation_evidence",
        ["recommendation_id"],
    )
    op.create_index("ix_marketplace_recommendation_evidence_created_at", "marketplace_recommendation_evidence", ["created_at"])

    op.create_table(
        "marketplace_recommendation_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["recommendation_id"], ["marketplace_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketplace_recommendation_review_recommendation_id",
        "marketplace_recommendation_review",
        ["recommendation_id"],
    )
    op.create_index("ix_marketplace_recommendation_review_reviewed_at", "marketplace_recommendation_review", ["reviewed_at"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_recommendation_review_reviewed_at", table_name="marketplace_recommendation_review")
    op.drop_index("ix_marketplace_recommendation_review_recommendation_id", table_name="marketplace_recommendation_review")
    op.drop_table("marketplace_recommendation_review")

    op.drop_index("ix_marketplace_recommendation_evidence_created_at", table_name="marketplace_recommendation_evidence")
    op.drop_index("ix_marketplace_recommendation_evidence_recommendation_id", table_name="marketplace_recommendation_evidence")
    op.drop_table("marketplace_recommendation_evidence")

    op.drop_index("ix_marketplace_recommendation_created_at", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_marketplace_id", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_inventory_copy_id", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_listing_id", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_recommendation_status", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_recommendation_type", table_name="marketplace_recommendation")
    op.drop_index("ix_marketplace_recommendation_recommendation_uuid", table_name="marketplace_recommendation")
    op.drop_table("marketplace_recommendation")
