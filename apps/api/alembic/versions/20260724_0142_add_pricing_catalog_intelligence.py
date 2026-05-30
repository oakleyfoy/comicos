"""add pricing catalog intelligence

Revision ID: 20260724_0142
Revises: 20260723_0141
Create Date: 2026-07-24 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260724_0142"
down_revision = "20260723_0141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_uuid", sa.String(length=64), nullable=False),
        sa.Column("agent_execution_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("inventory_title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("recommendation_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_execution_id"], ["agent_execution.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_uuid", name="uq_intelligence_recommendation_uuid"),
    )
    op.create_index(
        "ix_intelligence_recommendation_type_created",
        "intelligence_recommendation",
        ["recommendation_type", "created_at", "id"],
    )
    op.create_index(
        "ix_intelligence_recommendation_status_created",
        "intelligence_recommendation",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_intelligence_recommendation_confidence",
        "intelligence_recommendation",
        ["confidence_score", "id"],
    )
    op.create_index(
        "ix_intelligence_recommendation_opportunity",
        "intelligence_recommendation",
        ["opportunity_score", "id"],
    )
    op.create_index(
        "ix_intelligence_recommendation_priority",
        "intelligence_recommendation",
        ["priority_score", "id"],
    )
    op.create_index(
        "ix_intelligence_recommendation_execution_created",
        "intelligence_recommendation",
        ["agent_execution_id", "created_at", "id"],
    )
    op.create_index(op.f("ix_intelligence_recommendation_recommendation_uuid"), "intelligence_recommendation", ["recommendation_uuid"])
    op.create_index(op.f("ix_intelligence_recommendation_agent_execution_id"), "intelligence_recommendation", ["agent_execution_id"])
    op.create_index(op.f("ix_intelligence_recommendation_recommendation_type"), "intelligence_recommendation", ["recommendation_type"])
    op.create_index(op.f("ix_intelligence_recommendation_status"), "intelligence_recommendation", ["status"])
    op.create_index(op.f("ix_intelligence_recommendation_inventory_copy_id"), "intelligence_recommendation", ["inventory_copy_id"])

    op.create_table(
        "intelligence_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("evidence_source", sa.String(length=160), nullable=False),
        sa.Column("evidence_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["intelligence_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_evidence_recommendation_created",
        "intelligence_evidence",
        ["recommendation_id", "created_at", "id"],
    )
    op.create_index(
        "ix_intelligence_evidence_type_score",
        "intelligence_evidence",
        ["evidence_type", "evidence_score", "id"],
    )
    op.create_index(op.f("ix_intelligence_evidence_recommendation_id"), "intelligence_evidence", ["recommendation_id"])
    op.create_index(op.f("ix_intelligence_evidence_evidence_type"), "intelligence_evidence", ["evidence_type"])

    op.create_table(
        "intelligence_recommendation_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["recommendation_id"], ["intelligence_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_review_recommendation_reviewed",
        "intelligence_recommendation_review",
        ["recommendation_id", "reviewed_at", "id"],
    )
    op.create_index(
        "ix_intelligence_review_status_reviewed",
        "intelligence_recommendation_review",
        ["review_status", "reviewed_at", "id"],
    )
    op.create_index(op.f("ix_intelligence_recommendation_review_recommendation_id"), "intelligence_recommendation_review", ["recommendation_id"])
    op.create_index(op.f("ix_intelligence_recommendation_review_review_status"), "intelligence_recommendation_review", ["review_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_intelligence_recommendation_review_review_status"), table_name="intelligence_recommendation_review")
    op.drop_index(op.f("ix_intelligence_recommendation_review_recommendation_id"), table_name="intelligence_recommendation_review")
    op.drop_index("ix_intelligence_review_status_reviewed", table_name="intelligence_recommendation_review")
    op.drop_index("ix_intelligence_review_recommendation_reviewed", table_name="intelligence_recommendation_review")
    op.drop_table("intelligence_recommendation_review")

    op.drop_index(op.f("ix_intelligence_evidence_evidence_type"), table_name="intelligence_evidence")
    op.drop_index(op.f("ix_intelligence_evidence_recommendation_id"), table_name="intelligence_evidence")
    op.drop_index("ix_intelligence_evidence_type_score", table_name="intelligence_evidence")
    op.drop_index("ix_intelligence_evidence_recommendation_created", table_name="intelligence_evidence")
    op.drop_table("intelligence_evidence")

    op.drop_index(op.f("ix_intelligence_recommendation_inventory_copy_id"), table_name="intelligence_recommendation")
    op.drop_index(op.f("ix_intelligence_recommendation_status"), table_name="intelligence_recommendation")
    op.drop_index(op.f("ix_intelligence_recommendation_recommendation_type"), table_name="intelligence_recommendation")
    op.drop_index(op.f("ix_intelligence_recommendation_agent_execution_id"), table_name="intelligence_recommendation")
    op.drop_index(op.f("ix_intelligence_recommendation_recommendation_uuid"), table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_execution_created", table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_priority", table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_opportunity", table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_confidence", table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_status_created", table_name="intelligence_recommendation")
    op.drop_index("ix_intelligence_recommendation_type_created", table_name="intelligence_recommendation")
    op.drop_table("intelligence_recommendation")
