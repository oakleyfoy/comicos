"""add p88 marketplace listing comparison fields

Revision ID: 20260608_0260
Revises: 20260608_0259
Create Date: 2026-06-08 08:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0260"
down_revision = "20260608_0259"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "p88_marketplace_listing",
        sa.Column("marketplace_name", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "p88_marketplace_listing",
        sa.Column("availability_status", sa.String(length=16), nullable=False, server_default="UNKNOWN"),
    )
    op.add_column(
        "p88_marketplace_listing",
        sa.Column("listing_confidence", sa.String(length=8), nullable=False, server_default="MEDIUM"),
    )
    op.add_column(
        "p88_marketplace_listing",
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
    )
    op.add_column(
        "p88_marketplace_listing",
        sa.Column("price_last_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_p88_marketplace_listing_availability_status"),
        "p88_marketplace_listing",
        ["availability_status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_p88_marketplace_listing_availability_status"), table_name="p88_marketplace_listing")
    op.drop_column("p88_marketplace_listing", "price_last_changed_at")
    op.drop_column("p88_marketplace_listing", "currency")
    op.drop_column("p88_marketplace_listing", "listing_confidence")
    op.drop_column("p88_marketplace_listing", "availability_status")
    op.drop_column("p88_marketplace_listing", "marketplace_name")
