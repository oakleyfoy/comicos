"""add organization activity feed foundation

Revision ID: 20260630_0118
Revises: 20260629_0117
Create Date: 2026-06-30 00:18:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260630_0118"
down_revision = "20260629_0117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_activity_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("activity_type", sa.String(length=64), nullable=False),
        sa.Column("activity_payload_json", sa.JSON(), nullable=False),
        sa.Column("visibility_scope", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_activity_event_org_created",
        "organization_activity_events",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_activity_event_org_type_created",
        "organization_activity_events",
        ["organization_id", "activity_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_organization_activity_events_activity_type"), "organization_activity_events", ["activity_type"])
    op.create_index(op.f("ix_organization_activity_events_actor_user_id"), "organization_activity_events", ["actor_user_id"])
    op.create_index(op.f("ix_organization_activity_events_organization_id"), "organization_activity_events", ["organization_id"])
    op.create_index(op.f("ix_organization_activity_events_visibility_scope"), "organization_activity_events", ["visibility_scope"])

    op.create_table(
        "organization_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=48), nullable=False),
        sa.Column("notification_title", sa.String(length=200), nullable=False),
        sa.Column("notification_body", sa.String(length=2000), nullable=False),
        sa.Column("notification_status", sa.String(length=24), nullable=False),
        sa.Column("activity_event_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_event_id"], ["organization_activity_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_notification_org_target_created",
        "organization_notifications",
        ["organization_id", "target_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_notification_org_status_created",
        "organization_notifications",
        ["organization_id", "notification_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_organization_notifications_activity_event_id"), "organization_notifications", ["activity_event_id"])
    op.create_index(op.f("ix_organization_notifications_notification_status"), "organization_notifications", ["notification_status"])
    op.create_index(op.f("ix_organization_notifications_notification_type"), "organization_notifications", ["notification_type"])
    op.create_index(op.f("ix_organization_notifications_organization_id"), "organization_notifications", ["organization_id"])
    op.create_index(op.f("ix_organization_notifications_target_user_id"), "organization_notifications", ["target_user_id"])

    op.create_table(
        "organization_notification_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_notification_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_notification_id"], ["organization_notifications.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_notification_id",
            "user_id",
            name="uq_org_notification_receipt_notification_user",
        ),
    )
    op.create_index(
        "ix_org_notification_receipt_user_created",
        "organization_notification_receipts",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_organization_notification_receipts_organization_notification_id"),
        "organization_notification_receipts",
        ["organization_notification_id"],
    )
    op.create_index(op.f("ix_organization_notification_receipts_user_id"), "organization_notification_receipts", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_notification_receipts_user_id"), table_name="organization_notification_receipts")
    op.drop_index(
        op.f("ix_organization_notification_receipts_organization_notification_id"),
        table_name="organization_notification_receipts",
    )
    op.drop_index("ix_org_notification_receipt_user_created", table_name="organization_notification_receipts")
    op.drop_table("organization_notification_receipts")

    op.drop_index(op.f("ix_organization_notifications_target_user_id"), table_name="organization_notifications")
    op.drop_index(op.f("ix_organization_notifications_organization_id"), table_name="organization_notifications")
    op.drop_index(op.f("ix_organization_notifications_notification_type"), table_name="organization_notifications")
    op.drop_index(op.f("ix_organization_notifications_notification_status"), table_name="organization_notifications")
    op.drop_index(op.f("ix_organization_notifications_activity_event_id"), table_name="organization_notifications")
    op.drop_index("ix_org_notification_org_status_created", table_name="organization_notifications")
    op.drop_index("ix_org_notification_org_target_created", table_name="organization_notifications")
    op.drop_table("organization_notifications")

    op.drop_index(op.f("ix_organization_activity_events_visibility_scope"), table_name="organization_activity_events")
    op.drop_index(op.f("ix_organization_activity_events_organization_id"), table_name="organization_activity_events")
    op.drop_index(op.f("ix_organization_activity_events_actor_user_id"), table_name="organization_activity_events")
    op.drop_index(op.f("ix_organization_activity_events_activity_type"), table_name="organization_activity_events")
    op.drop_index("ix_org_activity_event_org_type_created", table_name="organization_activity_events")
    op.drop_index("ix_org_activity_event_org_created", table_name="organization_activity_events")
    op.drop_table("organization_activity_events")
