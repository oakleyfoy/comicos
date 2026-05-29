"""add mobile scanning

Revision ID: 20260715_0133
Revises: 20260714_0132
Create Date: 2026-07-15 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260715_0133"
down_revision = "20260714_0132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_captures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("scan_type", sa.String(length=32), nullable=False),
        sa.Column("scan_value", sa.String(length=512), nullable=False),
        sa.Column("normalized_value", sa.String(length=512), nullable=False),
        sa.Column("scan_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["mobile_devices.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_capture_org_created", "scan_captures", ["organization_id", "created_at", "id"])
    op.create_index("ix_scan_capture_device_created", "scan_captures", ["device_id", "created_at", "id"])
    op.create_index("ix_scan_capture_org_status_created", "scan_captures", ["organization_id", "scan_status", "created_at", "id"])
    op.create_index("ix_scan_capture_org_normalized", "scan_captures", ["organization_id", "normalized_value", "created_at", "id"])
    op.create_index(op.f("ix_scan_captures_organization_id"), "scan_captures", ["organization_id"])
    op.create_index(op.f("ix_scan_captures_device_id"), "scan_captures", ["device_id"])
    op.create_index(op.f("ix_scan_captures_scan_type"), "scan_captures", ["scan_type"])
    op.create_index(op.f("ix_scan_captures_normalized_value"), "scan_captures", ["normalized_value"])
    op.create_index(op.f("ix_scan_captures_scan_status"), "scan_captures", ["scan_status"])

    op.create_table(
        "scan_lookup_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("scan_capture_id", sa.Integer(), nullable=False),
        sa.Column("lookup_type", sa.String(length=32), nullable=False),
        sa.Column("lookup_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["scan_capture_id"], ["scan_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_lookup_org_created", "scan_lookup_results", ["organization_id", "created_at", "id"])
    op.create_index("ix_scan_lookup_capture_created", "scan_lookup_results", ["scan_capture_id", "created_at", "id"])
    op.create_index("ix_scan_lookup_org_type_created", "scan_lookup_results", ["organization_id", "lookup_type", "created_at", "id"])
    op.create_index(op.f("ix_scan_lookup_results_organization_id"), "scan_lookup_results", ["organization_id"])
    op.create_index(op.f("ix_scan_lookup_results_scan_capture_id"), "scan_lookup_results", ["scan_capture_id"])
    op.create_index(op.f("ix_scan_lookup_results_lookup_type"), "scan_lookup_results", ["lookup_type"])

    op.create_table(
        "intake_staging_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("scan_capture_id", sa.Integer(), nullable=False),
        sa.Column("staging_status", sa.String(length=24), nullable=False),
        sa.Column("staging_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["scan_capture_id"], ["scan_captures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intake_staging_org_created", "intake_staging_records", ["organization_id", "created_at", "id"])
    op.create_index("ix_intake_staging_capture_created", "intake_staging_records", ["scan_capture_id", "created_at", "id"])
    op.create_index("ix_intake_staging_org_status_created", "intake_staging_records", ["organization_id", "staging_status", "created_at", "id"])
    op.create_index(op.f("ix_intake_staging_records_organization_id"), "intake_staging_records", ["organization_id"])
    op.create_index(op.f("ix_intake_staging_records_scan_capture_id"), "intake_staging_records", ["scan_capture_id"])
    op.create_index(op.f("ix_intake_staging_records_staging_status"), "intake_staging_records", ["staging_status"])

    op.create_table(
        "scan_events",
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
    op.create_index("ix_scan_event_org_created", "scan_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_scan_event_org_type_created", "scan_events", ["organization_id", "event_type", "created_at", "id"])
    op.create_index("ix_scan_event_actor_created", "scan_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_scan_events_organization_id"), "scan_events", ["organization_id"])
    op.create_index(op.f("ix_scan_events_actor_user_id"), "scan_events", ["actor_user_id"])
    op.create_index(op.f("ix_scan_events_event_type"), "scan_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_scan_events_event_type"), table_name="scan_events")
    op.drop_index(op.f("ix_scan_events_actor_user_id"), table_name="scan_events")
    op.drop_index(op.f("ix_scan_events_organization_id"), table_name="scan_events")
    op.drop_index("ix_scan_event_actor_created", table_name="scan_events")
    op.drop_index("ix_scan_event_org_type_created", table_name="scan_events")
    op.drop_index("ix_scan_event_org_created", table_name="scan_events")
    op.drop_table("scan_events")

    op.drop_index(op.f("ix_intake_staging_records_staging_status"), table_name="intake_staging_records")
    op.drop_index(op.f("ix_intake_staging_records_scan_capture_id"), table_name="intake_staging_records")
    op.drop_index(op.f("ix_intake_staging_records_organization_id"), table_name="intake_staging_records")
    op.drop_index("ix_intake_staging_org_status_created", table_name="intake_staging_records")
    op.drop_index("ix_intake_staging_capture_created", table_name="intake_staging_records")
    op.drop_index("ix_intake_staging_org_created", table_name="intake_staging_records")
    op.drop_table("intake_staging_records")

    op.drop_index(op.f("ix_scan_lookup_results_lookup_type"), table_name="scan_lookup_results")
    op.drop_index(op.f("ix_scan_lookup_results_scan_capture_id"), table_name="scan_lookup_results")
    op.drop_index(op.f("ix_scan_lookup_results_organization_id"), table_name="scan_lookup_results")
    op.drop_index("ix_scan_lookup_org_type_created", table_name="scan_lookup_results")
    op.drop_index("ix_scan_lookup_capture_created", table_name="scan_lookup_results")
    op.drop_index("ix_scan_lookup_org_created", table_name="scan_lookup_results")
    op.drop_table("scan_lookup_results")

    op.drop_index(op.f("ix_scan_captures_scan_status"), table_name="scan_captures")
    op.drop_index(op.f("ix_scan_captures_normalized_value"), table_name="scan_captures")
    op.drop_index(op.f("ix_scan_captures_scan_type"), table_name="scan_captures")
    op.drop_index(op.f("ix_scan_captures_device_id"), table_name="scan_captures")
    op.drop_index(op.f("ix_scan_captures_organization_id"), table_name="scan_captures")
    op.drop_index("ix_scan_capture_org_normalized", table_name="scan_captures")
    op.drop_index("ix_scan_capture_org_status_created", table_name="scan_captures")
    op.drop_index("ix_scan_capture_device_created", table_name="scan_captures")
    op.drop_index("ix_scan_capture_org_created", table_name="scan_captures")
    op.drop_table("scan_captures")
