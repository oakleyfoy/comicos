"""P67 Portfolio Analytics Platform

Revision ID: 20260613_0228
Revises: 20260612_0227
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260613_0228"
down_revision = "20260612_0227"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p67_portfolio_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_cost_basis", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_estimated_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_unrealized_gain", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_unrealized_gain_pct", sa.Float(), nullable=False),
        sa.Column("total_realized_gain", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_realized_gain_pct", sa.Float(), nullable=False),
        sa.Column("average_roi_pct", sa.Float(), nullable=False),
        sa.Column("portfolio_cagr_pct", sa.Float(), nullable=True),
        sa.Column("best_performer_title", sa.String(length=512), nullable=False),
        sa.Column("worst_performer_title", sa.String(length=512), nullable=False),
        sa.Column("largest_position_title", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_port_perf_owner_gen", "p67_portfolio_performance_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p67_portfolio_performance_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series", sa.String(length=255), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain", sa.Numeric(12, 2), nullable=False),
        sa.Column("unrealized_gain_pct", sa.Float(), nullable=False),
        sa.Column("realized_gain", sa.Numeric(12, 2), nullable=False),
        sa.Column("realized_gain_pct", sa.Float(), nullable=False),
        sa.Column("roi_pct", sa.Float(), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p67_portfolio_performance_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_port_perf_item_snap", "p67_portfolio_performance_item", ["snapshot_id", "unrealized_gain_pct", "id"])

    op.create_table(
        "p67_collection_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_holdings", sa.Integer(), nullable=False),
        sa.Column("concentration_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_coll_analytics_owner_gen", "p67_collection_analytics_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p67_recommendation_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_tracked", sa.Integer(), nullable=False),
        sa.Column("hit_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_return_pct", sa.Float(), nullable=False),
        sa.Column("recommendation_roi_pct", sa.Float(), nullable=False),
        sa.Column("confidence_accuracy_pct", sa.Float(), nullable=False),
        sa.Column("best_recommendation_title", sa.String(length=512), nullable=False),
        sa.Column("worst_recommendation_title", sa.String(length=512), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_rec_perf_owner_gen", "p67_recommendation_performance_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p67_recommendation_performance_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("cross_system_recommendation_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("recommendation_type", sa.String(length=16), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("recommended", sa.Boolean(), nullable=False),
        sa.Column("viewed", sa.Boolean(), nullable=False),
        sa.Column("purchased", sa.Boolean(), nullable=False),
        sa.Column("held", sa.Boolean(), nullable=False),
        sa.Column("sold", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p67_recommendation_performance_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["cross_system_recommendation_id"], ["cross_system_recommendation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_rec_perf_item_snap", "p67_recommendation_performance_item", ["snapshot_id", "return_pct", "id"])
    op.create_index(op.f("ix_p67_recommendation_performance_item_outcome"), "p67_recommendation_performance_item", ["outcome"])

    op.create_table(
        "p67_grading_opportunity_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_grade_opp_owner_gen", "p67_grading_opportunity_snapshot", ["owner_user_id", "generated_at", "id"])

    op.create_table(
        "p67_grading_opportunity_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("estimated_grade", sa.String(length=32), nullable=False),
        sa.Column("submission_candidate_score", sa.Float(), nullable=False),
        sa.Column("estimated_roi_pct", sa.Float(), nullable=False),
        sa.Column("raw_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("graded_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("submission_priority", sa.Integer(), nullable=False),
        sa.Column("notes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p67_grading_opportunity_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_grade_opp_item_snap", "p67_grading_opportunity_item", ["snapshot_id", "submission_priority", "id"])

    op.create_table(
        "p67_investor_dashboard_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collection_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("cost_basis", sa.Numeric(14, 2), nullable=False),
        sa.Column("unrealized_gain", sa.Numeric(14, 2), nullable=False),
        sa.Column("realized_gain", sa.Numeric(14, 2), nullable=False),
        sa.Column("portfolio_health_score", sa.Float(), nullable=False),
        sa.Column("cards_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p67_investor_dash_owner_gen", "p67_investor_dashboard_snapshot", ["owner_user_id", "generated_at", "id"])


def downgrade() -> None:
    for t in (
        "p67_investor_dashboard_snapshot",
        "p67_grading_opportunity_item",
        "p67_grading_opportunity_snapshot",
        "p67_recommendation_performance_item",
        "p67_recommendation_performance_snapshot",
        "p67_collection_analytics_snapshot",
        "p67_portfolio_performance_item",
        "p67_portfolio_performance_snapshot",
    ):
        op.drop_table(t)
