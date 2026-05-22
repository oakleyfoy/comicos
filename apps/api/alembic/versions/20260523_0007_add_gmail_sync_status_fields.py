"""Add Gmail sync status fields.

Revision ID: 20260523_0007
Revises: 20260523_0006
Create Date: 2026-05-23 11:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0007"
down_revision: str | None = "20260523_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gmail_account",
        sa.Column("auto_sync_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "gmail_account",
        sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gmail_account",
        sa.Column("last_sync_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gmail_account",
        sa.Column("last_sync_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "gmail_account",
        sa.Column("last_sync_error", sa.String(), nullable=True),
    )
    op.alter_column("gmail_account", "auto_sync_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("gmail_account", "last_sync_error")
    op.drop_column("gmail_account", "last_sync_status")
    op.drop_column("gmail_account", "last_sync_completed_at")
    op.drop_column("gmail_account", "last_sync_started_at")
    op.drop_column("gmail_account", "auto_sync_enabled")
