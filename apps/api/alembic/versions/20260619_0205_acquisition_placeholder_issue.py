"""Acquisition placeholder issues (non-catalog books in acquisitions)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_0205"
down_revision = "20260619_0204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acquisition_placeholder_issue",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("acquisition_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("issue_number", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("catalog_status", sa.String(length=20), nullable=False, server_default="PLACEHOLDER"),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["acquisition_id"], ["acquisitions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["catalog_issue_id"], ["catalog_issue.id"]),
    )
    op.create_index(
        "ix_acq_placeholder_acquisition_id", "acquisition_placeholder_issue", ["acquisition_id"]
    )
    op.create_index("ix_acq_placeholder_user_id", "acquisition_placeholder_issue", ["user_id"])
    op.create_index(
        "ix_acq_placeholder_catalog_status", "acquisition_placeholder_issue", ["catalog_status"]
    )
    op.create_index(
        "ix_acq_placeholder_catalog_issue_id", "acquisition_placeholder_issue", ["catalog_issue_id"]
    )

    op.add_column(
        "inventory_copy",
        sa.Column("placeholder_issue_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_inventory_copy_placeholder_issue_id", "inventory_copy", ["placeholder_issue_id"]
    )
    op.create_foreign_key(
        "fk_inventory_copy_placeholder_issue_id",
        "inventory_copy",
        "acquisition_placeholder_issue",
        ["placeholder_issue_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_copy_placeholder_issue_id", "inventory_copy", type_="foreignkey"
    )
    op.drop_index("ix_inventory_copy_placeholder_issue_id", table_name="inventory_copy")
    op.drop_column("inventory_copy", "placeholder_issue_id")

    op.drop_index(
        "ix_acq_placeholder_catalog_issue_id", table_name="acquisition_placeholder_issue"
    )
    op.drop_index("ix_acq_placeholder_catalog_status", table_name="acquisition_placeholder_issue")
    op.drop_index("ix_acq_placeholder_user_id", table_name="acquisition_placeholder_issue")
    op.drop_index(
        "ix_acq_placeholder_acquisition_id", table_name="acquisition_placeholder_issue"
    )
    op.drop_table("acquisition_placeholder_issue")
