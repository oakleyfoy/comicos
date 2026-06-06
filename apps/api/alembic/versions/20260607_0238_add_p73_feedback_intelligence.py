"""add P73-03 recommendation feedback intelligence snapshots

Revision ID: 20260607_0238
Revises: 20260607_0237
Create Date: 2026-06-07 02:38:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0238"
down_revision = "20260607_0237"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p73_recommendation_feedback_bundle_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overall_accuracy_pct", sa.Float(), nullable=False),
        sa.Column("overall_roi_pct", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_fb_bundle_owner_gen",
        "p73_recommendation_feedback_bundle_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )

    op.create_table(
        "p73_recommendation_confidence_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("bundle_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("buy_confidence", sa.Integer(), nullable=False),
        sa.Column("grade_confidence", sa.Integer(), nullable=False),
        sa.Column("sell_confidence", sa.Integer(), nullable=False),
        sa.Column("watch_confidence", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["bundle_snapshot_id"], ["p73_recommendation_feedback_bundle_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p73_rec_conf_bundle", "p73_recommendation_confidence_snapshot", ["bundle_snapshot_id", "id"])

    op.create_table(
        "p73_recommendation_effectiveness_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("bundle_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("win_rate_pct", sa.Float(), nullable=False),
        sa.Column("loss_rate_pct", sa.Float(), nullable=False),
        sa.Column("expected_roi_pct", sa.Float(), nullable=False),
        sa.Column("actual_roi_pct", sa.Float(), nullable=False),
        sa.Column("recommendation_accuracy_pct", sa.Float(), nullable=False),
        sa.Column("by_type_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["bundle_snapshot_id"], ["p73_recommendation_feedback_bundle_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p73_rec_eff_bundle", "p73_recommendation_effectiveness_snapshot", ["bundle_snapshot_id", "id"])

    op.create_table(
        "p73_recommendation_category_calibration_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("bundle_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("calibration_category", sa.String(length=48), nullable=False),
        sa.Column("recommendation_count", sa.Integer(), nullable=False),
        sa.Column("success_rate_pct", sa.Float(), nullable=False),
        sa.Column("average_roi_pct", sa.Float(), nullable=False),
        sa.Column("median_roi_pct", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["bundle_snapshot_id"], ["p73_recommendation_feedback_bundle_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p73_rec_calib_bundle_cat",
        "p73_recommendation_category_calibration_snapshot",
        ["bundle_snapshot_id", "calibration_category", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p73_rec_calib_bundle_cat", table_name="p73_recommendation_category_calibration_snapshot")
    op.drop_table("p73_recommendation_category_calibration_snapshot")
    op.drop_index("ix_p73_rec_eff_bundle", table_name="p73_recommendation_effectiveness_snapshot")
    op.drop_table("p73_recommendation_effectiveness_snapshot")
    op.drop_index("ix_p73_rec_conf_bundle", table_name="p73_recommendation_confidence_snapshot")
    op.drop_table("p73_recommendation_confidence_snapshot")
    op.drop_index("ix_p73_rec_fb_bundle_owner_gen", table_name="p73_recommendation_feedback_bundle_snapshot")
    op.drop_table("p73_recommendation_feedback_bundle_snapshot")
