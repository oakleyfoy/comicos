"""Add cover link decision storage.

Revision ID: 20260523_0036
Revises: 20260523_0035
Create Date: 2026-06-08 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0036"
down_revision: str | None = "20260523_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_link_decision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_cover_image_id", sa.Integer(), nullable=False),
        sa.Column("candidate_cover_image_id", sa.Integer(), nullable=False),
        sa.Column("pair_key", sa.String(length=255), nullable=False),
        sa.Column("source_match_candidate_id", sa.Integer(), nullable=True),
        sa.Column("decision_type", sa.String(length=30), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("decision_state", sa.String(length=20), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decision_source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_decision_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["source_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["source_match_candidate_id"], ["cover_image_match_candidate.id"]),
        sa.ForeignKeyConstraint(["superseded_by_decision_id"], ["cover_image_link_decision.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_source_cover_image_id"),
        "cover_image_link_decision",
        ["source_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_candidate_cover_image_id"),
        "cover_image_link_decision",
        ["candidate_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_pair_key"),
        "cover_image_link_decision",
        ["pair_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_source_match_candidate_id"),
        "cover_image_link_decision",
        ["source_match_candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_decision_type"),
        "cover_image_link_decision",
        ["decision_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_relationship_type"),
        "cover_image_link_decision",
        ["relationship_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_decision_state"),
        "cover_image_link_decision",
        ["decision_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_reviewer_user_id"),
        "cover_image_link_decision",
        ["reviewer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_decision_source"),
        "cover_image_link_decision",
        ["decision_source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_link_decision_superseded_by_decision_id"),
        "cover_image_link_decision",
        ["superseded_by_decision_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_link_decision_superseded_by_decision_id"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_decision_source"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_reviewer_user_id"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_decision_state"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_relationship_type"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_decision_type"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_source_match_candidate_id"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_pair_key"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_candidate_cover_image_id"),
        table_name="cover_image_link_decision",
    )
    op.drop_index(
        op.f("ix_cover_image_link_decision_source_cover_image_id"),
        table_name="cover_image_link_decision",
    )
    op.drop_table("cover_image_link_decision")

