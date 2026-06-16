"""Placeholder variant fields and lookup indexes (P99 phases 03-05)."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260619_0208"
down_revision: str | None = "20260619_0207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("variant_label", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("cover_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("printing", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("ratio_variant", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("barcode", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("cover_artist", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("raw_variant_notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_acq_placeholder_title_issue",
        "acquisition_placeholder_issue",
        ["title", "issue_number"],
    )
    op.create_index(
        "ix_acq_placeholder_publisher_title",
        "acquisition_placeholder_issue",
        ["publisher", "title"],
    )


def downgrade() -> None:
    op.drop_index("ix_acq_placeholder_publisher_title", table_name="acquisition_placeholder_issue")
    op.drop_index("ix_acq_placeholder_title_issue", table_name="acquisition_placeholder_issue")
    for col in (
        "raw_variant_notes",
        "cover_artist",
        "barcode",
        "ratio_variant",
        "printing",
        "cover_type",
        "variant_label",
    ):
        op.drop_column("acquisition_placeholder_issue", col)
