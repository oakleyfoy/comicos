"""add p90 advisor generation_status

Revision ID: 20260608_0268
Revises: 20260608_0267
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0268"
down_revision = "20260608_0267"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p90_collector_advisor_snapshot",
        sa.Column("generation_status", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("p90_collector_advisor_snapshot", "generation_status")
