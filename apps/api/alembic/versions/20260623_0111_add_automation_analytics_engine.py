"""add automation analytics engine

Revision ID: 20260623_0111
Revises: 20260622_0110
Create Date: 2026-06-23 00:11:11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260623_0111"
down_revision = "20260622_0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_analytics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_key", sa.String(length=160), nullable=False),
        sa.Column("analytics_type", sa.String(length=32), nullable=False),
        sa.Column("analytics_scope", sa.String(length=80), nullable=False),
        sa.Column("analytics_status", sa.String(length=16), nullable=False),
        sa.Column("replay_safe", sa.Boolean(), nullable=False),
        sa.Column("deterministic_ordering_enabled", sa.Boolean(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_manifest_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "snapshot_key", name="uq_automation_analytics_snapshot_owner_key"),
    )
    op.create_index("ix_automation_analytics_snapshot_type_created", "automation_analytics_snapshots", ["analytics_type", "created_at", "id"])
    op.create_index("ix_automation_analytics_snapshot_status_created", "automation_analytics_snapshots", ["analytics_status", "created_at", "id"])

    op.create_table(
        "automation_analytics_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("metric_category", sa.String(length=24), nullable=False),
        sa.Column("metric_value", sa.String(length=512), nullable=False),
        sa.Column("metric_delta", sa.String(length=512), nullable=True),
        sa.Column("metric_status", sa.String(length=16), nullable=False),
        sa.Column("metric_rank", sa.Integer(), nullable=False),
        sa.Column("metric_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "metric_key", name="uq_automation_analytics_metric_snapshot_key"),
    )
    op.create_index("ix_automation_analytics_metric_category_rank", "automation_analytics_metrics", ["snapshot_id", "metric_category", "metric_rank", "metric_key", "id"])
    op.create_index("ix_automation_analytics_metric_status_created", "automation_analytics_metrics", ["metric_status", "created_at", "id"])

    op.create_table(
        "automation_analytics_trends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("trend_key", sa.String(length=120), nullable=False),
        sa.Column("trend_type", sa.String(length=32), nullable=False),
        sa.Column("trend_direction", sa.String(length=16), nullable=False),
        sa.Column("historical_window", sa.Integer(), nullable=False),
        sa.Column("trend_value", sa.String(length=512), nullable=False),
        sa.Column("trend_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "trend_key", name="uq_automation_analytics_trend_snapshot_key"),
    )
    op.create_index("ix_automation_analytics_trend_type_created", "automation_analytics_trends", ["trend_type", "created_at", "id"])
    op.create_index("ix_automation_analytics_trend_direction_created", "automation_analytics_trends", ["trend_direction", "created_at", "id"])

    op.create_table(
        "automation_analytics_comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("comparison_key", sa.String(length=120), nullable=False),
        sa.Column("comparison_type", sa.String(length=32), nullable=False),
        sa.Column("baseline_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("comparison_result_json", sa.JSON(), nullable=False),
        sa.Column("comparison_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["baseline_snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "comparison_key", name="uq_automation_analytics_comparison_snapshot_key"),
    )
    op.create_index("ix_automation_analytics_comparison_type_created", "automation_analytics_comparisons", ["comparison_type", "created_at", "id"])
    op.create_index("ix_automation_analytics_comparison_snapshot_created", "automation_analytics_comparisons", ["snapshot_id", "created_at", "id"])

    op.create_table(
        "automation_analytics_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("artifact_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "artifact_type", "artifact_checksum", name="uq_automation_analytics_artifact_type_checksum"),
    )
    op.create_index("ix_automation_analytics_artifact_snapshot_created", "automation_analytics_artifacts", ["snapshot_id", "created_at", "id"])

    op.create_table(
        "automation_analytics_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_message", sa.String(length=1024), nullable=False),
        sa.Column("issue_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "issue_checksum", name="uq_automation_analytics_issue_checksum"),
    )
    op.create_index("ix_automation_analytics_issue_type_created", "automation_analytics_issues", ["issue_type", "created_at", "id"])
    op.create_index("ix_automation_analytics_issue_snapshot_created", "automation_analytics_issues", ["snapshot_id", "created_at", "id"])

    op.create_table(
        "automation_analytics_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("comparison_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=True),
        sa.Column("event_message", sa.String(length=512), nullable=False),
        sa.Column("event_checksum", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["automation_analytics_comparisons.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["automation_analytics_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "event_checksum", name="uq_automation_analytics_history_checksum"),
    )
    op.create_index("ix_automation_analytics_history_snapshot_created", "automation_analytics_history", ["snapshot_id", "created_at", "id"])
    op.create_index("ix_automation_analytics_history_type_created", "automation_analytics_history", ["event_type", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("automation_analytics_history")
    op.drop_table("automation_analytics_issues")
    op.drop_table("automation_analytics_artifacts")
    op.drop_table("automation_analytics_comparisons")
    op.drop_table("automation_analytics_trends")
    op.drop_table("automation_analytics_metrics")
    op.drop_table("automation_analytics_snapshots")
