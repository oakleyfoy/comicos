"""add collector home checklist dismissed timestamp

Revision ID: 20260608_0270
Revises: 20260608_0269
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0270"
down_revision = "20260608_0269"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p77_collector_profile",
        sa.Column("collector_home_checklist_dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("p77_collector_profile", "collector_home_checklist_dismissed_at")
