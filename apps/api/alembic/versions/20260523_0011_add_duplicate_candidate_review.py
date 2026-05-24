"""Add duplicate candidate review table.

Revision ID: 20260523_0011
Revises: 20260523_0010
Create Date: 2026-05-23-223000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0011"
down_revision: str | None = "20260523_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_candidate_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("metadata_identity_key", sa.String(length=1024), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "metadata_identity_key",
            name="uq_duplicate_candidate_review_metadata_key",
        ),
    )
    op.create_index(
        op.f("ix_duplicate_candidate_review_review_status"),
        "duplicate_candidate_review",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_duplicate_candidate_review_reviewed_by_user_id"),
        "duplicate_candidate_review",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_duplicate_candidate_review_reviewed_by_user_id"),
        table_name="duplicate_candidate_review",
    )
    op.drop_index(
        op.f("ix_duplicate_candidate_review_review_status"),
        table_name="duplicate_candidate_review",
    )
    op.drop_table("duplicate_candidate_review")
