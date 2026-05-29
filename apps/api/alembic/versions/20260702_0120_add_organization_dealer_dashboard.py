"""add organization dealer operations dashboard foundation

Revision ID: 20260702_0120
Revises: 20260701_0119
Create Date: 2026-07-02 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260702_0120"
down_revision = "20260701_0119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_dealer_dashboard_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("snapshot_payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_dealer_dashboard_snapshot_org_generated",
        "organization_dealer_dashboard_snapshots",
        ["organization_id", "generated_at", "id"],
    )
    op.create_index(
        "ix_org_dealer_dashboard_snapshot_org_type_generated",
        "organization_dealer_dashboard_snapshots",
        ["organization_id", "snapshot_type", "generated_at", "id"],
    )
    op.create_index(
        op.f("ix_organization_dealer_dashboard_snapshots_organization_id"),
        "organization_dealer_dashboard_snapshots",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_organization_dealer_dashboard_snapshots_snapshot_type"),
        "organization_dealer_dashboard_snapshots",
        ["snapshot_type"],
    )

    op.create_table(
        "organization_dealer_operational_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("metric_value_json", sa.JSON(), nullable=False),
        sa.Column("metric_period", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_dealer_metric_org_key_generated",
        "organization_dealer_operational_metrics",
        ["organization_id", "metric_key", "generated_at", "id"],
    )
    op.create_index(
        "ix_org_dealer_metric_org_period_generated",
        "organization_dealer_operational_metrics",
        ["organization_id", "metric_period", "generated_at", "id"],
    )
    op.create_index(
        op.f("ix_organization_dealer_operational_metrics_metric_key"),
        "organization_dealer_operational_metrics",
        ["metric_key"],
    )
    op.create_index(
        op.f("ix_organization_dealer_operational_metrics_metric_period"),
        "organization_dealer_operational_metrics",
        ["metric_period"],
    )
    op.create_index(
        op.f("ix_organization_dealer_operational_metrics_organization_id"),
        "organization_dealer_operational_metrics",
        ["organization_id"],
    )

    op.create_table(
        "organization_dealer_dashboard_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_dealer_dashboard_event_org_created",
        "organization_dealer_dashboard_events",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_org_dealer_dashboard_event_org_type_created",
        "organization_dealer_dashboard_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_organization_dealer_dashboard_events_event_type"),
        "organization_dealer_dashboard_events",
        ["event_type"],
    )
    op.create_index(
        op.f("ix_organization_dealer_dashboard_events_organization_id"),
        "organization_dealer_dashboard_events",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_dealer_dashboard_events_organization_id"), table_name="organization_dealer_dashboard_events")
    op.drop_index(op.f("ix_organization_dealer_dashboard_events_event_type"), table_name="organization_dealer_dashboard_events")
    op.drop_index("ix_org_dealer_dashboard_event_org_type_created", table_name="organization_dealer_dashboard_events")
    op.drop_index("ix_org_dealer_dashboard_event_org_created", table_name="organization_dealer_dashboard_events")
    op.drop_table("organization_dealer_dashboard_events")

    op.drop_index(op.f("ix_organization_dealer_operational_metrics_organization_id"), table_name="organization_dealer_operational_metrics")
    op.drop_index(op.f("ix_organization_dealer_operational_metrics_metric_period"), table_name="organization_dealer_operational_metrics")
    op.drop_index(op.f("ix_organization_dealer_operational_metrics_metric_key"), table_name="organization_dealer_operational_metrics")
    op.drop_index("ix_org_dealer_metric_org_period_generated", table_name="organization_dealer_operational_metrics")
    op.drop_index("ix_org_dealer_metric_org_key_generated", table_name="organization_dealer_operational_metrics")
    op.drop_table("organization_dealer_operational_metrics")

    op.drop_index(op.f("ix_organization_dealer_dashboard_snapshots_snapshot_type"), table_name="organization_dealer_dashboard_snapshots")
    op.drop_index(op.f("ix_organization_dealer_dashboard_snapshots_organization_id"), table_name="organization_dealer_dashboard_snapshots")
    op.drop_index("ix_org_dealer_dashboard_snapshot_org_type_generated", table_name="organization_dealer_dashboard_snapshots")
    op.drop_index("ix_org_dealer_dashboard_snapshot_org_generated", table_name="organization_dealer_dashboard_snapshots")
    op.drop_table("organization_dealer_dashboard_snapshots")
