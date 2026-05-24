"""Add deterministic confidence fields to cover match candidates.

Revision ID: 20260523_0034
Revises: 20260523_0033
Create Date: 2026-06-07 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0034"
down_revision: str | None = "20260523_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "normalized_confidence_score",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "confidence_version",
            sa.String(length=100),
            nullable=False,
            server_default="cover-match-confidence-v1",
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "scoring_breakdown_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "matched_signal_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "hard_match_flags_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "cover_image_match_candidate",
        sa.Column(
            "weak_signal_flags_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_index(
        op.f("ix_cover_image_match_candidate_confidence_version"),
        "cover_image_match_candidate",
        ["confidence_version"],
        unique=False,
    )

    op.alter_column("cover_image_match_candidate", "normalized_confidence_score", server_default=None)
    op.alter_column("cover_image_match_candidate", "confidence_version", server_default=None)
    op.alter_column("cover_image_match_candidate", "scoring_breakdown_json", server_default=None)
    op.alter_column("cover_image_match_candidate", "matched_signal_count", server_default=None)
    op.alter_column("cover_image_match_candidate", "hard_match_flags_json", server_default=None)
    op.alter_column("cover_image_match_candidate", "weak_signal_flags_json", server_default=None)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cover_image_match_candidate_confidence_version"),
        table_name="cover_image_match_candidate",
    )
    op.drop_column("cover_image_match_candidate", "weak_signal_flags_json")
    op.drop_column("cover_image_match_candidate", "hard_match_flags_json")
    op.drop_column("cover_image_match_candidate", "matched_signal_count")
    op.drop_column("cover_image_match_candidate", "scoring_breakdown_json")
    op.drop_column("cover_image_match_candidate", "confidence_version")
    op.drop_column("cover_image_match_candidate", "normalized_confidence_score")
