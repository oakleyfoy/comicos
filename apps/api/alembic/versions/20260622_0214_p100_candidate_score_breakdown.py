"""P100-18 candidate score breakdown JSON."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260622_0214"
down_revision = "20260621_0213"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("photo_import_candidate", sa.Column("score_breakdown", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("photo_import_candidate", "score_breakdown")
