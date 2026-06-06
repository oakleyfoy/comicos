"""add P79-01 storage foundation

Revision ID: 20260607_0242
Revises: 20260607_0241
Create Date: 2026-06-07 02:42:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0242"
down_revision = "20260607_0241"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p79_storage_location",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("location_kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["p79_storage_location.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_storage_loc_owner_parent",
        "p79_storage_location",
        ["owner_user_id", "parent_id", "id"],
    )

    op.create_table(
        "p79_storage_box",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("shelf_location_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["shelf_location_id"], ["p79_storage_location.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p79_storage_box_shelf", "p79_storage_box", ["shelf_location_id", "id"])

    op.create_table(
        "p79_storage_slot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("box_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["box_id"], ["p79_storage_box.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("box_id", "slot_number", name="uq_p79_box_slot_number"),
    )
    op.create_index("ix_p79_storage_slot_box", "p79_storage_slot", ["box_id", "slot_number"])

    op.create_table(
        "p79_inventory_location_assignment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("storage_slot_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["storage_slot_id"], ["p79_storage_slot.id"]),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inventory_copy_id", name="uq_p79_inv_copy_assignment"),
    )
    op.create_index(
        "ix_p79_inv_assign_owner",
        "p79_inventory_location_assignment",
        ["owner_user_id", "inventory_copy_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p79_inv_assign_owner", table_name="p79_inventory_location_assignment")
    op.drop_table("p79_inventory_location_assignment")
    op.drop_index("ix_p79_storage_slot_box", table_name="p79_storage_slot")
    op.drop_table("p79_storage_slot")
    op.drop_index("ix_p79_storage_box_shelf", table_name="p79_storage_box")
    op.drop_table("p79_storage_box")
    op.drop_index("ix_p79_storage_loc_owner_parent", table_name="p79_storage_location")
    op.drop_table("p79_storage_location")
