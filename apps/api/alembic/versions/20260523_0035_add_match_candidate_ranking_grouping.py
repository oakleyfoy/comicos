"""Add deterministic ranking and grouping fields to cover match candidates.

Revision ID: 20260523_0035
Revises: 20260523_0034
Create Date: 2026-06-07 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0035"
down_revision: str | None = "20260523_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("ranking_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "ranking_version",
            sa.String(length=100),
            nullable=False,
            server_default="cover-match-ranking-v1",
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "ranking_reason_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("candidate_rank", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("grouping_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("grouping_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("grouping_confidence_bucket", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column("grouping_reason_summary", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_ranking_version"),
        "cover_image_match_candidate",
        ["ranking_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_candidate_rank"),
        "cover_image_match_candidate",
        ["candidate_rank"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_grouping_key"),
        "cover_image_match_candidate",
        ["grouping_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_grouping_type"),
        "cover_image_match_candidate",
        ["grouping_type"],
        unique=False,
    )

    op.alter_column("cover_image_match_candidate", "ranking_score", server_default=None)
    op.alter_column("cover_image_match_candidate", "ranking_version", server_default=None)
    op.alter_column("cover_image_match_candidate", "ranking_reason_json", server_default=None)
    op.alter_column("cover_image_match_candidate", "candidate_rank", server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_match_candidate_grouping_type"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_grouping_key"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_candidate_rank"),
        table_name="cover_image_match_candidate",
    )
    op.drop_index(
        op.f("ix_cover_image_match_candidate_ranking_version"),
        table_name="cover_image_match_candidate",
    )
    op.drop_column("cover_image_match_candidate", "grouping_reason_summary")
    op.drop_column("cover_image_match_candidate", "grouping_confidence_bucket")
    op.drop_column("cover_image_match_candidate", "grouping_type")
    op.drop_column("cover_image_match_candidate", "grouping_key")
    op.drop_column("cover_image_match_candidate", "candidate_rank")
    op.drop_column("cover_image_match_candidate", "ranking_reason_json")
    op.drop_column("cover_image_match_candidate", "ranking_version")
    op.drop_column("cover_image_match_candidate", "ranking_score")
