"""add external catalog decision_signals_json for RDE feed

Revision ID: 20261011_0217
Revises: 20261010_0216
Create Date: 2026-10-11 02:17:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261011_0217"
down_revision = "20261010_0216"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_catalog_issue",
        sa.Column("decision_signals_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_catalog_issue", "decision_signals_json")
