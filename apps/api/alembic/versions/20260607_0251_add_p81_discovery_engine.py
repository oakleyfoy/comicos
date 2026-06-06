"""add p81 discovery engine

Revision ID: 20260607_0251
Revises: 20260607_0250
Create Date: 2026-06-07 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0251"
down_revision = "20260607_0250"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p81_discovery_opportunity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_key", sa.String(length=320), nullable=False),
        sa.Column("opportunity_type", sa.String(length=32), nullable=False),
        sa.Column("registry_status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=24), nullable=False),
        sa.Column("variant_label", sa.String(length=200), nullable=False),
        sa.Column("discovery_date", sa.Date(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("creator_metadata_json", sa.JSON(), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=False),
        sa.Column("discovery_score", sa.Float(), nullable=False),
        sa.Column("score_category", sa.String(length=24), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("release_issue_id", sa.Integer(), nullable=True),
        sa.Column("external_catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_catalog_issue_id"], ["external_catalog_issue.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "opportunity_key", name="uq_p81_discovery_opportunity_key"),
    )
    op.create_index("ix_p81_discovery_owner_score", "p81_discovery_opportunity", ["owner_user_id", "discovery_score", "id"])
    op.create_index(
        "ix_p81_discovery_owner_category", "p81_discovery_opportunity", ["owner_user_id", "score_category", "updated_at", "id"]
    )
    op.create_index("ix_p81_discovery_owner_type", "p81_discovery_opportunity", ["owner_user_id", "opportunity_type", "id"])

    op.create_table(
        "p81_discovery_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p81_discovery_snapshot_owner_date", "p81_discovery_snapshot", ["owner_user_id", "snapshot_date", "id"])


def downgrade() -> None:
    op.drop_index("ix_p81_discovery_snapshot_owner_date", table_name="p81_discovery_snapshot")
    op.drop_table("p81_discovery_snapshot")
    op.drop_index("ix_p81_discovery_owner_type", table_name="p81_discovery_opportunity")
    op.drop_index("ix_p81_discovery_owner_category", table_name="p81_discovery_opportunity")
    op.drop_index("ix_p81_discovery_owner_score", table_name="p81_discovery_opportunity")
    op.drop_table("p81_discovery_opportunity")
