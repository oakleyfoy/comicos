"""add market and user intelligence (P51-03)

Revision ID: 20260820_0170
Revises: 20260819_0169
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0170"
down_revision = "20260819_0169"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_demand_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(length=160), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_name", name="uq_market_demand_profile_entity"),
    )
    op.create_index("ix_market_demand_profile_entity_type", "market_demand_profile", ["entity_type"])
    op.create_index("ix_market_demand_profile_entity_id", "market_demand_profile", ["entity_id"])
    op.create_index("ix_market_demand_profile_entity_name", "market_demand_profile", ["entity_name"])
    op.create_index("ix_market_demand_profile_demand_score", "market_demand_profile", ["demand_score"])
    op.create_index("ix_market_demand_profile_source_version", "market_demand_profile", ["source_version"])
    op.create_index("ix_market_demand_profile_demand", "market_demand_profile", ["demand_score", "created_at", "id"])

    op.create_table(
        "market_demand_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=48), nullable=False),
        sa.Column("signal_strength", sa.Float(), nullable=False),
        sa.Column("signal_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["market_demand_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_demand_signal_profile_id", "market_demand_signal", ["profile_id"])
    op.create_index("ix_market_demand_signal_signal_type", "market_demand_signal", ["signal_type"])
    op.create_index("ix_market_demand_signal_profile", "market_demand_signal", ["profile_id", "signal_type", "id"])

    op.create_table(
        "historical_performance_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_name", sa.String(length=160), nullable=False),
        sa.Column("performance_type", sa.String(length=48), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_historical_performance_signal_entity_type", "historical_performance_signal", ["entity_type"])
    op.create_index("ix_historical_performance_signal_entity_name", "historical_performance_signal", ["entity_name"])
    op.create_index("ix_historical_performance_signal_performance_type", "historical_performance_signal", ["performance_type"])
    op.create_index(
        "ix_historical_performance_entity",
        "historical_performance_signal",
        ["entity_type", "entity_name", "id"],
    )

    op.create_table(
        "collector_demand_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_name", sa.String(length=160), nullable=False),
        sa.Column("collector_score", sa.Float(), nullable=False),
        sa.Column("liquidity_score", sa.Float(), nullable=False),
        sa.Column("long_term_score", sa.Float(), nullable=False),
        sa.Column("volatility_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collector_demand_score_entity_type", "collector_demand_score", ["entity_type"])
    op.create_index("ix_collector_demand_score_entity_name", "collector_demand_score", ["entity_name"])
    op.create_index("ix_collector_demand_score_collector_score", "collector_demand_score", ["collector_score"])
    op.create_index("ix_collector_demand_entity", "collector_demand_score", ["entity_type", "entity_name", "id"])

    op.create_table(
        "user_preference_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("preference_type", sa.String(length=32), nullable=False),
        sa.Column("preference_key", sa.String(length=160), nullable=False),
        sa.Column("preference_label", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "preference_type", "preference_key", name="uq_user_preference_profile"),
    )
    op.create_index("ix_user_preference_profile_owner_user_id", "user_preference_profile", ["owner_user_id"])
    op.create_index("ix_user_preference_profile_preference_type", "user_preference_profile", ["preference_type"])
    op.create_index("ix_user_preference_profile_preference_key", "user_preference_profile", ["preference_key"])
    op.create_index("ix_user_preference_profile_status", "user_preference_profile", ["status"])
    op.create_index("ix_user_preference_profile_owner", "user_preference_profile", ["owner_user_id", "status", "id"])

    op.create_table(
        "user_preference_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("preference_profile_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=48), nullable=False),
        sa.Column("signal_strength", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["preference_profile_id"], ["user_preference_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_preference_signal_owner_user_id", "user_preference_signal", ["owner_user_id"])
    op.create_index("ix_user_preference_signal_preference_profile_id", "user_preference_signal", ["preference_profile_id"])
    op.create_index("ix_user_preference_signal_signal_type", "user_preference_signal", ["signal_type"])
    op.create_index("ix_user_preference_signal_source_type", "user_preference_signal", ["source_type"])
    op.create_index("ix_user_preference_signal_owner", "user_preference_signal", ["owner_user_id", "source_type", "id"])

    op.create_table(
        "user_preference_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("preference_profile_id", sa.Integer(), nullable=False),
        sa.Column("preference_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["preference_profile_id"], ["user_preference_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_preference_score_owner_user_id", "user_preference_score", ["owner_user_id"])
    op.create_index("ix_user_preference_score_preference_profile_id", "user_preference_score", ["preference_profile_id"])
    op.create_index("ix_user_preference_score_preference_score", "user_preference_score", ["preference_score"])
    op.create_index("ix_user_preference_score_profile", "user_preference_score", ["preference_profile_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("user_preference_score")
    op.drop_table("user_preference_signal")
    op.drop_table("user_preference_profile")
    op.drop_table("collector_demand_score")
    op.drop_table("historical_performance_signal")
    op.drop_table("market_demand_signal")
    op.drop_table("market_demand_profile")
