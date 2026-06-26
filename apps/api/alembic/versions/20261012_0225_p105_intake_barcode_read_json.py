"""P105 intake item barcode diagnostics JSON."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261012_0225"
down_revision = "20261012_0223"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("intake_session_item", sa.Column("barcode_read_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("intake_session_item", "barcode_read_json")
