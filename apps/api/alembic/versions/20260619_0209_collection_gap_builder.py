"""Collection gap builder targets + lookup indexes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260619_0209"
down_revision: str | None = "20260619_0208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_gap_target",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_title", sa.String(length=255), nullable=False),
        sa.Column("volume_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("normalized_issue_number", sa.String(length=32), nullable=False),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("placeholder_issue_id", sa.Integer(), nullable=True),
        sa.Column("target_status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["catalog_issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["placeholder_issue_id"], ["acquisition_placeholder_issue.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "volume_id",
            "normalized_issue_number",
            "catalog_issue_id",
            name="uq_collection_gap_target_user_vol_issue_catalog",
        ),
    )
    op.create_index("ix_collection_gap_target_user_id", "collection_gap_target", ["user_id"])
    op.create_index(
        "ix_collection_gap_target_user_volume_issue",
        "collection_gap_target",
        ["user_id", "volume_id", "normalized_issue_number"],
    )
    op.create_index(
        "ix_collection_gap_target_user_status",
        "collection_gap_target",
        ["user_id", "target_status", "id"],
    )
    op.create_index(
        "ix_acq_placeholder_user_source_issue",
        "acquisition_placeholder_issue",
        ["user_id", "source_volume_id", "issue_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_acq_placeholder_user_source_issue", table_name="acquisition_placeholder_issue")
    op.drop_index("ix_collection_gap_target_user_status", table_name="collection_gap_target")
    op.drop_index("ix_collection_gap_target_user_volume_issue", table_name="collection_gap_target")
    op.drop_index("ix_collection_gap_target_user_id", table_name="collection_gap_target")
    op.drop_table("collection_gap_target")
