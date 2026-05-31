"""add market forecasting foundation

Revision ID: 20260802_0151
Revises: 20260801_0150
Create Date: 2026-08-02 01:51:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260802_0151"
down_revision = "20260801_0150"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_forecast",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("forecast_uuid", sa.String(length=64), nullable=False),
        sa.Column("forecast_type", sa.String(length=80), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("forecast_horizon_days", sa.Integer(), nullable=False),
        sa.Column("forecast_value", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("forecast_uuid", name="uq_market_forecast_uuid"),
    )
    op.create_index("ix_market_forecast_owner_user_id", "market_forecast", ["owner_user_id"])
    op.create_index("ix_market_forecast_forecast_uuid", "market_forecast", ["forecast_uuid"])
    op.create_index("ix_market_forecast_forecast_type", "market_forecast", ["forecast_type"])
    op.create_index("ix_market_forecast_asset_type", "market_forecast", ["asset_type"])
    op.create_index("ix_market_forecast_asset_id", "market_forecast", ["asset_id"])
    op.create_index("ix_market_forecast_forecast_horizon_days", "market_forecast", ["forecast_horizon_days"])
    op.create_index("ix_market_forecast_confidence_score", "market_forecast", ["confidence_score"])
    op.create_index("ix_market_forecast_created_at", "market_forecast", ["created_at"])
    op.create_index("ix_market_forecast_owner_created", "market_forecast", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "market_forecast_point",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forecast_id", sa.Integer(), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("projected_value", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["forecast_id"], ["market_forecast.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_forecast_point_forecast_id", "market_forecast_point", ["forecast_id"])
    op.create_index("ix_market_forecast_point_forecast_date", "market_forecast_point", ["forecast_date"])
    op.create_index("ix_market_forecast_point_confidence_score", "market_forecast_point", ["confidence_score"])
    op.create_index("ix_market_forecast_point_created_at", "market_forecast_point", ["created_at"])

    op.create_table(
        "market_forecast_confidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forecast_id", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_band", sa.String(length=24), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["forecast_id"], ["market_forecast.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_forecast_confidence_forecast_id", "market_forecast_confidence", ["forecast_id"])
    op.create_index("ix_market_forecast_confidence_confidence_score", "market_forecast_confidence", ["confidence_score"])
    op.create_index("ix_market_forecast_confidence_confidence_band", "market_forecast_confidence", ["confidence_band"])
    op.create_index("ix_market_forecast_confidence_created_at", "market_forecast_confidence", ["created_at"])

    op.create_table(
        "market_risk_assessment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("assessment_uuid", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=80), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("risk_type", sa.String(length=80), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_uuid", name="uq_market_risk_assessment_uuid"),
    )
    op.create_index("ix_market_risk_assessment_owner_user_id", "market_risk_assessment", ["owner_user_id"])
    op.create_index("ix_market_risk_assessment_assessment_uuid", "market_risk_assessment", ["assessment_uuid"])
    op.create_index("ix_market_risk_assessment_asset_type", "market_risk_assessment", ["asset_type"])
    op.create_index("ix_market_risk_assessment_asset_id", "market_risk_assessment", ["asset_id"])
    op.create_index("ix_market_risk_assessment_risk_type", "market_risk_assessment", ["risk_type"])
    op.create_index("ix_market_risk_assessment_risk_score", "market_risk_assessment", ["risk_score"])
    op.create_index("ix_market_risk_assessment_confidence_score", "market_risk_assessment", ["confidence_score"])
    op.create_index("ix_market_risk_assessment_created_at", "market_risk_assessment", ["created_at"])
    op.create_index(
        "ix_market_risk_assessment_owner_created",
        "market_risk_assessment",
        ["owner_user_id", "created_at", "id"],
    )

    op.create_table(
        "forecast_agent_execution",
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
        sa.UniqueConstraint("execution_uuid", name="uq_forecast_agent_execution_uuid"),
    )
    op.create_index("ix_forecast_agent_execution_owner_user_id", "forecast_agent_execution", ["owner_user_id"])
    op.create_index("ix_forecast_agent_execution_agent_code", "forecast_agent_execution", ["agent_code"])
    op.create_index("ix_forecast_agent_execution_execution_uuid", "forecast_agent_execution", ["execution_uuid"])
    op.create_index("ix_forecast_agent_execution_status", "forecast_agent_execution", ["status"])
    op.create_index("ix_forecast_agent_execution_created_at", "forecast_agent_execution", ["created_at"])
    op.create_index(
        "ix_forecast_agent_execution_owner_created",
        "forecast_agent_execution",
        ["owner_user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_agent_execution_owner_created", table_name="forecast_agent_execution")
    op.drop_index("ix_forecast_agent_execution_created_at", table_name="forecast_agent_execution")
    op.drop_index("ix_forecast_agent_execution_status", table_name="forecast_agent_execution")
    op.drop_index("ix_forecast_agent_execution_execution_uuid", table_name="forecast_agent_execution")
    op.drop_index("ix_forecast_agent_execution_agent_code", table_name="forecast_agent_execution")
    op.drop_index("ix_forecast_agent_execution_owner_user_id", table_name="forecast_agent_execution")
    op.drop_table("forecast_agent_execution")

    op.drop_index("ix_market_risk_assessment_owner_created", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_created_at", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_confidence_score", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_risk_score", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_risk_type", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_asset_id", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_asset_type", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_assessment_uuid", table_name="market_risk_assessment")
    op.drop_index("ix_market_risk_assessment_owner_user_id", table_name="market_risk_assessment")
    op.drop_table("market_risk_assessment")

    op.drop_index("ix_market_forecast_confidence_created_at", table_name="market_forecast_confidence")
    op.drop_index("ix_market_forecast_confidence_confidence_band", table_name="market_forecast_confidence")
    op.drop_index("ix_market_forecast_confidence_confidence_score", table_name="market_forecast_confidence")
    op.drop_index("ix_market_forecast_confidence_forecast_id", table_name="market_forecast_confidence")
    op.drop_table("market_forecast_confidence")

    op.drop_index("ix_market_forecast_point_created_at", table_name="market_forecast_point")
    op.drop_index("ix_market_forecast_point_confidence_score", table_name="market_forecast_point")
    op.drop_index("ix_market_forecast_point_forecast_date", table_name="market_forecast_point")
    op.drop_index("ix_market_forecast_point_forecast_id", table_name="market_forecast_point")
    op.drop_table("market_forecast_point")

    op.drop_index("ix_market_forecast_owner_created", table_name="market_forecast")
    op.drop_index("ix_market_forecast_created_at", table_name="market_forecast")
    op.drop_index("ix_market_forecast_confidence_score", table_name="market_forecast")
    op.drop_index("ix_market_forecast_forecast_horizon_days", table_name="market_forecast")
    op.drop_index("ix_market_forecast_asset_id", table_name="market_forecast")
    op.drop_index("ix_market_forecast_asset_type", table_name="market_forecast")
    op.drop_index("ix_market_forecast_forecast_type", table_name="market_forecast")
    op.drop_index("ix_market_forecast_forecast_uuid", table_name="market_forecast")
    op.drop_index("ix_market_forecast_owner_user_id", table_name="market_forecast")
    op.drop_table("market_forecast")
