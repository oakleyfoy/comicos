"""add market intelligence foundation

Revision ID: 20260801_0150
Revises: 20260731_0149
Create Date: 2026-08-01 01:50:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260801_0150"
down_revision = "20260731_0149"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("signal_source", sa.String(length=80), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("signal_value", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_signal_owner_user_id", "market_signal", ["owner_user_id"])
    op.create_index("ix_market_signal_signal_type", "market_signal", ["signal_type"])
    op.create_index("ix_market_signal_signal_source", "market_signal", ["signal_source"])
    op.create_index("ix_market_signal_asset_type", "market_signal", ["asset_type"])
    op.create_index("ix_market_signal_asset_id", "market_signal", ["asset_id"])
    op.create_index("ix_market_signal_created_at", "market_signal", ["created_at"])
    op.create_index("ix_market_signal_owner_created", "market_signal", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "market_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_uuid", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("market_score", sa.Float(), nullable=False),
        sa.Column("bullish_signals", sa.Integer(), nullable=False),
        sa.Column("bearish_signals", sa.Integer(), nullable=False),
        sa.Column("neutral_signals", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_uuid", name="uq_market_snapshot_uuid"),
    )
    op.create_index("ix_market_snapshot_owner_user_id", "market_snapshot", ["owner_user_id"])
    op.create_index("ix_market_snapshot_snapshot_uuid", "market_snapshot", ["snapshot_uuid"])
    op.create_index("ix_market_snapshot_snapshot_date", "market_snapshot", ["snapshot_date"])
    op.create_index("ix_market_snapshot_created_at", "market_snapshot", ["created_at"])
    op.create_index("ix_market_snapshot_owner_date", "market_snapshot", ["owner_user_id", "snapshot_date", "id"])

    op.create_table(
        "market_trend",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("trend_type", sa.String(length=80), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("trend_direction", sa.String(length=24), nullable=False),
        sa.Column("trend_strength", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_trend_owner_user_id", "market_trend", ["owner_user_id"])
    op.create_index("ix_market_trend_trend_type", "market_trend", ["trend_type"])
    op.create_index("ix_market_trend_asset_type", "market_trend", ["asset_type"])
    op.create_index("ix_market_trend_asset_id", "market_trend", ["asset_id"])
    op.create_index("ix_market_trend_trend_direction", "market_trend", ["trend_direction"])
    op.create_index("ix_market_trend_created_at", "market_trend", ["created_at"])
    op.create_index("ix_market_trend_owner_created", "market_trend", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "market_observation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("observation_uuid", sa.String(length=64), nullable=False),
        sa.Column("observation_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_by_agent", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_uuid", name="uq_market_observation_uuid"),
    )
    op.create_index("ix_market_observation_owner_user_id", "market_observation", ["owner_user_id"])
    op.create_index("ix_market_observation_observation_uuid", "market_observation", ["observation_uuid"])
    op.create_index("ix_market_observation_observation_type", "market_observation", ["observation_type"])
    op.create_index("ix_market_observation_created_at", "market_observation", ["created_at"])
    op.create_index("ix_market_observation_owner_created", "market_observation", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "market_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=80), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_market_agent_execution_uuid"),
    )
    op.create_index("ix_market_agent_execution_owner_user_id", "market_agent_execution", ["owner_user_id"])
    op.create_index("ix_market_agent_execution_agent_code", "market_agent_execution", ["agent_code"])
    op.create_index("ix_market_agent_execution_execution_uuid", "market_agent_execution", ["execution_uuid"])
    op.create_index("ix_market_agent_execution_status", "market_agent_execution", ["status"])
    op.create_index("ix_market_agent_execution_created_at", "market_agent_execution", ["created_at"])
    op.create_index(
        "ix_market_agent_execution_owner_created",
        "market_agent_execution",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_agent_execution_owner_created", table_name="market_agent_execution")
    op.drop_index("ix_market_agent_execution_created_at", table_name="market_agent_execution")
    op.drop_index("ix_market_agent_execution_status", table_name="market_agent_execution")
    op.drop_index("ix_market_agent_execution_execution_uuid", table_name="market_agent_execution")
    op.drop_index("ix_market_agent_execution_agent_code", table_name="market_agent_execution")
    op.drop_index("ix_market_agent_execution_owner_user_id", table_name="market_agent_execution")
    op.drop_table("market_agent_execution")

    op.drop_index("ix_market_observation_owner_created", table_name="market_observation")
    op.drop_index("ix_market_observation_created_at", table_name="market_observation")
    op.drop_index("ix_market_observation_observation_type", table_name="market_observation")
    op.drop_index("ix_market_observation_observation_uuid", table_name="market_observation")
    op.drop_index("ix_market_observation_owner_user_id", table_name="market_observation")
    op.drop_table("market_observation")

    op.drop_index("ix_market_trend_owner_created", table_name="market_trend")
    op.drop_index("ix_market_trend_created_at", table_name="market_trend")
    op.drop_index("ix_market_trend_trend_direction", table_name="market_trend")
    op.drop_index("ix_market_trend_asset_id", table_name="market_trend")
    op.drop_index("ix_market_trend_asset_type", table_name="market_trend")
    op.drop_index("ix_market_trend_trend_type", table_name="market_trend")
    op.drop_index("ix_market_trend_owner_user_id", table_name="market_trend")
    op.drop_table("market_trend")

    op.drop_index("ix_market_snapshot_owner_date", table_name="market_snapshot")
    op.drop_index("ix_market_snapshot_created_at", table_name="market_snapshot")
    op.drop_index("ix_market_snapshot_snapshot_date", table_name="market_snapshot")
    op.drop_index("ix_market_snapshot_snapshot_uuid", table_name="market_snapshot")
    op.drop_index("ix_market_snapshot_owner_user_id", table_name="market_snapshot")
    op.drop_table("market_snapshot")

    op.drop_index("ix_market_signal_owner_created", table_name="market_signal")
    op.drop_index("ix_market_signal_created_at", table_name="market_signal")
    op.drop_index("ix_market_signal_asset_id", table_name="market_signal")
    op.drop_index("ix_market_signal_asset_type", table_name="market_signal")
    op.drop_index("ix_market_signal_signal_source", table_name="market_signal")
    op.drop_index("ix_market_signal_signal_type", table_name="market_signal")
    op.drop_index("ix_market_signal_owner_user_id", table_name="market_signal")
    op.drop_table("market_signal")
