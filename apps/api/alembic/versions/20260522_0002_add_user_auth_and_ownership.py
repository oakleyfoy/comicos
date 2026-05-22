"""Add user auth and ownership fields.

Revision ID: 20260522_0002
Revises: 20260522_0001
Create Date: 2026-05-22 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260522_0002"
down_revision: str | None = "20260522_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.add_column("customer_order", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_customer_order_user_id"), "customer_order", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_customer_order_user_id_user",
        "customer_order",
        "user",
        ["user_id"],
        ["id"],
    )

    op.add_column("inventory_copy", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_inventory_copy_user_id"), "inventory_copy", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_inventory_copy_user_id_user",
        "inventory_copy",
        "user",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_inventory_copy_user_id_user", "inventory_copy", type_="foreignkey")
    op.drop_index(op.f("ix_inventory_copy_user_id"), table_name="inventory_copy")
    op.drop_column("inventory_copy", "user_id")

    op.drop_constraint("fk_customer_order_user_id_user", "customer_order", type_="foreignkey")
    op.drop_index(op.f("ix_customer_order_user_id"), table_name="customer_order")
    op.drop_column("customer_order", "user_id")

    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
