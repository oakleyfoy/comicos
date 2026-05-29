"""add organization review workflow foundation

Revision ID: 20260628_0116
Revises: 20260627_0115
Create Date: 2026-06-28 00:16:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260628_0116"
down_revision = "20260627_0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("review_type", sa.String(length=48), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_review_org_status_requested",
        "organization_reviews",
        ["organization_id", "review_status", "requested_at", "id"],
    )
    op.create_index(
        "ix_org_review_org_item_status",
        "organization_reviews",
        ["organization_id", "inventory_item_id", "review_status", "id"],
    )
    op.create_index(
        "ix_org_review_org_assignee_status",
        "organization_reviews",
        ["organization_id", "assigned_user_id", "review_status", "id"],
    )

    op.create_table(
        "organization_review_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_review_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=24), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_review_id"], ["organization_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_review_decision_review_created",
        "organization_review_decisions",
        ["organization_review_id", "created_at", "id"],
    )

    op.create_table(
        "organization_approval_queues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("queue_name", sa.String(length=48), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("queue_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["organization_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", name="uq_org_approval_queue_org_review"),
    )
    op.create_index(
        "ix_org_approval_queue_org_name_pos",
        "organization_approval_queues",
        ["organization_id", "queue_name", "queue_position", "id"],
    )
    op.create_index(
        "ix_org_approval_queue_org_status",
        "organization_approval_queues",
        ["organization_id", "queue_status", "created_at", "id"],
    )

    op.create_table(
        "organization_review_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("organization_review_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["organization_review_id"], ["organization_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_review_event_org_created", "organization_review_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_org_review_event_review_created",
        "organization_review_events",
        ["organization_review_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_review_event_review_created", table_name="organization_review_events")
    op.drop_index("ix_org_review_event_org_created", table_name="organization_review_events")
    op.drop_table("organization_review_events")
    op.drop_index("ix_org_approval_queue_org_status", table_name="organization_approval_queues")
    op.drop_index("ix_org_approval_queue_org_name_pos", table_name="organization_approval_queues")
    op.drop_table("organization_approval_queues")
    op.drop_index("ix_org_review_decision_review_created", table_name="organization_review_decisions")
    op.drop_table("organization_review_decisions")
    op.drop_index("ix_org_review_org_assignee_status", table_name="organization_reviews")
    op.drop_index("ix_org_review_org_item_status", table_name="organization_reviews")
    op.drop_index("ix_org_review_org_status_requested", table_name="organization_reviews")
    op.drop_table("organization_reviews")
