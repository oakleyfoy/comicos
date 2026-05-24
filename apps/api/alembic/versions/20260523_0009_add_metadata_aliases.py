"""Add metadata aliases.

Revision ID: 20260523_0009
Revises: 20260523_0008
Create Date: 2026-05-23 18:10:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0009"
down_revision: str | None = "20260523_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    op.create_table(
        "metadata_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alias_value", sa.String(length=255), nullable=False),
        sa.Column("canonical_value", sa.String(length=255), nullable=False),
        sa.Column("alias_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "alias_type",
            "alias_value",
            name="uq_metadata_alias_alias_type_value",
        ),
    )
    op.create_index(
        op.f("ix_metadata_alias_alias_type"),
        "metadata_alias",
        ["alias_type"],
        unique=False,
    )
    op.bulk_insert(
        sa.table(
            "metadata_alias",
            sa.column("alias_value", sa.String()),
            sa.column("canonical_value", sa.String()),
            sa.column("alias_type", sa.String()),
            sa.column("source", sa.String()),
            sa.column("is_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "alias_value": "IDW Publishing",
                "canonical_value": "IDW",
                "alias_type": "publisher",
                "source": "manual",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "alias_value": "Image Comics",
                "canonical_value": "Image",
                "alias_type": "publisher",
                "source": "manual",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "alias_value": "Mad Cave Studios",
                "canonical_value": "Mad Cave",
                "alias_type": "publisher",
                "source": "manual",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "alias_value": "Marvel Comics",
                "canonical_value": "Marvel",
                "alias_type": "publisher",
                "source": "manual",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "alias_value": "DC Comics",
                "canonical_value": "DC",
                "alias_type": "publisher",
                "source": "manual",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_metadata_alias_alias_type"), table_name="metadata_alias")
    op.drop_table("metadata_alias")
