"""add marketplace event processing foundation

Revision ID: 20260708_0126
Revises: 20260707_0125
Create Date: 2026-07-08 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260708_0126"
down_revision = "20260707_0125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_type", sa.String(length=32), nullable=False),
        sa.Column("external_event_identifier", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_status", sa.String(length=24), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_account_id", "external_event_identifier", name="uq_marketplace_event_identity"),
    )
    op.create_index("ix_marketplace_event_org_received", "marketplace_events", ["organization_id", "received_at", "id"])
    op.create_index(
        "ix_marketplace_event_org_account_received",
        "marketplace_events",
        ["organization_id", "marketplace_account_id", "received_at", "id"],
    )
    op.create_index(
        "ix_marketplace_event_org_status_received",
        "marketplace_events",
        ["organization_id", "event_status", "received_at", "id"],
    )
    op.create_index("ix_marketplace_event_org_type_received", "marketplace_events", ["organization_id", "event_type", "received_at", "id"])
    op.create_index(op.f("ix_marketplace_events_external_event_identifier"), "marketplace_events", ["external_event_identifier"])
    op.create_index(op.f("ix_marketplace_events_event_status"), "marketplace_events", ["event_status"])
    op.create_index(op.f("ix_marketplace_events_event_type"), "marketplace_events", ["event_type"])
    op.create_index(op.f("ix_marketplace_events_marketplace_account_id"), "marketplace_events", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_events_marketplace_type"), "marketplace_events", ["marketplace_type"])
    op.create_index(op.f("ix_marketplace_events_organization_id"), "marketplace_events", ["organization_id"])

    op.create_table(
        "marketplace_webhook_endpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("endpoint_type", sa.String(length=32), nullable=False),
        sa.Column("endpoint_status", sa.String(length=24), nullable=False),
        sa.Column("endpoint_identifier", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "endpoint_identifier", name="uq_marketplace_webhook_endpoint_identity"),
    )
    op.create_index("ix_marketplace_webhook_endpoint_org_created", "marketplace_webhook_endpoints", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_marketplace_webhook_endpoint_org_status_created",
        "marketplace_webhook_endpoints",
        ["organization_id", "endpoint_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_webhook_endpoints_endpoint_identifier"), "marketplace_webhook_endpoints", ["endpoint_identifier"])
    op.create_index(op.f("ix_marketplace_webhook_endpoints_endpoint_status"), "marketplace_webhook_endpoints", ["endpoint_status"])
    op.create_index(op.f("ix_marketplace_webhook_endpoints_endpoint_type"), "marketplace_webhook_endpoints", ["endpoint_type"])
    op.create_index(op.f("ix_marketplace_webhook_endpoints_marketplace_account_id"), "marketplace_webhook_endpoints", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_webhook_endpoints_organization_id"), "marketplace_webhook_endpoints", ["organization_id"])

    op.create_table(
        "marketplace_event_processing_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_event_id", sa.Integer(), nullable=False),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("processing_result_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["marketplace_event_id"], ["marketplace_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_event_run_org_started", "marketplace_event_processing_runs", ["organization_id", "started_at", "id"])
    op.create_index(
        "ix_marketplace_event_run_event_started",
        "marketplace_event_processing_runs",
        ["marketplace_event_id", "started_at", "id"],
    )
    op.create_index(
        "ix_marketplace_event_run_org_status_started",
        "marketplace_event_processing_runs",
        ["organization_id", "processing_status", "started_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_event_processing_runs_marketplace_event_id"), "marketplace_event_processing_runs", ["marketplace_event_id"])
    op.create_index(op.f("ix_marketplace_event_processing_runs_processing_status"), "marketplace_event_processing_runs", ["processing_status"])
    op.create_index(op.f("ix_marketplace_event_processing_runs_organization_id"), "marketplace_event_processing_runs", ["organization_id"])

    op.create_table(
        "marketplace_event_lineage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_event_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("lineage_event_type", sa.String(length=80), nullable=False),
        sa.Column("lineage_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_event_id"], ["marketplace_events.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_event_lineage_org_created", "marketplace_event_lineage", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_marketplace_event_lineage_event_created",
        "marketplace_event_lineage",
        ["marketplace_event_id", "created_at", "id"],
    )
    op.create_index(
        "ix_marketplace_event_lineage_org_type_created",
        "marketplace_event_lineage",
        ["organization_id", "lineage_event_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_event_lineage_actor_user_id"), "marketplace_event_lineage", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_event_lineage_lineage_event_type"), "marketplace_event_lineage", ["lineage_event_type"])
    op.create_index(op.f("ix_marketplace_event_lineage_marketplace_event_id"), "marketplace_event_lineage", ["marketplace_event_id"])
    op.create_index(op.f("ix_marketplace_event_lineage_organization_id"), "marketplace_event_lineage", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_event_lineage_organization_id"), table_name="marketplace_event_lineage")
    op.drop_index(op.f("ix_marketplace_event_lineage_marketplace_event_id"), table_name="marketplace_event_lineage")
    op.drop_index(op.f("ix_marketplace_event_lineage_lineage_event_type"), table_name="marketplace_event_lineage")
    op.drop_index(op.f("ix_marketplace_event_lineage_actor_user_id"), table_name="marketplace_event_lineage")
    op.drop_index("ix_marketplace_event_lineage_org_type_created", table_name="marketplace_event_lineage")
    op.drop_index("ix_marketplace_event_lineage_event_created", table_name="marketplace_event_lineage")
    op.drop_index("ix_marketplace_event_lineage_org_created", table_name="marketplace_event_lineage")
    op.drop_table("marketplace_event_lineage")

    op.drop_index(op.f("ix_marketplace_event_processing_runs_organization_id"), table_name="marketplace_event_processing_runs")
    op.drop_index(op.f("ix_marketplace_event_processing_runs_processing_status"), table_name="marketplace_event_processing_runs")
    op.drop_index(op.f("ix_marketplace_event_processing_runs_marketplace_event_id"), table_name="marketplace_event_processing_runs")
    op.drop_index("ix_marketplace_event_run_org_status_started", table_name="marketplace_event_processing_runs")
    op.drop_index("ix_marketplace_event_run_event_started", table_name="marketplace_event_processing_runs")
    op.drop_index("ix_marketplace_event_run_org_started", table_name="marketplace_event_processing_runs")
    op.drop_table("marketplace_event_processing_runs")

    op.drop_index(op.f("ix_marketplace_webhook_endpoints_organization_id"), table_name="marketplace_webhook_endpoints")
    op.drop_index(op.f("ix_marketplace_webhook_endpoints_marketplace_account_id"), table_name="marketplace_webhook_endpoints")
    op.drop_index(op.f("ix_marketplace_webhook_endpoints_endpoint_type"), table_name="marketplace_webhook_endpoints")
    op.drop_index(op.f("ix_marketplace_webhook_endpoints_endpoint_status"), table_name="marketplace_webhook_endpoints")
    op.drop_index(op.f("ix_marketplace_webhook_endpoints_endpoint_identifier"), table_name="marketplace_webhook_endpoints")
    op.drop_index("ix_marketplace_webhook_endpoint_org_status_created", table_name="marketplace_webhook_endpoints")
    op.drop_index("ix_marketplace_webhook_endpoint_org_created", table_name="marketplace_webhook_endpoints")
    op.drop_table("marketplace_webhook_endpoints")

    op.drop_index(op.f("ix_marketplace_events_organization_id"), table_name="marketplace_events")
    op.drop_index(op.f("ix_marketplace_events_marketplace_type"), table_name="marketplace_events")
    op.drop_index(op.f("ix_marketplace_events_marketplace_account_id"), table_name="marketplace_events")
    op.drop_index(op.f("ix_marketplace_events_event_type"), table_name="marketplace_events")
    op.drop_index(op.f("ix_marketplace_events_event_status"), table_name="marketplace_events")
    op.drop_index(op.f("ix_marketplace_events_external_event_identifier"), table_name="marketplace_events")
    op.drop_index("ix_marketplace_event_org_type_received", table_name="marketplace_events")
    op.drop_index("ix_marketplace_event_org_status_received", table_name="marketplace_events")
    op.drop_index("ix_marketplace_event_org_account_received", table_name="marketplace_events")
    op.drop_index("ix_marketplace_event_org_received", table_name="marketplace_events")
    op.drop_table("marketplace_events")
