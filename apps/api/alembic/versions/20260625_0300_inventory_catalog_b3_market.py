"""Inventory catalog unification B3: catalog_issue_id on market read ledgers.

Adds nullable catalog_issue_id alongside legacy canonical_comic_issue_id so
inventory and market surfaces can key on the master catalog spine during
transition. Additive + nullable => fully reversible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260625_0300"
down_revision = "20260625_0200"
branch_labels = None
depends_on = None


def _add_catalog_issue_id(table: str) -> None:
    op.add_column(table, sa.Column("catalog_issue_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        f"fk_{table}_catalog_issue_id_catalog_issue",
        table,
        "catalog_issue",
        ["catalog_issue_id"],
        ["id"],
    )
    op.create_index(f"ix_{table}_catalog_issue_id", table, ["catalog_issue_id"])


def _drop_catalog_issue_id(table: str) -> None:
    op.drop_index(f"ix_{table}_catalog_issue_id", table_name=table)
    op.drop_constraint(f"fk_{table}_catalog_issue_id_catalog_issue", table, type_="foreignkey")
    op.drop_column(table, "catalog_issue_id")


def upgrade() -> None:
    for table in (
        "market_acquisition_score",
        "inventory_liquidity_snapshot",
        "listing_intelligence_snapshot",
    ):
        _add_catalog_issue_id(table)


def downgrade() -> None:
    for table in (
        "listing_intelligence_snapshot",
        "inventory_liquidity_snapshot",
        "market_acquisition_score",
    ):
        _drop_catalog_issue_id(table)
