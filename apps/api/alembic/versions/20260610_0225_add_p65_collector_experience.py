"""add P65 collector experience platform tables

Revision ID: 20260610_0225
Revises: 20260609_0224
Create Date: 2026-06-10 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260610_0225"
down_revision = "20260609_0224"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_task_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_task_snap_owner_gen", "collector_task_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "collector_task_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_ref_json", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("action_hint", sa.String(length=64), nullable=False),
        sa.Column("status_history_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["collector_task_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_task_item_snap_type", "collector_task_item", ["snapshot_id", "task_type", "status", "id"])

    op.create_table(
        "collector_narrative_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("week_start", sa.String(length=16), nullable=False),
        sa.Column("readiness_status", sa.String(length=16), nullable=False),
        sa.Column("briefing_markdown", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_narrative_owner_gen", "collector_narrative_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "collector_narrative_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("narrative_kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("narrative_text", sa.Text(), nullable=False),
        sa.Column("signal_citations_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["collector_narrative_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_narrative_item_snap", "collector_narrative_item", ["snapshot_id", "narrative_kind", "id"])

    op.create_table(
        "automation_subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("automation_kind", sa.String(length=32), nullable=False),
        sa.Column("delivery_type", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_sub_owner_kind", "automation_subscription", ["owner_user_id", "automation_kind", "id"])

    op.create_table(
        "automation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("automation_kind", sa.String(length=32), nullable=False),
        sa.Column("delivery_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["automation_subscription.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_run_owner_started", "automation_run", ["owner_user_id", "started_at", "id"])

    op.create_table(
        "notification_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_snap_owner_gen", "notification_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "notification_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("deep_link", sa.String(length=256), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["notification_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_item_snap_status", "notification_item", ["snapshot_id", "status", "id"])


def downgrade() -> None:
    op.drop_index("ix_notification_item_snap_status", table_name="notification_item")
    op.drop_table("notification_item")
    op.drop_index("ix_notification_snap_owner_gen", table_name="notification_snapshot")
    op.drop_table("notification_snapshot")
    op.drop_index("ix_automation_run_owner_started", table_name="automation_run")
    op.drop_table("automation_run")
    op.drop_index("ix_automation_sub_owner_kind", table_name="automation_subscription")
    op.drop_table("automation_subscription")
    op.drop_index("ix_collector_narrative_item_snap", table_name="collector_narrative_item")
    op.drop_table("collector_narrative_item")
    op.drop_index("ix_collector_narrative_owner_gen", table_name="collector_narrative_snapshot")
    op.drop_table("collector_narrative_snapshot")
    op.drop_index("ix_collector_task_item_snap_type", table_name="collector_task_item")
    op.drop_table("collector_task_item")
    op.drop_index("ix_collector_task_snap_owner_gen", table_name="collector_task_snapshot")
    op.drop_table("collector_task_snapshot")
