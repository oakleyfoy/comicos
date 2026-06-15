"""Add manual request notes to P97 volume issue import queue."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260619_0203"
down_revision = "20260619_0202"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p97_volume_issue_import_queue",
        sa.Column("request_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("p97_volume_issue_import_queue", "request_notes")
