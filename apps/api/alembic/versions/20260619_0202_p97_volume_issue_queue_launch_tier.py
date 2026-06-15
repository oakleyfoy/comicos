"""Add launch_priority_tier to P97 volume issue import queue."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_0202"
down_revision = "20260619_0201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p97_volume_issue_import_queue",
        sa.Column(
            "launch_priority_tier",
            sa.String(length=32),
            nullable=False,
            server_default="tier_3_other_us",
        ),
    )
    op.create_index(
        "ix_p97_volume_issue_import_queue_launch_priority_tier",
        "p97_volume_issue_import_queue",
        ["launch_priority_tier"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_p97_volume_issue_import_queue_launch_priority_tier",
        table_name="p97_volume_issue_import_queue",
    )
    op.drop_column("p97_volume_issue_import_queue", "launch_priority_tier")
