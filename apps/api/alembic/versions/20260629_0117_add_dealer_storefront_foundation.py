"""add dealer profile storefront foundation

Revision ID: 20260629_0117
Revises: 20260628_0116
Create Date: 2026-06-29 00:17:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260629_0117"
down_revision = "20260628_0116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dealer_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("public_slug", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("tagline", sa.String(length=240), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_asset_id", sa.Integer(), nullable=True),
        sa.Column("banner_asset_id", sa.Integer(), nullable=True),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("instagram_url", sa.String(length=512), nullable=True),
        sa.Column("whatnot_url", sa.String(length=512), nullable=True),
        sa.Column("location_label", sa.String(length=160), nullable=True),
        sa.Column("profile_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_dealer_profile_organization"),
        sa.UniqueConstraint("public_slug", name="uq_dealer_profile_public_slug"),
    )
    op.create_index("ix_dealer_profile_status_updated", "dealer_profiles", ["profile_status", "updated_at", "id"])

    op.create_table(
        "dealer_storefront_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("storefront_visibility", sa.String(length=24), nullable=False),
        sa.Column("public_inventory_enabled", sa.Boolean(), nullable=False),
        sa.Column("featured_inventory_limit", sa.Integer(), nullable=False),
        sa.Column("featured_inventory_sort", sa.String(length=32), nullable=False),
        sa.Column("featured_manual_inventory_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_dealer_storefront_settings_org"),
    )

    op.create_table(
        "dealer_storefront_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dealer_storefront_event_org_created", "dealer_storefront_events", ["organization_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_dealer_storefront_event_org_created", table_name="dealer_storefront_events")
    op.drop_table("dealer_storefront_events")
    op.drop_table("dealer_storefront_settings")
    op.drop_index("ix_dealer_profile_status_updated", table_name="dealer_profiles")
    op.drop_table("dealer_profiles")
