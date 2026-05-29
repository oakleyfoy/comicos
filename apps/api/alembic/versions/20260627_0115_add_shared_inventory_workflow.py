"""add shared organization inventory workflow foundation

Revision ID: 20260627_0115
Revises: 20260626_0114
Create Date: 2026-06-27 00:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260627_0115"
down_revision = "20260626_0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_inventory_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("assignment_status", sa.String(length=24), nullable=False),
        sa.Column("assignment_notes", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_inv_assign_org_item_status",
        "organization_inventory_assignments",
        ["organization_id", "inventory_item_id", "assignment_status", "assigned_at", "id"],
    )
    op.create_index(
        "ix_org_inv_assign_org_user_status",
        "organization_inventory_assignments",
        ["organization_id", "assigned_user_id", "assignment_status", "assigned_at", "id"],
    )

    op.create_table(
        "organization_inventory_workflow_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("workflow_event_type", sa.String(length=64), nullable=False),
        sa.Column("workflow_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_inv_wf_event_org_created",
        "organization_inventory_workflow_events",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_inv_wf_event_org_item_created",
        "organization_inventory_workflow_events",
        ["organization_id", "inventory_item_id", "created_at", "id"],
    )

    op.create_table(
        "organization_inventory_queues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("queue_name", sa.String(length=48), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("queue_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "inventory_item_id", name="uq_org_inv_queue_org_item"),
    )
    op.create_index(
        "ix_org_inv_queue_org_name_pos",
        "organization_inventory_queues",
        ["organization_id", "queue_name", "queue_position", "id"],
    )
    op.create_index(
        "ix_org_inv_queue_org_status",
        "organization_inventory_queues",
        ["organization_id", "queue_status", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_inv_queue_org_status", table_name="organization_inventory_queues")
    op.drop_index("ix_org_inv_queue_org_name_pos", table_name="organization_inventory_queues")
    op.drop_table("organization_inventory_queues")
    op.drop_index("ix_org_inv_wf_event_org_item_created", table_name="organization_inventory_workflow_events")
    op.drop_index("ix_org_inv_wf_event_org_created", table_name="organization_inventory_workflow_events")
    op.drop_table("organization_inventory_workflow_events")
    op.drop_index("ix_org_inv_assign_org_user_status", table_name="organization_inventory_assignments")
    op.drop_index("ix_org_inv_assign_org_item_status", table_name="organization_inventory_assignments")
    op.drop_table("organization_inventory_assignments")
