"""P66-06 printing intelligence columns on release_issue and release_variant

Revision ID: 20260612_0227
Revises: 20260611_0226
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260612_0227"
down_revision = "20260611_0226"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("release_issue", sa.Column("original_foc_date", sa.Date(), nullable=True))
    op.add_column("release_issue", sa.Column("original_release_date", sa.Date(), nullable=True))
    op.create_index("ix_release_issue_owner_original_release", "release_issue", ["owner_user_id", "original_release_date"])

    op.add_column("release_variant", sa.Column("printing_number", sa.Integer(), nullable=True))
    op.add_column(
        "release_variant",
        sa.Column("printing_kind", sa.String(length=32), nullable=False, server_default="FIRST_PRINT"),
    )
    op.add_column("release_variant", sa.Column("printing_foc_date", sa.Date(), nullable=True))
    op.add_column("release_variant", sa.Column("printing_release_date", sa.Date(), nullable=True))
    op.create_index("ix_release_variant_printing_kind", "release_variant", ["printing_kind", "issue_id"])


def downgrade() -> None:
    op.drop_index("ix_release_variant_printing_kind", table_name="release_variant")
    op.drop_column("release_variant", "printing_release_date")
    op.drop_column("release_variant", "printing_foc_date")
    op.drop_column("release_variant", "printing_kind")
    op.drop_column("release_variant", "printing_number")

    op.drop_index("ix_release_issue_owner_original_release", table_name="release_issue")
    op.drop_column("release_issue", "original_release_date")
    op.drop_column("release_issue", "original_foc_date")
