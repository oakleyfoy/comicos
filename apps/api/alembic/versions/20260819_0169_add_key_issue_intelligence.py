"""add key issue intelligence (P51-02)

Revision ID: 20260819_0169
Revises: 20260818_0168
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260819_0169"
down_revision = "20260818_0168"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "key_issue_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("key_issue_type", sa.String(length=48), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_issue_id", "key_issue_type", name="uq_key_issue_profile_issue_type"),
    )
    op.create_index("ix_key_issue_profile_release_issue_id", "key_issue_profile", ["release_issue_id"])
    op.create_index("ix_key_issue_profile_key_issue_type", "key_issue_profile", ["key_issue_type"])
    op.create_index("ix_key_issue_profile_importance_score", "key_issue_profile", ["importance_score"])
    op.create_index("ix_key_issue_profile_source_version", "key_issue_profile", ["source_version"])
    op.create_index("ix_key_issue_profile_issue_created", "key_issue_profile", ["release_issue_id", "created_at", "id"])
    op.create_index("ix_key_issue_profile_type_score", "key_issue_profile", ["key_issue_type", "importance_score", "id"])

    op.create_table(
        "key_issue_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=48), nullable=False),
        sa.Column("signal_strength", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_key_issue_signal_release_issue_id", "key_issue_signal", ["release_issue_id"])
    op.create_index("ix_key_issue_signal_signal_type", "key_issue_signal", ["signal_type"])
    op.create_index("ix_key_issue_signal_issue_type", "key_issue_signal", ["release_issue_id", "signal_type", "id"])

    op.create_table(
        "key_issue_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key_issue_profile_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("evidence_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["key_issue_profile_id"], ["key_issue_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_key_issue_evidence_key_issue_profile_id", "key_issue_evidence", ["key_issue_profile_id"])
    op.create_index("ix_key_issue_evidence_evidence_type", "key_issue_evidence", ["evidence_type"])
    op.create_index("ix_key_issue_evidence_profile", "key_issue_evidence", ["key_issue_profile_id", "created_at", "id"])

    op.create_table(
        "key_issue_classification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_issue_id", name="uq_key_issue_classification_issue"),
    )
    op.create_index("ix_key_issue_classification_release_issue_id", "key_issue_classification", ["release_issue_id"])
    op.create_index("ix_key_issue_classification_classification", "key_issue_classification", ["classification"])
    op.create_index("ix_key_issue_classification_class", "key_issue_classification", ["classification", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("key_issue_classification")
    op.drop_table("key_issue_evidence")
    op.drop_table("key_issue_signal")
    op.drop_table("key_issue_profile")
