"""merge alembic heads: collector ratio variant + P61 demand intelligence

Revision ID: 20260605_0220
Revises: 20260604_0213, 20260605_0219
Create Date: 2026-06-05 16:30:00
"""

from __future__ import annotations

from alembic import op


revision = "20260605_0220"
down_revision = ("20260604_0213", "20260605_0219")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
