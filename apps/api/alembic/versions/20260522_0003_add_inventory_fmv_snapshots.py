"""Add inventory FMV snapshots.

Revision ID: 20260522_0003
Revises: 20260522_0002
Create Date: 2026-05-22 02:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_0003"
down_revision: str | None = "20260522_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_fmv_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("previous_fmv", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_fmv", sa.Numeric(12, 2), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inventory_fmv_snapshot_inventory_copy_id"),
        "inventory_fmv_snapshot",
        ["inventory_copy_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("inventory_fmv_snapshot")
