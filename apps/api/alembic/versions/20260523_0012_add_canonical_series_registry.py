"""Add canonical series registry.

Revision ID: 20260523_0012
Revises: 20260523_0011
Create Date: 2026-05-23 23:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0012"
down_revision: str | None = "20260523_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_title", sa.String(length=255), nullable=False),
        sa.Column("canonical_publisher", sa.String(length=255), nullable=False),
        sa.Column("series_key", sa.String(length=1024), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_key", name="uq_canonical_series_series_key"),
    )
    op.create_index(
        op.f("ix_canonical_series_canonical_publisher"),
        "canonical_series",
        ["canonical_publisher"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_series_canonical_title"),
        "canonical_series",
        ["canonical_title"],
        unique=False,
    )

    op.add_column(
        "inventory_copy",
        sa.Column("canonical_series_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_inventory_copy_canonical_series_id"),
        "inventory_copy",
        ["canonical_series_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inventory_copy_canonical_series_id_canonical_series",
        "inventory_copy",
        "canonical_series",
        ["canonical_series_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_copy_canonical_series_id_canonical_series",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_inventory_copy_canonical_series_id"), table_name="inventory_copy")
    op.drop_column("inventory_copy", "canonical_series_id")

    op.drop_index(op.f("ix_canonical_series_canonical_title"), table_name="canonical_series")
    op.drop_index(op.f("ix_canonical_series_canonical_publisher"), table_name="canonical_series")
    op.drop_table("canonical_series")
