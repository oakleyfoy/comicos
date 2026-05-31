from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260906_0182"
down_revision = "20260905_0181"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "want_list",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_want_list_owner_active", "want_list", ["owner_user_id", "is_active", "id"])
    op.create_index(op.f("ix_want_list_owner_user_id"), "want_list", ["owner_user_id"])

    op.create_table(
        "want_list_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("want_list_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("variant_description", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["want_list_id"], ["want_list.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_want_list_item_owner_status", "want_list_item", ["owner_user_id", "status", "id"])
    op.create_index("ix_want_list_item_owner_priority", "want_list_item", ["owner_user_id", "priority", "id"])
    op.create_index(op.f("ix_want_list_item_owner_user_id"), "want_list_item", ["owner_user_id"])
    op.create_index(op.f("ix_want_list_item_want_list_id"), "want_list_item", ["want_list_id"])
    op.create_index(op.f("ix_want_list_item_priority"), "want_list_item", ["priority"])
    op.create_index(op.f("ix_want_list_item_status"), "want_list_item", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_want_list_item_status"), table_name="want_list_item")
    op.drop_index(op.f("ix_want_list_item_priority"), table_name="want_list_item")
    op.drop_index(op.f("ix_want_list_item_want_list_id"), table_name="want_list_item")
    op.drop_index(op.f("ix_want_list_item_owner_user_id"), table_name="want_list_item")
    op.drop_index("ix_want_list_item_owner_priority", table_name="want_list_item")
    op.drop_index("ix_want_list_item_owner_status", table_name="want_list_item")
    op.drop_table("want_list_item")
    op.drop_index(op.f("ix_want_list_owner_user_id"), table_name="want_list")
    op.drop_index("ix_want_list_owner_active", table_name="want_list")
    op.drop_table("want_list")
