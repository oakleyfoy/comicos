"""add P64 collector assistant phase A tables

Revision ID: 20260609_0224
Revises: 20260608_0223
Create Date: 2026-06-09 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260609_0224"
down_revision = "20260608_0223"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_assistant_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("upstream_fingerprint_json", sa.JSON(), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_assistant_run_owner_started", "collector_assistant_run", ["owner_user_id", "started_at", "id"])

    op.create_table(
        "collector_briefing_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_status", sa.String(length=16), nullable=False),
        sa.Column("briefing_json", sa.JSON(), nullable=False),
        sa.Column("briefing_markdown", sa.Text(), nullable=False),
        sa.Column("source_versions_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["collector_assistant_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_briefing_run", "collector_briefing_snapshot", ["run_id", "id"])

    op.create_table(
        "collector_recommendation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("lane", sa.String(length=16), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["collector_assistant_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_rec_snap_run_lane", "collector_recommendation_snapshot", ["run_id", "lane", "id"])

    op.create_table(
        "collector_recommendation_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("lane", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("recommended_action", sa.String(length=32), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["collector_recommendation_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_rec_item_snap_pri", "collector_recommendation_item", ["snapshot_id", "priority_score", "id"])

    op.create_table(
        "collector_health_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_status", sa.String(length=16), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False),
        sa.Column("health_band", sa.String(length=16), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("risk_flags_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["collector_assistant_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_health_run", "collector_health_snapshot", ["run_id", "id"])

    op.create_table(
        "collector_opportunity_alert_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alert_count", sa.Integer(), nullable=False),
        sa.Column("critical_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["collector_assistant_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_alert_snap_run", "collector_opportunity_alert_snapshot", ["run_id", "id"])

    op.create_table(
        "collector_opportunity_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_deep_link", sa.String(length=256), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["alert_snapshot_id"], ["collector_opportunity_alert_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_alert_snap_sev", "collector_opportunity_alert", ["alert_snapshot_id", "severity", "id"])

    op.create_table(
        "collector_executive_bundle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_status", sa.String(length=16), nullable=False),
        sa.Column("platform_ready", sa.Boolean(), nullable=False),
        sa.Column("dashboard_json", sa.JSON(), nullable=False),
        sa.Column("freshness_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["collector_assistant_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_executive_run", "collector_executive_bundle", ["run_id", "id"])


def downgrade() -> None:
    for t in (
        "collector_executive_bundle",
        "collector_opportunity_alert",
        "collector_opportunity_alert_snapshot",
        "collector_health_snapshot",
        "collector_recommendation_item",
        "collector_recommendation_snapshot",
        "collector_briefing_snapshot",
        "collector_assistant_run",
    ):
        op.drop_table(t)
