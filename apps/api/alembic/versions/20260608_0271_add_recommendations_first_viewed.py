"""add recommendations_first_viewed_at

Revision ID: 20260608_0271
Revises: 20260608_0270
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0271"
down_revision = "20260608_0270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p77_collector_profile",
        sa.Column("recommendations_first_viewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("p77_collector_profile", "recommendations_first_viewed_at")
