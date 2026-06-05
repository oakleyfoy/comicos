"""add P62 collector intelligence suite tables

Revision ID: 20260607_0222
Revises: 20260606_0221
Create Date: 2026-06-07 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260607_0222"
down_revision = "20260606_0221"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foc_alert_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_foc_alert_snapshot_owner_gen", "foc_alert_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "foc_alert_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("velocity_score", sa.Float(), nullable=False),
        sa.Column("spec_score", sa.Float(), nullable=False),
        sa.Column("urgency_score", sa.Float(), nullable=False),
        sa.Column("alert_reason", sa.Text(), nullable=False),
        sa.Column("suggested_quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["foc_alert_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_foc_alert_item_snapshot_urgency", "foc_alert_item", ["snapshot_id", "urgency_score", "id"])

    op.create_table(
        "future_pull_forecast",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_future_pull_forecast_owner_gen", "future_pull_forecast", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "future_pull_forecast_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forecast_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["forecast_id"], ["future_pull_forecast.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_future_pull_forecast_item_forecast_conf", "future_pull_forecast_item", ["forecast_id", "confidence", "id"]
    )

    op.create_table(
        "auto_watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("watchlist_type", sa.String(length=48), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation_epoch", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "watchlist_type", "generation_epoch", name="uq_auto_watchlist_owner_type_epoch"),
    )
    op.create_index("ix_auto_watchlist_owner_type", "auto_watchlist", ["owner_user_id", "watchlist_type", "id"])

    op.create_table(
        "auto_watchlist_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("inclusion_reason", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["watchlist_id"], ["auto_watchlist.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auto_watchlist_item_list_issue", "auto_watchlist_item", ["watchlist_id", "release_issue_id", "id"])


def downgrade() -> None:
    op.drop_table("auto_watchlist_item")
    op.drop_table("auto_watchlist")
    op.drop_table("future_pull_forecast_item")
    op.drop_table("future_pull_forecast")
    op.drop_table("foc_alert_item")
    op.drop_table("foc_alert_snapshot")
