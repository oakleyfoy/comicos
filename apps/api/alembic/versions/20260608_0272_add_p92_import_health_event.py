"""add p92 import health events

Revision ID: 20260608_0272
Revises: 20260608_0271
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0272"
down_revision = "20260608_0271"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p92_import_health_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("draft_import_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["draft_import_id"], ["draft_import.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p92_import_health_owner_created", "p92_import_health_event", ["owner_user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_p92_import_health_owner_created", table_name="p92_import_health_event")
    op.drop_table("p92_import_health_event")
