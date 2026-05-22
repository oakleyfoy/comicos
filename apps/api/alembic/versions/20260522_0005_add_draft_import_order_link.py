"""Add linked order id to draft imports.

Revision ID: 20260522_0005
Revises: 20260522_0004
Create Date: 2026-05-22 23:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_0005"
down_revision: str | None = "20260522_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("draft_import", sa.Column("linked_order_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_draft_import_linked_order_id_customer_order",
        "draft_import",
        "customer_order",
        ["linked_order_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_draft_import_linked_order_id"),
        "draft_import",
        ["linked_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_draft_import_linked_order_id"), table_name="draft_import")
    op.drop_constraint("fk_draft_import_linked_order_id_customer_order", "draft_import")
    op.drop_column("draft_import", "linked_order_id")
