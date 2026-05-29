"""add mobile ops dashboard

Revision ID: 20260718_0136
Revises: 20260717_0135
Create Date: 2026-07-18 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260718_0136"
down_revision = "20260717_0135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_ops_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=40), nullable=False),
        sa.Column("snapshot_payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_ops_snapshot_org_generated", "mobile_ops_snapshots", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mobile_ops_snapshot_org_type_generated",
        "mobile_ops_snapshots",
        ["organization_id", "snapshot_type", "generated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_ops_snapshots_organization_id"), "mobile_ops_snapshots", ["organization_id"])
    op.create_index(op.f("ix_mobile_ops_snapshots_snapshot_type"), "mobile_ops_snapshots", ["snapshot_type"])

    op.create_table(
        "mobile_ops_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_json", sa.JSON(), nullable=False),
        sa.Column("metric_period", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_ops_metric_org_generated", "mobile_ops_metrics", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mobile_ops_metric_org_key_generated",
        "mobile_ops_metrics",
        ["organization_id", "metric_key", "generated_at", "id"],
    )
    op.create_index(
        "ix_mobile_ops_metric_org_period_generated",
        "mobile_ops_metrics",
        ["organization_id", "metric_period", "generated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_ops_metrics_organization_id"), "mobile_ops_metrics", ["organization_id"])
    op.create_index(op.f("ix_mobile_ops_metrics_metric_key"), "mobile_ops_metrics", ["metric_key"])
    op.create_index(op.f("ix_mobile_ops_metrics_metric_period"), "mobile_ops_metrics", ["metric_period"])

    op.create_table(
        "mobile_ops_diagnostics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("diagnostic_category", sa.String(length=32), nullable=False),
        sa.Column("diagnostic_status", sa.String(length=16), nullable=False),
        sa.Column("diagnostic_code", sa.String(length=80), nullable=False),
        sa.Column("diagnostic_message", sa.String(length=1000), nullable=False),
        sa.Column("diagnostic_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_ops_diag_org_created", "mobile_ops_diagnostics", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_ops_diag_org_category_created",
        "mobile_ops_diagnostics",
        ["organization_id", "diagnostic_category", "created_at", "id"],
    )
    op.create_index(
        "ix_mobile_ops_diag_org_status_created",
        "mobile_ops_diagnostics",
        ["organization_id", "diagnostic_status", "created_at", "id"],
    )
    op.create_index(
        "ix_mobile_ops_diag_org_code_created",
        "mobile_ops_diagnostics",
        ["organization_id", "diagnostic_code", "created_at", "id"],
    )
    op.create_index(op.f("ix_mobile_ops_diagnostics_organization_id"), "mobile_ops_diagnostics", ["organization_id"])
    op.create_index(op.f("ix_mobile_ops_diagnostics_diagnostic_category"), "mobile_ops_diagnostics", ["diagnostic_category"])
    op.create_index(op.f("ix_mobile_ops_diagnostics_diagnostic_status"), "mobile_ops_diagnostics", ["diagnostic_status"])
    op.create_index(op.f("ix_mobile_ops_diagnostics_diagnostic_code"), "mobile_ops_diagnostics", ["diagnostic_code"])

    op.create_table(
        "mobile_ops_events",
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
    op.create_index("ix_mobile_ops_event_org_created", "mobile_ops_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_ops_event_org_type_created",
        "mobile_ops_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_mobile_ops_event_actor_created", "mobile_ops_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_mobile_ops_events_organization_id"), "mobile_ops_events", ["organization_id"])
    op.create_index(op.f("ix_mobile_ops_events_actor_user_id"), "mobile_ops_events", ["actor_user_id"])
    op.create_index(op.f("ix_mobile_ops_events_event_type"), "mobile_ops_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mobile_ops_events_event_type"), table_name="mobile_ops_events")
    op.drop_index(op.f("ix_mobile_ops_events_actor_user_id"), table_name="mobile_ops_events")
    op.drop_index(op.f("ix_mobile_ops_events_organization_id"), table_name="mobile_ops_events")
    op.drop_index("ix_mobile_ops_event_actor_created", table_name="mobile_ops_events")
    op.drop_index("ix_mobile_ops_event_org_type_created", table_name="mobile_ops_events")
    op.drop_index("ix_mobile_ops_event_org_created", table_name="mobile_ops_events")
    op.drop_table("mobile_ops_events")

    op.drop_index(op.f("ix_mobile_ops_diagnostics_diagnostic_code"), table_name="mobile_ops_diagnostics")
    op.drop_index(op.f("ix_mobile_ops_diagnostics_diagnostic_status"), table_name="mobile_ops_diagnostics")
    op.drop_index(op.f("ix_mobile_ops_diagnostics_diagnostic_category"), table_name="mobile_ops_diagnostics")
    op.drop_index(op.f("ix_mobile_ops_diagnostics_organization_id"), table_name="mobile_ops_diagnostics")
    op.drop_index("ix_mobile_ops_diag_org_code_created", table_name="mobile_ops_diagnostics")
    op.drop_index("ix_mobile_ops_diag_org_status_created", table_name="mobile_ops_diagnostics")
    op.drop_index("ix_mobile_ops_diag_org_category_created", table_name="mobile_ops_diagnostics")
    op.drop_index("ix_mobile_ops_diag_org_created", table_name="mobile_ops_diagnostics")
    op.drop_table("mobile_ops_diagnostics")

    op.drop_index(op.f("ix_mobile_ops_metrics_metric_period"), table_name="mobile_ops_metrics")
    op.drop_index(op.f("ix_mobile_ops_metrics_metric_key"), table_name="mobile_ops_metrics")
    op.drop_index(op.f("ix_mobile_ops_metrics_organization_id"), table_name="mobile_ops_metrics")
    op.drop_index("ix_mobile_ops_metric_org_period_generated", table_name="mobile_ops_metrics")
    op.drop_index("ix_mobile_ops_metric_org_key_generated", table_name="mobile_ops_metrics")
    op.drop_index("ix_mobile_ops_metric_org_generated", table_name="mobile_ops_metrics")
    op.drop_table("mobile_ops_metrics")

    op.drop_index(op.f("ix_mobile_ops_snapshots_snapshot_type"), table_name="mobile_ops_snapshots")
    op.drop_index(op.f("ix_mobile_ops_snapshots_organization_id"), table_name="mobile_ops_snapshots")
    op.drop_index("ix_mobile_ops_snapshot_org_type_generated", table_name="mobile_ops_snapshots")
    op.drop_index("ix_mobile_ops_snapshot_org_generated", table_name="mobile_ops_snapshots")
    op.drop_table("mobile_ops_snapshots")
