"""add P74-01 release intelligence monitoring

Revision ID: 20260607_0239
Revises: 20260607_0238
Create Date: 2026-06-07 02:39:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0239"
down_revision = "20260607_0238"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p74_release_change_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(length=48), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["release_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_release_change_owner_detected",
        "p74_release_change_record",
        ["owner_user_id", "detected_at", "id"],
    )

    op.create_table(
        "p74_release_event_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["release_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_release_event_owner_created",
        "p74_release_event_history",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_p74_release_event_issue_type",
        "p74_release_event_history",
        ["issue_id", "event_type", "id"],
    )

    op.create_table(
        "p74_release_monitoring_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("upcoming_total", sa.Integer(), nullable=False),
        sa.Column("this_week_count", sa.Integer(), nullable=False),
        sa.Column("next_week_count", sa.Integer(), nullable=False),
        sa.Column("next_30_days_count", sa.Integer(), nullable=False),
        sa.Column("next_90_days_count", sa.Integer(), nullable=False),
        sa.Column("windows_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_release_mon_snap_owner",
        "p74_release_monitoring_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )

    op.create_table(
        "p74_release_change_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("monitoring_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("changes_total", sa.Integer(), nullable=False),
        sa.Column("discoveries_total", sa.Integer(), nullable=False),
        sa.Column("removals_total", sa.Integer(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_snapshot_id"], ["p74_release_monitoring_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_release_chg_snap_owner",
        "p74_release_change_snapshot",
        ["owner_user_id", "monitoring_snapshot_id", "id"],
    )

    op.create_table(
        "p74_variant_monitoring_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("monitoring_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("variants_added", sa.Integer(), nullable=False),
        sa.Column("ratio_variants_added", sa.Integer(), nullable=False),
        sa.Column("incentive_variants_added", sa.Integer(), nullable=False),
        sa.Column("late_variants_added", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_snapshot_id"], ["p74_release_monitoring_snapshot.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_variant_mon_snap_owner",
        "p74_variant_monitoring_snapshot",
        ["owner_user_id", "monitoring_snapshot_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p74_variant_mon_snap_owner", table_name="p74_variant_monitoring_snapshot")
    op.drop_table("p74_variant_monitoring_snapshot")
    op.drop_index("ix_p74_release_chg_snap_owner", table_name="p74_release_change_snapshot")
    op.drop_table("p74_release_change_snapshot")
    op.drop_index("ix_p74_release_mon_snap_owner", table_name="p74_release_monitoring_snapshot")
    op.drop_table("p74_release_monitoring_snapshot")
    op.drop_index("ix_p74_release_event_issue_type", table_name="p74_release_event_history")
    op.drop_index("ix_p74_release_event_owner_created", table_name="p74_release_event_history")
    op.drop_table("p74_release_event_history")
    op.drop_index("ix_p74_release_change_owner_detected", table_name="p74_release_change_record")
    op.drop_table("p74_release_change_record")
