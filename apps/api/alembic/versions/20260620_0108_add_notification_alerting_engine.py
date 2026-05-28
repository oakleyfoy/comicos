"""add notification alerting engine

Revision ID: 20260620_0108
Revises: 20260619_0107
Create Date: 2026-06-20 00:10:08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260620_0108"
down_revision = "20260619_0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("notification_key", sa.String(length=120), nullable=False),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("notification_status", sa.String(length=24), nullable=False),
        sa.Column("source_event_type", sa.String(length=64), nullable=False),
        sa.Column("source_record_type", sa.String(length=64), nullable=True),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=True),
        sa.Column("notification_payload_json", sa.JSON(), nullable=False),
        sa.Column("notification_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "notification_key", name="uq_automation_notification_owner_key"),
    )
    op.create_index("ix_automation_notification_status_created", "automation_notifications", ["notification_status", "created_at", "id"])
    op.create_index("ix_automation_notification_type_created", "automation_notifications", ["notification_type", "created_at", "id"])

    op.create_table(
        "automation_notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.Integer(), nullable=False),
        sa.Column("delivery_channel", sa.String(length=32), nullable=False),
        sa.Column("delivery_status", sa.String(length=24), nullable=False),
        sa.Column("delivery_rank", sa.Integer(), nullable=False),
        sa.Column("destination_key", sa.String(length=160), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("delivery_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["automation_notifications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "delivery_channel", "destination_key", name="uq_automation_notification_delivery_dest"),
    )

    op.create_table(
        "automation_notification_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_key", sa.String(length=120), nullable=False),
        sa.Column("template_name", sa.String(length=160), nullable=False),
        sa.Column("template_category", sa.String(length=24), nullable=False),
        sa.Column("template_status", sa.String(length=24), nullable=False),
        sa.Column("subject_template", sa.String(length=512), nullable=False),
        sa.Column("body_template", sa.String(length=4096), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("template_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_key", name="uq_automation_notification_template_key"),
    )

    op.create_table(
        "automation_notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("preference_key", sa.String(length=120), nullable=False),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("delivery_channel", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("escalation_enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_hours_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "preference_key", name="uq_automation_notification_preference_owner_key"),
    )

    op.create_table(
        "automation_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_key", sa.String(length=120), nullable=False),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("alert_severity", sa.String(length=16), nullable=False),
        sa.Column("alert_status", sa.String(length=24), nullable=False),
        sa.Column("source_notification_id", sa.Integer(), nullable=True),
        sa.Column("escalation_level", sa.String(length=16), nullable=False),
        sa.Column("alert_checksum", sa.String(length=64), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_notification_id"], ["automation_notifications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_key", name="uq_automation_alert_key"),
    )

    op.create_table(
        "automation_notification_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["automation_notifications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "issue_checksum", name="uq_automation_notification_issue_checksum"),
    )

    op.create_table(
        "automation_notification_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_id", sa.Integer(), nullable=True),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["automation_notifications.id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["automation_alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", "event_checksum", name="uq_automation_notification_history_checksum"),
    )


def downgrade() -> None:
    op.drop_table("automation_notification_history")
    op.drop_table("automation_notification_issues")
    op.drop_table("automation_alerts")
    op.drop_table("automation_notification_preferences")
    op.drop_table("automation_notification_templates")
    op.drop_table("automation_notification_deliveries")
    op.drop_table("automation_notifications")
