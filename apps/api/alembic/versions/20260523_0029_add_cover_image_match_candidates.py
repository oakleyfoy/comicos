"""Add cover image match candidate persistence.

Revision ID: 20260523_0029
Revises: 20260523_0028
Create Date: 2026-06-07 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0029"
down_revision: str | None = "20260523_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_image_match_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_cover_image_id", sa.Integer(), nullable=False),
        sa.Column("candidate_cover_image_id", sa.Integer(), nullable=False),
        sa.Column("candidate_type", sa.String(length=30), nullable=False),
        sa.Column("confidence_bucket", sa.String(length=20), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("matched_signals", sa.JSON(), nullable=False),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["candidate_cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_source_cover_image_id"),
        "cover_image_match_candidate",
        ["source_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_candidate_cover_image_id"),
        "cover_image_match_candidate",
        ["candidate_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_candidate_type"),
        "cover_image_match_candidate",
        ["candidate_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_confidence_bucket"),
        "cover_image_match_candidate",
        ["confidence_bucket"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_extraction_version"),
        "cover_image_match_candidate",
        ["extraction_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_match_candidate_extraction_version"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_confidence_bucket"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_candidate_type"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_candidate_cover_image_id"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_source_cover_image_id"),
        table_name="cover_image_match_candidate",
    )
    op.drop_table("cover_image_match_candidate")
