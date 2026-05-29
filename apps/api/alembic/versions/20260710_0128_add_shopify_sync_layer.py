"""add shopify sync layer

Revision ID: 20260710_0128
Revises: 20260709_0127
Create Date: 2026-07-10 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0128"
down_revision = "20260709_0127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopify_storefronts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("storefront_name", sa.String(length=255), nullable=False),
        sa.Column("storefront_status", sa.String(length=32), nullable=False),
        sa.Column("storefront_identifier", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "marketplace_account_id", name="uq_shopify_storefront_account"),
        sa.UniqueConstraint("organization_id", "storefront_identifier", name="uq_shopify_storefront_identifier"),
    )
    op.create_index("ix_shopify_storefront_org_created", "shopify_storefronts", ["organization_id", "created_at", "id"])
    op.create_index("ix_shopify_storefront_org_status_created", "shopify_storefronts", ["organization_id", "storefront_status", "created_at", "id"])
    op.create_index(op.f("ix_shopify_storefronts_marketplace_account_id"), "shopify_storefronts", ["marketplace_account_id"])
    op.create_index(op.f("ix_shopify_storefronts_organization_id"), "shopify_storefronts", ["organization_id"])
    op.create_index(op.f("ix_shopify_storefronts_storefront_identifier"), "shopify_storefronts", ["storefront_identifier"])
    op.create_index(op.f("ix_shopify_storefronts_storefront_status"), "shopify_storefronts", ["storefront_status"])

    op.create_table(
        "shopify_product_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("storefront_product_identifier", sa.String(length=255), nullable=False),
        sa.Column("mapping_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "inventory_item_id", "marketplace_listing_draft_id", name="uq_shopify_product_mapping_identity"),
        sa.UniqueConstraint("organization_id", "storefront_product_identifier", name="uq_shopify_product_mapping_identifier"),
    )
    op.create_index("ix_shopify_product_mapping_org_updated", "shopify_product_mappings", ["organization_id", "updated_at", "id"])
    op.create_index("ix_shopify_product_mapping_org_status_updated", "shopify_product_mappings", ["organization_id", "mapping_status", "updated_at", "id"])
    op.create_index(op.f("ix_shopify_product_mappings_inventory_item_id"), "shopify_product_mappings", ["inventory_item_id"])
    op.create_index(op.f("ix_shopify_product_mappings_marketplace_listing_draft_id"), "shopify_product_mappings", ["marketplace_listing_draft_id"])
    op.create_index(op.f("ix_shopify_product_mappings_mapping_status"), "shopify_product_mappings", ["mapping_status"])
    op.create_index(op.f("ix_shopify_product_mappings_organization_id"), "shopify_product_mappings", ["organization_id"])
    op.create_index(op.f("ix_shopify_product_mappings_storefront_product_identifier"), "shopify_product_mappings", ["storefront_product_identifier"])

    op.create_table(
        "shopify_sync_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("storefront_id", sa.Integer(), nullable=False),
        sa.Column("sync_status", sa.String(length=24), nullable=False),
        sa.Column("sync_payload_json", sa.JSON(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["storefront_id"], ["shopify_storefronts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storefront_id", name="uq_shopify_sync_state_storefront"),
    )
    op.create_index("ix_shopify_sync_state_org_created", "shopify_sync_states", ["organization_id", "created_at", "id"])
    op.create_index("ix_shopify_sync_state_storefront_last_sync", "shopify_sync_states", ["storefront_id", "last_sync_at", "id"])
    op.create_index("ix_shopify_sync_state_org_status_created", "shopify_sync_states", ["organization_id", "sync_status", "created_at", "id"])
    op.create_index(op.f("ix_shopify_sync_states_organization_id"), "shopify_sync_states", ["organization_id"])
    op.create_index(op.f("ix_shopify_sync_states_storefront_id"), "shopify_sync_states", ["storefront_id"])
    op.create_index(op.f("ix_shopify_sync_states_sync_status"), "shopify_sync_states", ["sync_status"])

    op.create_table(
        "shopify_sync_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("storefront_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["storefront_id"], ["shopify_storefronts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopify_sync_event_org_created", "shopify_sync_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_shopify_sync_event_storefront_created", "shopify_sync_events", ["storefront_id", "created_at", "id"])
    op.create_index("ix_shopify_sync_event_org_type_created", "shopify_sync_events", ["organization_id", "event_type", "created_at", "id"])
    op.create_index("ix_shopify_sync_event_actor_created", "shopify_sync_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_shopify_sync_events_actor_user_id"), "shopify_sync_events", ["actor_user_id"])
    op.create_index(op.f("ix_shopify_sync_events_event_type"), "shopify_sync_events", ["event_type"])
    op.create_index(op.f("ix_shopify_sync_events_organization_id"), "shopify_sync_events", ["organization_id"])
    op.create_index(op.f("ix_shopify_sync_events_storefront_id"), "shopify_sync_events", ["storefront_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_shopify_sync_events_storefront_id"), table_name="shopify_sync_events")
    op.drop_index(op.f("ix_shopify_sync_events_organization_id"), table_name="shopify_sync_events")
    op.drop_index(op.f("ix_shopify_sync_events_event_type"), table_name="shopify_sync_events")
    op.drop_index(op.f("ix_shopify_sync_events_actor_user_id"), table_name="shopify_sync_events")
    op.drop_index("ix_shopify_sync_event_actor_created", table_name="shopify_sync_events")
    op.drop_index("ix_shopify_sync_event_org_type_created", table_name="shopify_sync_events")
    op.drop_index("ix_shopify_sync_event_storefront_created", table_name="shopify_sync_events")
    op.drop_index("ix_shopify_sync_event_org_created", table_name="shopify_sync_events")
    op.drop_table("shopify_sync_events")

    op.drop_index(op.f("ix_shopify_sync_states_sync_status"), table_name="shopify_sync_states")
    op.drop_index(op.f("ix_shopify_sync_states_storefront_id"), table_name="shopify_sync_states")
    op.drop_index(op.f("ix_shopify_sync_states_organization_id"), table_name="shopify_sync_states")
    op.drop_index("ix_shopify_sync_state_org_status_created", table_name="shopify_sync_states")
    op.drop_index("ix_shopify_sync_state_storefront_last_sync", table_name="shopify_sync_states")
    op.drop_index("ix_shopify_sync_state_org_created", table_name="shopify_sync_states")
    op.drop_table("shopify_sync_states")

    op.drop_index(op.f("ix_shopify_product_mappings_storefront_product_identifier"), table_name="shopify_product_mappings")
    op.drop_index(op.f("ix_shopify_product_mappings_organization_id"), table_name="shopify_product_mappings")
    op.drop_index(op.f("ix_shopify_product_mappings_mapping_status"), table_name="shopify_product_mappings")
    op.drop_index(op.f("ix_shopify_product_mappings_marketplace_listing_draft_id"), table_name="shopify_product_mappings")
    op.drop_index(op.f("ix_shopify_product_mappings_inventory_item_id"), table_name="shopify_product_mappings")
    op.drop_index("ix_shopify_product_mapping_org_status_updated", table_name="shopify_product_mappings")
    op.drop_index("ix_shopify_product_mapping_org_updated", table_name="shopify_product_mappings")
    op.drop_table("shopify_product_mappings")

    op.drop_index(op.f("ix_shopify_storefronts_storefront_status"), table_name="shopify_storefronts")
    op.drop_index(op.f("ix_shopify_storefronts_storefront_identifier"), table_name="shopify_storefronts")
    op.drop_index(op.f("ix_shopify_storefronts_organization_id"), table_name="shopify_storefronts")
    op.drop_index(op.f("ix_shopify_storefronts_marketplace_account_id"), table_name="shopify_storefronts")
    op.drop_index("ix_shopify_storefront_org_status_created", table_name="shopify_storefronts")
    op.drop_index("ix_shopify_storefront_org_created", table_name="shopify_storefronts")
    op.drop_table("shopify_storefronts")
