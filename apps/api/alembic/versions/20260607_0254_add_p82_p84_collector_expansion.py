"""add p82 p84 collector expansion

Revision ID: 20260607_0254
Revises: 20260607_0253
Create Date: 2026-06-08 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0254"
down_revision = "20260607_0253"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p82_marketplace_acquisition_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("marketplace", sa.String(length=24), nullable=False),
        sa.Column("external_listing_id", sa.String(length=128), nullable=False),
        sa.Column("listing_url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("issue", sa.String(length=24), nullable=False),
        sa.Column("variant", sa.String(length=200), nullable=False),
        sa.Column("asking_price", sa.Float(), nullable=False),
        sa.Column("estimated_fmv", sa.Float(), nullable=False),
        sa.Column("discount_to_fmv", sa.Float(), nullable=False),
        sa.Column("liquidity", sa.Float(), nullable=False),
        sa.Column("velocity", sa.Float(), nullable=False),
        sa.Column("grading_upside", sa.Float(), nullable=False),
        sa.Column("ownership_status", sa.String(length=32), nullable=False),
        sa.Column("profile_match_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "marketplace", "external_listing_id", name="uq_p82_mkt_acq_listing"),
    )
    op.create_index("ix_p82_mkt_acq_owner_score", "p82_marketplace_acquisition_opportunity", ["owner_user_id", "opportunity_score", "id"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_owner_user_id"), "p82_marketplace_acquisition_opportunity", ["owner_user_id"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_marketplace"), "p82_marketplace_acquisition_opportunity", ["marketplace"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_external_listing_id"), "p82_marketplace_acquisition_opportunity", ["external_listing_id"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_opportunity_score"), "p82_marketplace_acquisition_opportunity", ["opportunity_score"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_recommendation"), "p82_marketplace_acquisition_opportunity", ["recommendation"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_opportunity_status"), "p82_marketplace_acquisition_opportunity", ["status"])

    op.create_table(
        "p82_marketplace_acquisition_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p82_mkt_acq_snap_owner_date", "p82_marketplace_acquisition_snapshot", ["owner_user_id", "snapshot_date", "id"])
    op.create_index(op.f("ix_p82_marketplace_acquisition_snapshot_owner_user_id"), "p82_marketplace_acquisition_snapshot", ["owner_user_id"])

    op.create_table(
        "p83_collection_valuation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("forecast_json", sa.JSON(), nullable=False),
        sa.Column("optimization_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p83_valuation_snap_owner_date", "p83_collection_valuation_snapshot", ["owner_user_id", "snapshot_date", "id"])
    op.create_index(op.f("ix_p83_collection_valuation_snapshot_owner_user_id"), "p83_collection_valuation_snapshot", ["owner_user_id"])

    op.create_table(
        "p83_collection_risk_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_category", sa.String(length=24), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p83_risk_snap_owner_date", "p83_collection_risk_snapshot", ["owner_user_id", "snapshot_date", "id"])
    op.create_index(op.f("ix_p83_collection_risk_snapshot_owner_user_id"), "p83_collection_risk_snapshot", ["owner_user_id"])
    op.create_index(op.f("ix_p83_collection_risk_snapshot_risk_category"), "p83_collection_risk_snapshot", ["risk_category"])

    op.create_table(
        "p83_collection_scenario_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scenario_type", sa.String(length=32), nullable=False),
        sa.Column("projected_value", sa.Float(), nullable=False),
        sa.Column("cash_generated", sa.Float(), nullable=False),
        sa.Column("risk_change", sa.Float(), nullable=False),
        sa.Column("roi_impact", sa.Float(), nullable=False),
        sa.Column("affected_books_json", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p83_scenario_owner_created", "p83_collection_scenario_run", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_p83_collection_scenario_run_owner_user_id"), "p83_collection_scenario_run", ["owner_user_id"])
    op.create_index(op.f("ix_p83_collection_scenario_run_scenario_type"), "p83_collection_scenario_run", ["scenario_type"])

    op.create_table(
        "p84_collector_notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_entity_type", sa.String(length=32), nullable=False),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("action_url", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p84_notif_owner_status", "p84_collector_notification", ["owner_user_id", "status", "priority", "id"])
    op.create_index(op.f("ix_p84_collector_notification_owner_user_id"), "p84_collector_notification", ["owner_user_id"])
    op.create_index(op.f("ix_p84_collector_notification_notification_type"), "p84_collector_notification", ["notification_type"])
    op.create_index(op.f("ix_p84_collector_notification_priority"), "p84_collector_notification", ["priority"])
    op.create_index(op.f("ix_p84_collector_notification_related_entity_id"), "p84_collector_notification", ["related_entity_id"])
    op.create_index(op.f("ix_p84_collector_notification_status"), "p84_collector_notification", ["status"])

    op.create_table(
        "p84_collector_briefing",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("briefing_type", sa.String(length=16), nullable=False),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("top_actions_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p84_briefing_owner_type_date", "p84_collector_briefing", ["owner_user_id", "briefing_type", "briefing_date", "id"])
    op.create_index(op.f("ix_p84_collector_briefing_owner_user_id"), "p84_collector_briefing", ["owner_user_id"])
    op.create_index(op.f("ix_p84_collector_briefing_briefing_type"), "p84_collector_briefing", ["briefing_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p84_collector_briefing_briefing_type"), table_name="p84_collector_briefing")
    op.drop_index(op.f("ix_p84_collector_briefing_owner_user_id"), table_name="p84_collector_briefing")
    op.drop_index("ix_p84_briefing_owner_type_date", table_name="p84_collector_briefing")
    op.drop_table("p84_collector_briefing")

    op.drop_index(op.f("ix_p84_collector_notification_status"), table_name="p84_collector_notification")
    op.drop_index(op.f("ix_p84_collector_notification_related_entity_id"), table_name="p84_collector_notification")
    op.drop_index(op.f("ix_p84_collector_notification_priority"), table_name="p84_collector_notification")
    op.drop_index(op.f("ix_p84_collector_notification_notification_type"), table_name="p84_collector_notification")
    op.drop_index(op.f("ix_p84_collector_notification_owner_user_id"), table_name="p84_collector_notification")
    op.drop_index("ix_p84_notif_owner_status", table_name="p84_collector_notification")
    op.drop_table("p84_collector_notification")

    op.drop_index(op.f("ix_p83_collection_scenario_run_scenario_type"), table_name="p83_collection_scenario_run")
    op.drop_index(op.f("ix_p83_collection_scenario_run_owner_user_id"), table_name="p83_collection_scenario_run")
    op.drop_index("ix_p83_scenario_owner_created", table_name="p83_collection_scenario_run")
    op.drop_table("p83_collection_scenario_run")

    op.drop_index(op.f("ix_p83_collection_risk_snapshot_risk_category"), table_name="p83_collection_risk_snapshot")
    op.drop_index(op.f("ix_p83_collection_risk_snapshot_owner_user_id"), table_name="p83_collection_risk_snapshot")
    op.drop_index("ix_p83_risk_snap_owner_date", table_name="p83_collection_risk_snapshot")
    op.drop_table("p83_collection_risk_snapshot")

    op.drop_index(op.f("ix_p83_collection_valuation_snapshot_owner_user_id"), table_name="p83_collection_valuation_snapshot")
    op.drop_index("ix_p83_valuation_snap_owner_date", table_name="p83_collection_valuation_snapshot")
    op.drop_table("p83_collection_valuation_snapshot")

    op.drop_index(op.f("ix_p82_marketplace_acquisition_snapshot_owner_user_id"), table_name="p82_marketplace_acquisition_snapshot")
    op.drop_index("ix_p82_mkt_acq_snap_owner_date", table_name="p82_marketplace_acquisition_snapshot")
    op.drop_table("p82_marketplace_acquisition_snapshot")

    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_status"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_recommendation"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_opportunity_score"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_external_listing_id"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_marketplace"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index(op.f("ix_p82_marketplace_acquisition_opportunity_owner_user_id"), table_name="p82_marketplace_acquisition_opportunity")
    op.drop_index("ix_p82_mkt_acq_owner_score", table_name="p82_marketplace_acquisition_opportunity")
    op.drop_table("p82_marketplace_acquisition_opportunity")
