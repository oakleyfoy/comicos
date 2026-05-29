"""add mobile analytics

Revision ID: 20260720_0138
Revises: 20260719_0137
Create Date: 2026-07-20 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260720_0138"
down_revision = "20260719_0137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_analytics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=40), nullable=False),
        sa.Column("snapshot_payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_analytics_snapshot_org_generated", "mobile_analytics_snapshots", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mobile_analytics_snapshot_org_type_generated",
        "mobile_analytics_snapshots",
        ["organization_id", "snapshot_type", "generated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_analytics_snapshots_organization_id"), "mobile_analytics_snapshots", ["organization_id"])
    op.create_index(op.f("ix_mobile_analytics_snapshots_snapshot_type"), "mobile_analytics_snapshots", ["snapshot_type"])

    op.create_table(
        "mobile_usage_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_json", sa.JSON(), nullable=False),
        sa.Column("metric_period", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_usage_metric_org_generated", "mobile_usage_metrics", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mobile_usage_metric_org_key_generated",
        "mobile_usage_metrics",
        ["organization_id", "metric_key", "generated_at", "id"],
    )
    op.create_index(
        "ix_mobile_usage_metric_org_period_generated",
        "mobile_usage_metrics",
        ["organization_id", "metric_period", "generated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_usage_metrics_organization_id"), "mobile_usage_metrics", ["organization_id"])
    op.create_index(op.f("ix_mobile_usage_metrics_metric_key"), "mobile_usage_metrics", ["metric_key"])
    op.create_index(op.f("ix_mobile_usage_metrics_metric_period"), "mobile_usage_metrics", ["metric_period"])

    op.create_table(
        "mobile_usage_trends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trend_key", sa.String(length=80), nullable=False),
        sa.Column("trend_payload_json", sa.JSON(), nullable=False),
        sa.Column("trend_period", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mobile_usage_trend_org_generated", "mobile_usage_trends", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mobile_usage_trend_org_key_generated",
        "mobile_usage_trends",
        ["organization_id", "trend_key", "generated_at", "id"],
    )
    op.create_index(
        "ix_mobile_usage_trend_org_period_generated",
        "mobile_usage_trends",
        ["organization_id", "trend_period", "generated_at", "id"],
    )
    op.create_index(op.f("ix_mobile_usage_trends_organization_id"), "mobile_usage_trends", ["organization_id"])
    op.create_index(op.f("ix_mobile_usage_trends_trend_key"), "mobile_usage_trends", ["trend_key"])
    op.create_index(op.f("ix_mobile_usage_trends_trend_period"), "mobile_usage_trends", ["trend_period"])

    op.create_table(
        "mobile_analytics_events",
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
    op.create_index("ix_mobile_analytics_event_org_created", "mobile_analytics_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mobile_analytics_event_org_type_created",
        "mobile_analytics_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_mobile_analytics_event_actor_created", "mobile_analytics_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_mobile_analytics_events_organization_id"), "mobile_analytics_events", ["organization_id"])
    op.create_index(op.f("ix_mobile_analytics_events_actor_user_id"), "mobile_analytics_events", ["actor_user_id"])
    op.create_index(op.f("ix_mobile_analytics_events_event_type"), "mobile_analytics_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mobile_analytics_events_event_type"), table_name="mobile_analytics_events")
    op.drop_index(op.f("ix_mobile_analytics_events_actor_user_id"), table_name="mobile_analytics_events")
    op.drop_index(op.f("ix_mobile_analytics_events_organization_id"), table_name="mobile_analytics_events")
    op.drop_index("ix_mobile_analytics_event_actor_created", table_name="mobile_analytics_events")
    op.drop_index("ix_mobile_analytics_event_org_type_created", table_name="mobile_analytics_events")
    op.drop_index("ix_mobile_analytics_event_org_created", table_name="mobile_analytics_events")
    op.drop_table("mobile_analytics_events")

    op.drop_index(op.f("ix_mobile_usage_trends_trend_period"), table_name="mobile_usage_trends")
    op.drop_index(op.f("ix_mobile_usage_trends_trend_key"), table_name="mobile_usage_trends")
    op.drop_index(op.f("ix_mobile_usage_trends_organization_id"), table_name="mobile_usage_trends")
    op.drop_index("ix_mobile_usage_trend_org_period_generated", table_name="mobile_usage_trends")
    op.drop_index("ix_mobile_usage_trend_org_key_generated", table_name="mobile_usage_trends")
    op.drop_index("ix_mobile_usage_trend_org_generated", table_name="mobile_usage_trends")
    op.drop_table("mobile_usage_trends")

    op.drop_index(op.f("ix_mobile_usage_metrics_metric_period"), table_name="mobile_usage_metrics")
    op.drop_index(op.f("ix_mobile_usage_metrics_metric_key"), table_name="mobile_usage_metrics")
    op.drop_index(op.f("ix_mobile_usage_metrics_organization_id"), table_name="mobile_usage_metrics")
    op.drop_index("ix_mobile_usage_metric_org_period_generated", table_name="mobile_usage_metrics")
    op.drop_index("ix_mobile_usage_metric_org_key_generated", table_name="mobile_usage_metrics")
    op.drop_index("ix_mobile_usage_metric_org_generated", table_name="mobile_usage_metrics")
    op.drop_table("mobile_usage_metrics")

    op.drop_index(op.f("ix_mobile_analytics_snapshots_snapshot_type"), table_name="mobile_analytics_snapshots")
    op.drop_index(op.f("ix_mobile_analytics_snapshots_organization_id"), table_name="mobile_analytics_snapshots")
    op.drop_index("ix_mobile_analytics_snapshot_org_type_generated", table_name="mobile_analytics_snapshots")
    op.drop_index("ix_mobile_analytics_snapshot_org_generated", table_name="mobile_analytics_snapshots")
    op.drop_table("mobile_analytics_snapshots")
