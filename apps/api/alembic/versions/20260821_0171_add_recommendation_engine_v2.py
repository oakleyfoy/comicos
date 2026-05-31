"""add recommendation engine v2 (P51-04)

Revision ID: 20260821_0171
Revises: 20260820_0170
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260821_0171"
down_revision = "20260820_0170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_run_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("run_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("issues_scored", sa.Integer(), nullable=False),
        sa.Column("variants_scored", sa.Integer(), nullable=False),
        sa.Column("recommendations_created", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_uuid", name="uq_recommendation_run_v2_uuid"),
    )
    op.create_index("ix_recommendation_run_v2_owner_user_id", "recommendation_run_v2", ["owner_user_id"])
    op.create_index("ix_recommendation_run_v2_run_uuid", "recommendation_run_v2", ["run_uuid"])
    op.create_index("ix_recommendation_run_v2_status", "recommendation_run_v2", ["status"])
    op.create_index("ix_recommendation_run_v2_owner", "recommendation_run_v2", ["owner_user_id", "started_at", "id"])

    op.create_table(
        "recommendation_score_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_run_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("release_variant_id", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("recommendation_tier", sa.String(length=24), nullable=False),
        sa.Column("recommendation_type", sa.String(length=48), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["recommendation_run_id"], ["recommendation_run_v2.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["release_variant_id"], ["release_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_score_v2_owner_user_id", "recommendation_score_v2", ["owner_user_id"])
    op.create_index("ix_recommendation_score_v2_recommendation_run_id", "recommendation_score_v2", ["recommendation_run_id"])
    op.create_index("ix_recommendation_score_v2_release_issue_id", "recommendation_score_v2", ["release_issue_id"])
    op.create_index("ix_recommendation_score_v2_release_variant_id", "recommendation_score_v2", ["release_variant_id"])
    op.create_index("ix_recommendation_score_v2_total_score", "recommendation_score_v2", ["total_score"])
    op.create_index("ix_recommendation_score_v2_recommendation_tier", "recommendation_score_v2", ["recommendation_tier"])
    op.create_index("ix_recommendation_score_v2_recommendation_type", "recommendation_score_v2", ["recommendation_type"])
    op.create_index(
        "ix_recommendation_score_v2_owner_tier",
        "recommendation_score_v2",
        ["owner_user_id", "recommendation_tier", "total_score", "id"],
    )
    op.create_index(
        "ix_recommendation_score_v2_issue",
        "recommendation_score_v2",
        ["release_issue_id", "created_at", "id"],
    )

    op.create_table(
        "recommendation_score_component_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_score_id", sa.Integer(), nullable=False),
        sa.Column("component_name", sa.String(length=64), nullable=False),
        sa.Column("component_score", sa.Float(), nullable=False),
        sa.Column("component_weight", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_score_id"], ["recommendation_score_v2.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_score_component_v2_recommendation_score_id",
        "recommendation_score_component_v2",
        ["recommendation_score_id"],
    )
    op.create_index(
        "ix_recommendation_score_component_v2_component_name",
        "recommendation_score_component_v2",
        ["component_name"],
    )
    op.create_index(
        "ix_rec_score_component_v2_score",
        "recommendation_score_component_v2",
        ["recommendation_score_id", "component_name"],
    )

    op.create_table(
        "recommendation_decision_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_score_id", sa.Integer(), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("primary_reason", sa.Text(), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("suggested_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_score_id"], ["recommendation_score_v2.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_decision_v2_recommendation_score_id",
        "recommendation_decision_v2",
        ["recommendation_score_id"],
    )
    op.create_index(
        "ix_recommendation_decision_v2_score",
        "recommendation_decision_v2",
        ["recommendation_score_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("recommendation_decision_v2")
    op.drop_table("recommendation_score_component_v2")
    op.drop_table("recommendation_score_v2")
    op.drop_table("recommendation_run_v2")
