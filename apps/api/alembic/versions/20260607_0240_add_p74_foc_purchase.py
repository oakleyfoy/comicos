"""add P74-02 FOC purchase intelligence

Revision ID: 20260607_0240
Revises: 20260607_0239
Create Date: 2026-06-07 02:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0240"
down_revision = "20260607_0239"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p74_foc_recommendation_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("foc_this_week", sa.Integer(), nullable=False),
        sa.Column("foc_next_week", sa.Integer(), nullable=False),
        sa.Column("foc_within_30_days", sa.Integer(), nullable=False),
        sa.Column("foc_missed", sa.Integer(), nullable=False),
        sa.Column("foc_unknown", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_foc_rec_snap_owner",
        "p74_foc_recommendation_snapshot",
        ["owner_user_id", "generated_at", "id"],
    )

    op.create_table(
        "p74_purchase_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("foc_bucket", sa.String(length=32), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("purchase_action", sa.String(length=16), nullable=False),
        sa.Column("quantity_recommended", sa.Integer(), nullable=False),
        sa.Column("owned_quantity", sa.Integer(), nullable=False),
        sa.Column("ordered_quantity", sa.Integer(), nullable=False),
        sa.Column("watchlist_match", sa.Boolean(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("scores_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p74_foc_recommendation_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_purchase_rec_owner_issue",
        "p74_purchase_recommendation",
        ["owner_user_id", "release_issue_id", "generated_at", "id"],
    )

    op.create_table(
        "p74_recommendation_change_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("change_kind", sa.String(length=16), nullable=False),
        sa.Column("previous_action", sa.String(length=16), nullable=False),
        sa.Column("current_action", sa.String(length=16), nullable=False),
        sa.Column("previous_quantity", sa.Integer(), nullable=False),
        sa.Column("current_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p74_rec_change_owner_created",
        "p74_recommendation_change_event",
        ["owner_user_id", "created_at", "id"],
    )

    op.create_table(
        "p74_foc_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["p74_foc_recommendation_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p74_foc_alert_snap", "p74_foc_alert", ["snapshot_id", "alert_type", "id"])


def downgrade() -> None:
    op.drop_index("ix_p74_foc_alert_snap", table_name="p74_foc_alert")
    op.drop_table("p74_foc_alert")
    op.drop_index("ix_p74_rec_change_owner_created", table_name="p74_recommendation_change_event")
    op.drop_table("p74_recommendation_change_event")
    op.drop_index("ix_p74_purchase_rec_owner_issue", table_name="p74_purchase_recommendation")
    op.drop_table("p74_purchase_recommendation")
    op.drop_index("ix_p74_foc_rec_snap_owner", table_name="p74_foc_recommendation_snapshot")
    op.drop_table("p74_foc_recommendation_snapshot")
