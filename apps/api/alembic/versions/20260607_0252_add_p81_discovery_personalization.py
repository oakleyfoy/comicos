"""add p81 discovery personalization

Revision ID: 20260607_0252
Revises: 20260607_0251
Create Date: 2026-06-08 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0252"
down_revision = "20260607_0251"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p81_discovery_watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("watchlist_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("auto_managed", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "watchlist_type", "label", name="uq_p81_discovery_watchlist_label"),
    )
    op.create_index("ix_p81_discovery_watchlist_owner", "p81_discovery_watchlist", ["owner_user_id", "active", "id"])

    op.create_table(
        "p81_discovery_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("personalized_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["p81_discovery_opportunity.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p81_discovery_alert_owner_status", "p81_discovery_alert", ["owner_user_id", "status", "priority", "id"])
    op.create_index("ix_p81_discovery_alert_owner_opp", "p81_discovery_alert", ["owner_user_id", "opportunity_id", "id"])

    op.create_table(
        "p81_future_pull_list_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=False),
        sa.Column("pipeline_status", sa.String(length=16), nullable=False),
        sa.Column("watch_level", sa.String(length=16), nullable=False),
        sa.Column("recommendation_action", sa.String(length=16), nullable=False),
        sa.Column("recommendation_quantity", sa.Integer(), nullable=False),
        sa.Column("personalized_score", sa.Float(), nullable=False),
        sa.Column("priority_category", sa.String(length=24), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["p81_discovery_opportunity.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "opportunity_id", name="uq_p81_future_pull_opportunity"),
    )
    op.create_index(
        "ix_p81_future_pull_owner_pipeline",
        "p81_future_pull_list_item",
        ["owner_user_id", "pipeline_status", "personalized_score", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p81_future_pull_owner_pipeline", table_name="p81_future_pull_list_item")
    op.drop_table("p81_future_pull_list_item")
    op.drop_index("ix_p81_discovery_alert_owner_opp", table_name="p81_discovery_alert")
    op.drop_index("ix_p81_discovery_alert_owner_status", table_name="p81_discovery_alert")
    op.drop_table("p81_discovery_alert")
    op.drop_index("ix_p81_discovery_watchlist_owner", table_name="p81_discovery_watchlist")
    op.drop_table("p81_discovery_watchlist")
