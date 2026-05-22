"""Add draft imports.

Revision ID: 20260522_0004
Revises: 20260522_0003
Create Date: 2026-05-22 23:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_0004"
down_revision: str | None = "20260522_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_import",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("parsed_payload_json", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_draft_import_user_id"), "draft_import", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("draft_import")
