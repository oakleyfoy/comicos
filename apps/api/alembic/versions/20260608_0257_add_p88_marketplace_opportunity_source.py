"""add p88 marketplace opportunity source

Revision ID: 20260608_0257
Revises: 20260608_0256
Create Date: 2026-06-08 05:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0257"
down_revision = "20260608_0256"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p88_marketplace_opportunity_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), nullable=True),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("external_listing_id", sa.String(length=128), nullable=False),
        sa.Column("source_status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], ["p82_marketplace_acquisition_opportunity.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p88_mkt_src_owner_created",
        "p88_marketplace_opportunity_source",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_p88_mkt_src_opportunity",
        "p88_marketplace_opportunity_source",
        ["opportunity_id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_opportunity_source_owner_user_id"),
        "p88_marketplace_opportunity_source",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_opportunity_source_marketplace"),
        "p88_marketplace_opportunity_source",
        ["marketplace"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_opportunity_source_source_type"),
        "p88_marketplace_opportunity_source",
        ["source_type"],
    )
    op.create_index(
        op.f("ix_p88_marketplace_opportunity_source_source_status"),
        "p88_marketplace_opportunity_source",
        ["source_status"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_p88_marketplace_opportunity_source_source_status"),
        table_name="p88_marketplace_opportunity_source",
    )
    op.drop_index(
        op.f("ix_p88_marketplace_opportunity_source_source_type"),
        table_name="p88_marketplace_opportunity_source",
    )
    op.drop_index(
        op.f("ix_p88_marketplace_opportunity_source_marketplace"),
        table_name="p88_marketplace_opportunity_source",
    )
    op.drop_index(
        op.f("ix_p88_marketplace_opportunity_source_owner_user_id"),
        table_name="p88_marketplace_opportunity_source",
    )
    op.drop_index("ix_p88_mkt_src_opportunity", table_name="p88_marketplace_opportunity_source")
    op.drop_index("ix_p88_mkt_src_owner_created", table_name="p88_marketplace_opportunity_source")
    op.drop_table("p88_marketplace_opportunity_source")
