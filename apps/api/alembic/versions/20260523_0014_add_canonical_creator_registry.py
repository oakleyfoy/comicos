"""Add canonical creator registry.

Revision ID: 20260523_0014
Revises: 20260523_0013
Create Date: 2026-05-24 02:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0014"
down_revision: str | None = "20260523_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_creator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("creator_key", sa.String(length=1024), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_key", name="uq_canonical_creator_creator_key"),
    )
    op.create_index(
        op.f("ix_canonical_creator_canonical_name"),
        "canonical_creator",
        ["canonical_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_creator_normalized_name"),
        "canonical_creator",
        ["normalized_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_canonical_creator_normalized_name"), table_name="canonical_creator")
    op.drop_index(op.f("ix_canonical_creator_canonical_name"), table_name="canonical_creator")
    op.drop_table("canonical_creator")
