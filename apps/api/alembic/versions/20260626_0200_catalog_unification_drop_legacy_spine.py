"""Catalog unification: detach inventory_copy from legacy spine and drop legacy tables.

Nulls inventory_copy.order_item_id / variant_id, drops FKs, removes
grading_candidate.canonical_comic_issue_id, then drops customer_order,
order_item, variant, comic_issue, and comic_title. Keeps publisher (still
referenced by canonical metadata and market rows).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260626_0200"
down_revision = "20260626_0100"
branch_labels = None
depends_on = None

_LEGACY_TABLES_DROP_ORDER = ("order_item", "customer_order", "variant", "comic_issue", "comic_title")


def _drop_all_fks_referencing(referred_table: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk.get("referred_table") == referred_table and fk.get("name"):
                op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    op.execute(sa.text("UPDATE inventory_copy SET order_item_id = NULL, variant_id = NULL"))

    for legacy in _LEGACY_TABLES_DROP_ORDER:
        _drop_all_fks_referencing(legacy)

    if "canonical_comic_issue_id" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("grading_candidate")}:
        op.drop_column("grading_candidate", "canonical_comic_issue_id")

    for table in _LEGACY_TABLES_DROP_ORDER:
        if sa.inspect(op.get_bind()).has_table(table):
            op.drop_table(table)


def downgrade() -> None:
    raise NotImplementedError("Legacy spine teardown is not reversible via downgrade.")
