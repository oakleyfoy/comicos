"""add P79-03 storage analytics

Revision ID: 20260607_0244
Revises: 20260607_0243
Create Date: 2026-06-07 02:44:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0244"
down_revision = "20260607_0243"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p79_storage_analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_locations", sa.Integer(), nullable=False),
        sa.Column("total_boxes", sa.Integer(), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("used_capacity", sa.Integer(), nullable=False),
        sa.Column("available_capacity", sa.Integer(), nullable=False),
        sa.Column("utilization_pct", sa.Float(), nullable=False),
        sa.Column("assigned_inventory_count", sa.Integer(), nullable=False),
        sa.Column("unassigned_inventory_count", sa.Integer(), nullable=False),
        sa.Column("over_capacity_boxes", sa.Integer(), nullable=False),
        sa.Column("inactive_locations", sa.Integer(), nullable=False),
        sa.Column("forecast_risk", sa.String(length=16), nullable=False),
        sa.Column("estimated_months_until_full", sa.Float(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_stor_analytics_owner",
        "p79_storage_analytics_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )

    op.create_table(
        "p79_storage_utilization_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("group_kind", sa.String(length=24), nullable=False),
        sa.Column("group_key", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("utilization_pct", sa.Float(), nullable=False),
        sa.Column("used_capacity", sa.Integer(), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p79_storage_analytics_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_stor_util_snap",
        "p79_storage_utilization_snapshot",
        ["analytics_snapshot_id", "group_kind", "group_key"],
    )

    op.create_table(
        "p79_storage_audit_performance_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("audits_started", sa.Integer(), nullable=False),
        sa.Column("audits_completed", sa.Integer(), nullable=False),
        sa.Column("average_verification_rate_pct", sa.Float(), nullable=False),
        sa.Column("missing_books_found", sa.Integer(), nullable=False),
        sa.Column("unexpected_books_found", sa.Integer(), nullable=False),
        sa.Column("duplicate_assignments_found", sa.Integer(), nullable=False),
        sa.Column("moved_books", sa.Integer(), nullable=False),
        sa.Column("audit_accuracy_rate_pct", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p79_storage_analytics_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_stor_audit_perf",
        "p79_storage_audit_performance_snapshot",
        ["analytics_snapshot_id", "id"],
    )

    op.create_table(
        "p79_storage_health_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["p79_storage_analytics_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_stor_health_snap",
        "p79_storage_health_snapshot",
        ["analytics_snapshot_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p79_stor_health_snap", table_name="p79_storage_health_snapshot")
    op.drop_table("p79_storage_health_snapshot")
    op.drop_index("ix_p79_stor_audit_perf", table_name="p79_storage_audit_performance_snapshot")
    op.drop_table("p79_storage_audit_performance_snapshot")
    op.drop_index("ix_p79_stor_util_snap", table_name="p79_storage_utilization_snapshot")
    op.drop_table("p79_storage_utilization_snapshot")
    op.drop_index("ix_p79_stor_analytics_owner", table_name="p79_storage_analytics_snapshot")
    op.drop_table("p79_storage_analytics_snapshot")
