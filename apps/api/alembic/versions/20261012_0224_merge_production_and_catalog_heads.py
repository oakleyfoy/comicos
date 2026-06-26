"""merge production intake head with catalog/receiving branch heads

Revision ID: 20261012_0224
Revises: 20260619_0205, 20260628_0100, 20261012_0222
Create Date: 2026-10-12 02:24:00

P104 was chained only to 20261012_0222, which is not an ancestor of the
production head 20260628_0100. This merge reunifies the migration graph
without dropping migrations from either branch.
"""

from __future__ import annotations

from alembic import op

revision = "20261012_0224"
down_revision = ("20260619_0205", "20260628_0100", "20261012_0222")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
