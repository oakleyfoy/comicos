"""add offline inventory engine

Revision ID: 20260714_0132
Revises: 20260713_0131
Create Date: 2026-07-14 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260714_0132"
down_revision = "20260713_0131"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offline_inventory_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("local_record_identifier", sa.String(length=128), nullable=False),
        sa.Column("record_payload_json", sa.JSON(), nullable=False),
        sa.Column("local_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "local_record_identifier", name="uq_offline_inventory_org_local_id"),
    )
    op.create_index("ix_offline_inventory_record_org_created", "offline_inventory_records", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_offline_inventory_record_org_local_updated",
        "offline_inventory_records",
        ["organization_id", "local_updated_at", "id"],
    )
    op.create_index(op.f("ix_offline_inventory_records_organization_id"), "offline_inventory_records", ["organization_id"])
    op.create_index(op.f("ix_offline_inventory_records_inventory_item_id"), "offline_inventory_records", ["inventory_item_id"])
    op.create_index(op.f("ix_offline_inventory_records_local_record_identifier"), "offline_inventory_records", ["local_record_identifier"])

    op.create_table(
        "offline_inventory_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(length=24), nullable=False),
        sa.Column("change_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offline_inventory_change_org_created", "offline_inventory_changes", ["organization_id", "created_at", "id"])
    op.create_index("ix_offline_inventory_change_device_created", "offline_inventory_changes", ["device_id", "created_at", "id"])
    op.create_index(
        "ix_offline_inventory_change_org_type_created",
        "offline_inventory_changes",
        ["organization_id", "change_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_offline_inventory_changes_organization_id"), "offline_inventory_changes", ["organization_id"])
    op.create_index(op.f("ix_offline_inventory_changes_device_id"), "offline_inventory_changes", ["device_id"])
    op.create_index(op.f("ix_offline_inventory_changes_inventory_item_id"), "offline_inventory_changes", ["inventory_item_id"])
    op.create_index(op.f("ix_offline_inventory_changes_change_type"), "offline_inventory_changes", ["change_type"])

    op.create_table(
        "offline_sync_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("queue_status", sa.String(length=24), nullable=False),
        sa.Column("queue_payload_json", sa.JSON(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offline_sync_queue_org_queued", "offline_sync_queue", ["organization_id", "queued_at", "id"])
    op.create_index("ix_offline_sync_queue_device_queued", "offline_sync_queue", ["device_id", "queued_at", "id"])
    op.create_index(
        "ix_offline_sync_queue_org_status_queued",
        "offline_sync_queue",
        ["organization_id", "queue_status", "queued_at", "id"],
    )
    op.create_index(op.f("ix_offline_sync_queue_organization_id"), "offline_sync_queue", ["organization_id"])
    op.create_index(op.f("ix_offline_sync_queue_device_id"), "offline_sync_queue", ["device_id"])
    op.create_index(op.f("ix_offline_sync_queue_queue_status"), "offline_sync_queue", ["queue_status"])

    op.create_table(
        "offline_sync_conflicts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("conflict_type", sa.String(length=32), nullable=False),
        sa.Column("local_payload_json", sa.JSON(), nullable=False),
        sa.Column("server_payload_json", sa.JSON(), nullable=False),
        sa.Column("conflict_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offline_sync_conflict_org_created", "offline_sync_conflicts", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_offline_sync_conflict_org_status_created",
        "offline_sync_conflicts",
        ["organization_id", "conflict_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_offline_sync_conflicts_organization_id"), "offline_sync_conflicts", ["organization_id"])
    op.create_index(op.f("ix_offline_sync_conflicts_inventory_item_id"), "offline_sync_conflicts", ["inventory_item_id"])
    op.create_index(op.f("ix_offline_sync_conflicts_conflict_type"), "offline_sync_conflicts", ["conflict_type"])
    op.create_index(op.f("ix_offline_sync_conflicts_conflict_status"), "offline_sync_conflicts", ["conflict_status"])

    op.create_table(
        "offline_inventory_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offline_inventory_event_org_created", "offline_inventory_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_offline_inventory_event_org_type_created",
        "offline_inventory_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_offline_inventory_event_actor_created", "offline_inventory_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_offline_inventory_events_organization_id"), "offline_inventory_events", ["organization_id"])
    op.create_index(op.f("ix_offline_inventory_events_actor_user_id"), "offline_inventory_events", ["actor_user_id"])
    op.create_index(op.f("ix_offline_inventory_events_event_type"), "offline_inventory_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_offline_inventory_events_event_type"), table_name="offline_inventory_events")
    op.drop_index(op.f("ix_offline_inventory_events_actor_user_id"), table_name="offline_inventory_events")
    op.drop_index(op.f("ix_offline_inventory_events_organization_id"), table_name="offline_inventory_events")
    op.drop_index("ix_offline_inventory_event_actor_created", table_name="offline_inventory_events")
    op.drop_index("ix_offline_inventory_event_org_type_created", table_name="offline_inventory_events")
    op.drop_index("ix_offline_inventory_event_org_created", table_name="offline_inventory_events")
    op.drop_table("offline_inventory_events")

    op.drop_index(op.f("ix_offline_sync_conflicts_conflict_status"), table_name="offline_sync_conflicts")
    op.drop_index(op.f("ix_offline_sync_conflicts_conflict_type"), table_name="offline_sync_conflicts")
    op.drop_index(op.f("ix_offline_sync_conflicts_inventory_item_id"), table_name="offline_sync_conflicts")
    op.drop_index(op.f("ix_offline_sync_conflicts_organization_id"), table_name="offline_sync_conflicts")
    op.drop_index("ix_offline_sync_conflict_org_status_created", table_name="offline_sync_conflicts")
    op.drop_index("ix_offline_sync_conflict_org_created", table_name="offline_sync_conflicts")
    op.drop_table("offline_sync_conflicts")

    op.drop_index(op.f("ix_offline_sync_queue_queue_status"), table_name="offline_sync_queue")
    op.drop_index(op.f("ix_offline_sync_queue_device_id"), table_name="offline_sync_queue")
    op.drop_index(op.f("ix_offline_sync_queue_organization_id"), table_name="offline_sync_queue")
    op.drop_index("ix_offline_sync_queue_org_status_queued", table_name="offline_sync_queue")
    op.drop_index("ix_offline_sync_queue_device_queued", table_name="offline_sync_queue")
    op.drop_index("ix_offline_sync_queue_org_queued", table_name="offline_sync_queue")
    op.drop_table("offline_sync_queue")

    op.drop_index(op.f("ix_offline_inventory_changes_change_type"), table_name="offline_inventory_changes")
    op.drop_index(op.f("ix_offline_inventory_changes_inventory_item_id"), table_name="offline_inventory_changes")
    op.drop_index(op.f("ix_offline_inventory_changes_device_id"), table_name="offline_inventory_changes")
    op.drop_index(op.f("ix_offline_inventory_changes_organization_id"), table_name="offline_inventory_changes")
    op.drop_index("ix_offline_inventory_change_org_type_created", table_name="offline_inventory_changes")
    op.drop_index("ix_offline_inventory_change_device_created", table_name="offline_inventory_changes")
    op.drop_index("ix_offline_inventory_change_org_created", table_name="offline_inventory_changes")
    op.drop_table("offline_inventory_changes")

    op.drop_index(op.f("ix_offline_inventory_records_local_record_identifier"), table_name="offline_inventory_records")
    op.drop_index(op.f("ix_offline_inventory_records_inventory_item_id"), table_name="offline_inventory_records")
    op.drop_index(op.f("ix_offline_inventory_records_organization_id"), table_name="offline_inventory_records")
    op.drop_index("ix_offline_inventory_record_org_local_updated", table_name="offline_inventory_records")
    op.drop_index("ix_offline_inventory_record_org_created", table_name="offline_inventory_records")
    op.drop_table("offline_inventory_records")
