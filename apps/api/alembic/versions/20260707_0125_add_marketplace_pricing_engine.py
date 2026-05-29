"""add marketplace pricing engine foundation

Revision ID: 20260707_0125
Revises: 20260706_0124
Create Date: 2026-07-07 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260707_0125"
down_revision = "20260706_0124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_pricing_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("rule_key", sa.String(length=80), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_status", sa.String(length=24), nullable=False),
        sa.Column("rule_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "rule_key", name="uq_marketplace_pricing_rule_key"),
    )
    op.create_index("ix_mkt_pricing_rule_org_updated", "marketplace_pricing_rules", ["organization_id", "updated_at", "id"])
    op.create_index(
        "ix_mkt_pricing_rule_org_status_updated",
        "marketplace_pricing_rules",
        ["organization_id", "rule_status", "updated_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_pricing_rules_created_by_user_id"), "marketplace_pricing_rules", ["created_by_user_id"])
    op.create_index(op.f("ix_marketplace_pricing_rules_organization_id"), "marketplace_pricing_rules", ["organization_id"])
    op.create_index(op.f("ix_marketplace_pricing_rules_rule_key"), "marketplace_pricing_rules", ["rule_key"])
    op.create_index(op.f("ix_marketplace_pricing_rules_rule_status"), "marketplace_pricing_rules", ["rule_status"])

    op.create_table(
        "marketplace_price_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=32), nullable=False),
        sa.Column("recommended_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_listing_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("floor_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("ceiling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("recommendation_reason", sa.String(length=1000), nullable=False),
        sa.Column("recommendation_status", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_pricing_rec_org_generated", "marketplace_price_recommendations", ["organization_id", "generated_at", "id"])
    op.create_index(
        "ix_mkt_pricing_rec_org_listing_generated",
        "marketplace_price_recommendations",
        ["organization_id", "marketplace_listing_draft_id", "generated_at", "id"],
    )
    op.create_index(
        "ix_mkt_pricing_rec_org_status_generated",
        "marketplace_price_recommendations",
        ["organization_id", "recommendation_status", "generated_at", "id"],
    )
    op.create_index(
        "ix_mkt_pricing_rec_org_account_generated",
        "marketplace_price_recommendations",
        ["organization_id", "marketplace_account_id", "generated_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_price_recommendations_inventory_item_id"), "marketplace_price_recommendations", ["inventory_item_id"])
    op.create_index(op.f("ix_marketplace_price_recommendations_marketplace_account_id"), "marketplace_price_recommendations", ["marketplace_account_id"])
    op.create_index(
        op.f("ix_marketplace_price_recommendations_marketplace_listing_draft_id"),
        "marketplace_price_recommendations",
        ["marketplace_listing_draft_id"],
    )
    op.create_index(op.f("ix_marketplace_price_recommendations_organization_id"), "marketplace_price_recommendations", ["organization_id"])
    op.create_index(
        op.f("ix_marketplace_price_recommendations_recommendation_status"),
        "marketplace_price_recommendations",
        ["recommendation_status"],
    )
    op.create_index(op.f("ix_marketplace_price_recommendations_recommendation_type"), "marketplace_price_recommendations", ["recommendation_type"])

    op.create_table(
        "marketplace_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_offer_identifier", sa.String(length=255), nullable=False),
        sa.Column("offer_status", sa.String(length=24), nullable=False),
        sa.Column("offer_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("offer_currency", sa.String(length=8), nullable=False),
        sa.Column("buyer_identifier", sa.String(length=255), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "marketplace_account_id",
            "marketplace_offer_identifier",
            name="uq_marketplace_offer_identity",
        ),
    )
    op.create_index("ix_mkt_offer_org_received", "marketplace_offers", ["organization_id", "received_at", "id"])
    op.create_index(
        "ix_mkt_offer_org_listing_received",
        "marketplace_offers",
        ["organization_id", "marketplace_listing_draft_id", "received_at", "id"],
    )
    op.create_index("ix_mkt_offer_org_status_received", "marketplace_offers", ["organization_id", "offer_status", "received_at", "id"])
    op.create_index(op.f("ix_marketplace_offers_buyer_identifier"), "marketplace_offers", ["buyer_identifier"])
    op.create_index(op.f("ix_marketplace_offers_marketplace_account_id"), "marketplace_offers", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_offers_marketplace_listing_draft_id"), "marketplace_offers", ["marketplace_listing_draft_id"])
    op.create_index(op.f("ix_marketplace_offers_offer_currency"), "marketplace_offers", ["offer_currency"])
    op.create_index(op.f("ix_marketplace_offers_offer_status"), "marketplace_offers", ["offer_status"])
    op.create_index(op.f("ix_marketplace_offers_organization_id"), "marketplace_offers", ["organization_id"])
    op.create_index(op.f("ix_marketplace_offers_marketplace_offer_identifier"), "marketplace_offers", ["marketplace_offer_identifier"])

    op.create_table(
        "marketplace_pricing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_pricing_event_org_created", "marketplace_pricing_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_pricing_event_org_type_created",
        "marketplace_pricing_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_pricing_events_actor_user_id"), "marketplace_pricing_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_pricing_events_event_type"), "marketplace_pricing_events", ["event_type"])
    op.create_index(op.f("ix_marketplace_pricing_events_marketplace_account_id"), "marketplace_pricing_events", ["marketplace_account_id"])
    op.create_index(
        op.f("ix_marketplace_pricing_events_marketplace_listing_draft_id"),
        "marketplace_pricing_events",
        ["marketplace_listing_draft_id"],
    )
    op.create_index(op.f("ix_marketplace_pricing_events_organization_id"), "marketplace_pricing_events", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_pricing_events_organization_id"), table_name="marketplace_pricing_events")
    op.drop_index(op.f("ix_marketplace_pricing_events_marketplace_listing_draft_id"), table_name="marketplace_pricing_events")
    op.drop_index(op.f("ix_marketplace_pricing_events_marketplace_account_id"), table_name="marketplace_pricing_events")
    op.drop_index(op.f("ix_marketplace_pricing_events_event_type"), table_name="marketplace_pricing_events")
    op.drop_index(op.f("ix_marketplace_pricing_events_actor_user_id"), table_name="marketplace_pricing_events")
    op.drop_index("ix_mkt_pricing_event_org_type_created", table_name="marketplace_pricing_events")
    op.drop_index("ix_mkt_pricing_event_org_created", table_name="marketplace_pricing_events")
    op.drop_table("marketplace_pricing_events")

    op.drop_index(op.f("ix_marketplace_offers_marketplace_offer_identifier"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_organization_id"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_offer_status"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_offer_currency"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_marketplace_listing_draft_id"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_marketplace_account_id"), table_name="marketplace_offers")
    op.drop_index(op.f("ix_marketplace_offers_buyer_identifier"), table_name="marketplace_offers")
    op.drop_index("ix_mkt_offer_org_status_received", table_name="marketplace_offers")
    op.drop_index("ix_mkt_offer_org_listing_received", table_name="marketplace_offers")
    op.drop_index("ix_mkt_offer_org_received", table_name="marketplace_offers")
    op.drop_table("marketplace_offers")

    op.drop_index(op.f("ix_marketplace_price_recommendations_recommendation_type"), table_name="marketplace_price_recommendations")
    op.drop_index(op.f("ix_marketplace_price_recommendations_recommendation_status"), table_name="marketplace_price_recommendations")
    op.drop_index(op.f("ix_marketplace_price_recommendations_organization_id"), table_name="marketplace_price_recommendations")
    op.drop_index(
        op.f("ix_marketplace_price_recommendations_marketplace_listing_draft_id"),
        table_name="marketplace_price_recommendations",
    )
    op.drop_index(op.f("ix_marketplace_price_recommendations_marketplace_account_id"), table_name="marketplace_price_recommendations")
    op.drop_index(op.f("ix_marketplace_price_recommendations_inventory_item_id"), table_name="marketplace_price_recommendations")
    op.drop_index("ix_mkt_pricing_rec_org_account_generated", table_name="marketplace_price_recommendations")
    op.drop_index("ix_mkt_pricing_rec_org_status_generated", table_name="marketplace_price_recommendations")
    op.drop_index("ix_mkt_pricing_rec_org_listing_generated", table_name="marketplace_price_recommendations")
    op.drop_index("ix_mkt_pricing_rec_org_generated", table_name="marketplace_price_recommendations")
    op.drop_table("marketplace_price_recommendations")

    op.drop_index(op.f("ix_marketplace_pricing_rules_rule_status"), table_name="marketplace_pricing_rules")
    op.drop_index(op.f("ix_marketplace_pricing_rules_rule_key"), table_name="marketplace_pricing_rules")
    op.drop_index(op.f("ix_marketplace_pricing_rules_organization_id"), table_name="marketplace_pricing_rules")
    op.drop_index(op.f("ix_marketplace_pricing_rules_created_by_user_id"), table_name="marketplace_pricing_rules")
    op.drop_index("ix_mkt_pricing_rule_org_status_updated", table_name="marketplace_pricing_rules")
    op.drop_index("ix_mkt_pricing_rule_org_updated", table_name="marketplace_pricing_rules")
    op.drop_table("marketplace_pricing_rules")
