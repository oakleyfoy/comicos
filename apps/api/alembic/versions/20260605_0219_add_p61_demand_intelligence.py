"""add P61 demand intelligence platform tables

Revision ID: 20260605_0219
Revises: 20261012_0218
Create Date: 2026-06-05 15:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260605_0219"
down_revision = "20261012_0218"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demand_refresh_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=48), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("profiles_updated", sa.Integer(), nullable=False),
        sa.Column("issues_refreshed", sa.Integer(), nullable=False),
        sa.Column("signals_appended", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_demand_refresh_run_trigger_type", "demand_refresh_run", ["trigger_type"])
    op.create_index("ix_demand_refresh_run_started", "demand_refresh_run", ["started_at", "id"])

    op.create_table(
        "issue_demand_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("pull_count", sa.Integer(), nullable=True),
        sa.Column("want_count", sa.Integer(), nullable=True),
        sa.Column("community_demand_score", sa.Float(), nullable=False),
        sa.Column("entity_rollup_score", sa.Float(), nullable=False),
        sa.Column("combined_demand_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("signal_sources_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "external_issue_id", name="uq_issue_demand_snapshot_source_external"),
    )
    op.create_index("ix_issue_demand_snapshot_source_name", "issue_demand_snapshot", ["source_name"])
    op.create_index("ix_issue_demand_snapshot_release", "issue_demand_snapshot", ["release_issue_id", "combined_demand_score"])

    op.create_table(
        "issue_demand_observation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pull_count", sa.Integer(), nullable=True),
        sa.Column("want_count", sa.Integer(), nullable=True),
        sa.Column("community_demand_score", sa.Float(), nullable=False),
        sa.Column("capture_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_issue_demand_obs_external_observed",
        "issue_demand_observation",
        ["external_issue_id", "observed_at", "id"],
    )

    op.create_table(
        "demand_velocity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("pull_delta", sa.Float(), nullable=False),
        sa.Column("want_delta", sa.Float(), nullable=False),
        sa.Column("combined_score_delta", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("acceleration_score", sa.Float(), nullable=False),
        sa.Column("trend_label", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_issue_id",
            "external_issue_id",
            "window_days",
            name="uq_demand_velocity_issue_window",
        ),
    )

    op.create_table(
        "spec_opportunity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_epoch", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "spec_opportunity_row",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("spec_baseline_score", sa.Float(), nullable=True),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("preference_fit_score", sa.Float(), nullable=False),
        sa.Column("horizon_bucket", sa.String(length=32), nullable=False),
        sa.Column("rationale_json", sa.JSON(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["spec_opportunity_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "weekly_demand_capture_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("certification_path", sa.Text(), nullable=True),
        sa.Column("sync_run_id", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_date", name="uq_weekly_demand_capture_release_date"),
    )

    op.create_table(
        "weekly_demand_capture_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["weekly_demand_capture_schedule.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("weekly_demand_capture_event")
    op.drop_table("weekly_demand_capture_schedule")
    op.drop_table("spec_opportunity_row")
    op.drop_table("spec_opportunity_snapshot")
    op.drop_table("demand_velocity_snapshot")
    op.drop_table("issue_demand_observation")
    op.drop_table("issue_demand_snapshot")
    op.drop_table("demand_refresh_run")
