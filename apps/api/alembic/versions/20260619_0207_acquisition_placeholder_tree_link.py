"""Tree-linked acquisition placeholder metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260619_0207"
down_revision: str | None = "20260619_0206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("comicvine_volume_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("source_volume_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("source_issue_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "acquisition_placeholder_issue",
        sa.Column("tree_linked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_acq_placeholder_source_volume_id",
        "acquisition_placeholder_issue",
        ["source_volume_id"],
    )
    op.create_index(
        "ix_acq_placeholder_tree_volume_issue",
        "acquisition_placeholder_issue",
        ["acquisition_id", "source_volume_id", "issue_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_acq_placeholder_tree_volume_issue", table_name="acquisition_placeholder_issue")
    op.drop_index("ix_acq_placeholder_source_volume_id", table_name="acquisition_placeholder_issue")
    op.drop_column("acquisition_placeholder_issue", "tree_linked")
    op.drop_column("acquisition_placeholder_issue", "source_issue_id")
    op.drop_column("acquisition_placeholder_issue", "source_volume_id")
    op.drop_column("acquisition_placeholder_issue", "comicvine_volume_id")
