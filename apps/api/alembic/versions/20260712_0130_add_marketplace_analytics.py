"""add marketplace analytics

Revision ID: 20260712_0130
Revises: 20260711_0129
Create Date: 2026-07-12 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260712_0130"
down_revision = "20260711_0129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_analytics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=40), nullable=False),
        sa.Column("snapshot_payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_analytics_snapshot_org_generated", "marketplace_analytics_snapshots", ["organization_id", "generated_at", "id"])
    op.create_index("ix_marketplace_analytics_snapshot_org_type_generated", "marketplace_analytics_snapshots", ["organization_id", "snapshot_type", "generated_at", "id"])
    op.create_index(op.f("ix_marketplace_analytics_snapshots_organization_id"), "marketplace_analytics_snapshots", ["organization_id"])
    op.create_index(op.f("ix_marketplace_analytics_snapshots_snapshot_type"), "marketplace_analytics_snapshots", ["snapshot_type"])

    op.create_table(
        "marketplace_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=80), nullable=False),
        sa.Column("metric_value_json", sa.JSON(), nullable=False),
        sa.Column("metric_period", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_metric_org_generated", "marketplace_metrics", ["organization_id", "generated_at", "id"])
    op.create_index("ix_marketplace_metric_org_key_generated", "marketplace_metrics", ["organization_id", "metric_key", "generated_at", "id"])
    op.create_index("ix_marketplace_metric_org_period_generated", "marketplace_metrics", ["organization_id", "metric_period", "generated_at", "id"])
    op.create_index(op.f("ix_marketplace_metrics_organization_id"), "marketplace_metrics", ["organization_id"])
    op.create_index(op.f("ix_marketplace_metrics_metric_key"), "marketplace_metrics", ["metric_key"])
    op.create_index(op.f("ix_marketplace_metrics_metric_period"), "marketplace_metrics", ["metric_period"])

    op.create_table(
        "marketplace_performance_trends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trend_key", sa.String(length=80), nullable=False),
        sa.Column("trend_payload_json", sa.JSON(), nullable=False),
        sa.Column("trend_period", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_trend_org_generated", "marketplace_performance_trends", ["organization_id", "generated_at", "id"])
    op.create_index("ix_marketplace_trend_org_key_generated", "marketplace_performance_trends", ["organization_id", "trend_key", "generated_at", "id"])
    op.create_index("ix_marketplace_trend_org_period_generated", "marketplace_performance_trends", ["organization_id", "trend_period", "generated_at", "id"])
    op.create_index(op.f("ix_marketplace_performance_trends_organization_id"), "marketplace_performance_trends", ["organization_id"])
    op.create_index(op.f("ix_marketplace_performance_trends_trend_key"), "marketplace_performance_trends", ["trend_key"])
    op.create_index(op.f("ix_marketplace_performance_trends_trend_period"), "marketplace_performance_trends", ["trend_period"])

    op.create_table(
        "marketplace_analytics_events",
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
    op.create_index("ix_marketplace_analytics_event_org_created", "marketplace_analytics_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_marketplace_analytics_event_org_type_created", "marketplace_analytics_events", ["organization_id", "event_type", "created_at", "id"])
    op.create_index("ix_marketplace_analytics_event_actor_created", "marketplace_analytics_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_marketplace_analytics_events_organization_id"), "marketplace_analytics_events", ["organization_id"])
    op.create_index(op.f("ix_marketplace_analytics_events_actor_user_id"), "marketplace_analytics_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_analytics_events_event_type"), "marketplace_analytics_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_analytics_events_event_type"), table_name="marketplace_analytics_events")
    op.drop_index(op.f("ix_marketplace_analytics_events_actor_user_id"), table_name="marketplace_analytics_events")
    op.drop_index(op.f("ix_marketplace_analytics_events_organization_id"), table_name="marketplace_analytics_events")
    op.drop_index("ix_marketplace_analytics_event_actor_created", table_name="marketplace_analytics_events")
    op.drop_index("ix_marketplace_analytics_event_org_type_created", table_name="marketplace_analytics_events")
    op.drop_index("ix_marketplace_analytics_event_org_created", table_name="marketplace_analytics_events")
    op.drop_table("marketplace_analytics_events")

    op.drop_index(op.f("ix_marketplace_performance_trends_trend_period"), table_name="marketplace_performance_trends")
    op.drop_index(op.f("ix_marketplace_performance_trends_trend_key"), table_name="marketplace_performance_trends")
    op.drop_index(op.f("ix_marketplace_performance_trends_organization_id"), table_name="marketplace_performance_trends")
    op.drop_index("ix_marketplace_trend_org_period_generated", table_name="marketplace_performance_trends")
    op.drop_index("ix_marketplace_trend_org_key_generated", table_name="marketplace_performance_trends")
    op.drop_index("ix_marketplace_trend_org_generated", table_name="marketplace_performance_trends")
    op.drop_table("marketplace_performance_trends")

    op.drop_index(op.f("ix_marketplace_metrics_metric_period"), table_name="marketplace_metrics")
    op.drop_index(op.f("ix_marketplace_metrics_metric_key"), table_name="marketplace_metrics")
    op.drop_index(op.f("ix_marketplace_metrics_organization_id"), table_name="marketplace_metrics")
    op.drop_index("ix_marketplace_metric_org_period_generated", table_name="marketplace_metrics")
    op.drop_index("ix_marketplace_metric_org_key_generated", table_name="marketplace_metrics")
    op.drop_index("ix_marketplace_metric_org_generated", table_name="marketplace_metrics")
    op.drop_table("marketplace_metrics")

    op.drop_index(op.f("ix_marketplace_analytics_snapshots_snapshot_type"), table_name="marketplace_analytics_snapshots")
    op.drop_index(op.f("ix_marketplace_analytics_snapshots_organization_id"), table_name="marketplace_analytics_snapshots")
    op.drop_index("ix_marketplace_analytics_snapshot_org_type_generated", table_name="marketplace_analytics_snapshots")
    op.drop_index("ix_marketplace_analytics_snapshot_org_generated", table_name="marketplace_analytics_snapshots")
    op.drop_table("marketplace_analytics_snapshots")
