"""Inventory catalog unification B2: catalog_issue_id on grading ledgers."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260626_0100"
down_revision = "20260625_0300"
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
        "grading_candidate",
        "grading_recommendation",
        "grading_roi_snapshot",
        "grading_risk_snapshot",
        "grading_spread_snapshot",
    ):
        _add_catalog_issue_id(table)


def downgrade() -> None:
    for table in (
        "grading_spread_snapshot",
        "grading_risk_snapshot",
        "grading_roi_snapshot",
        "grading_recommendation",
        "grading_candidate",
    ):
        _drop_catalog_issue_id(table)
