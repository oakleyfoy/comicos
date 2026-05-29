"""add marketplace listing engine foundation

Revision ID: 20260704_0122
Revises: 20260703_0121
Create Date: 2026-07-04 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260704_0122"
down_revision = "20260703_0121"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_listing_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("listing_title", sa.String(length=500), nullable=False),
        sa.Column("listing_description", sa.String(), nullable=True),
        sa.Column("listing_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("listing_currency", sa.String(length=8), nullable=False),
        sa.Column("listing_quantity", sa.Integer(), nullable=False),
        sa.Column("listing_status", sa.String(length=24), nullable=False),
        sa.Column("validation_status", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mkt_listing_draft_org_status_created",
        "marketplace_listing_drafts",
        ["organization_id", "listing_status", "created_at", "id"],
    )
    op.create_index(
        "ix_mkt_listing_draft_org_account_created",
        "marketplace_listing_drafts",
        ["organization_id", "marketplace_account_id", "created_at", "id"],
    )
    op.create_index(
        "ix_mkt_listing_draft_org_inventory_created",
        "marketplace_listing_drafts",
        ["organization_id", "inventory_item_id", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_listing_drafts_created_by_user_id"), "marketplace_listing_drafts", ["created_by_user_id"])
    op.create_index(op.f("ix_marketplace_listing_drafts_inventory_item_id"), "marketplace_listing_drafts", ["inventory_item_id"])
    op.create_index(op.f("ix_marketplace_listing_drafts_listing_status"), "marketplace_listing_drafts", ["listing_status"])
    op.create_index(op.f("ix_marketplace_listing_drafts_marketplace_account_id"), "marketplace_listing_drafts", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_listing_drafts_organization_id"), "marketplace_listing_drafts", ["organization_id"])
    op.create_index(op.f("ix_marketplace_listing_drafts_validation_status"), "marketplace_listing_drafts", ["validation_status"])

    op.create_table(
        "marketplace_listing_projections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_type", sa.String(length=32), nullable=False),
        sa.Column("projection_payload_json", sa.JSON(), nullable=False),
        sa.Column("projection_status", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mkt_listing_proj_draft_generated",
        "marketplace_listing_projections",
        ["marketplace_listing_draft_id", "generated_at", "id"],
    )
    op.create_index(
        "ix_mkt_listing_proj_org_type_generated",
        "marketplace_listing_projections",
        ["organization_id", "marketplace_type", "generated_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_listing_projections_marketplace_listing_draft_id"), "marketplace_listing_projections", ["marketplace_listing_draft_id"])
    op.create_index(op.f("ix_marketplace_listing_projections_marketplace_type"), "marketplace_listing_projections", ["marketplace_type"])
    op.create_index(op.f("ix_marketplace_listing_projections_organization_id"), "marketplace_listing_projections", ["organization_id"])
    op.create_index(op.f("ix_marketplace_listing_projections_projection_status"), "marketplace_listing_projections", ["projection_status"])

    op.create_table(
        "marketplace_listing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_listing_event_org_created", "marketplace_listing_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_mkt_listing_event_draft_created", "marketplace_listing_events", ["marketplace_listing_draft_id", "created_at", "id"])
    op.create_index("ix_mkt_listing_event_org_type_created", "marketplace_listing_events", ["organization_id", "event_type", "created_at", "id"])
    op.create_index("ix_mkt_listing_event_actor_created", "marketplace_listing_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_marketplace_listing_events_actor_user_id"), "marketplace_listing_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_listing_events_event_type"), "marketplace_listing_events", ["event_type"])
    op.create_index(op.f("ix_marketplace_listing_events_marketplace_listing_draft_id"), "marketplace_listing_events", ["marketplace_listing_draft_id"])
    op.create_index(op.f("ix_marketplace_listing_events_organization_id"), "marketplace_listing_events", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_listing_events_organization_id"), table_name="marketplace_listing_events")
    op.drop_index(op.f("ix_marketplace_listing_events_marketplace_listing_draft_id"), table_name="marketplace_listing_events")
    op.drop_index(op.f("ix_marketplace_listing_events_event_type"), table_name="marketplace_listing_events")
    op.drop_index(op.f("ix_marketplace_listing_events_actor_user_id"), table_name="marketplace_listing_events")
    op.drop_index("ix_mkt_listing_event_actor_created", table_name="marketplace_listing_events")
    op.drop_index("ix_mkt_listing_event_org_type_created", table_name="marketplace_listing_events")
    op.drop_index("ix_mkt_listing_event_draft_created", table_name="marketplace_listing_events")
    op.drop_index("ix_mkt_listing_event_org_created", table_name="marketplace_listing_events")
    op.drop_table("marketplace_listing_events")

    op.drop_index(op.f("ix_marketplace_listing_projections_projection_status"), table_name="marketplace_listing_projections")
    op.drop_index(op.f("ix_marketplace_listing_projections_organization_id"), table_name="marketplace_listing_projections")
    op.drop_index(op.f("ix_marketplace_listing_projections_marketplace_type"), table_name="marketplace_listing_projections")
    op.drop_index(op.f("ix_marketplace_listing_projections_marketplace_listing_draft_id"), table_name="marketplace_listing_projections")
    op.drop_index("ix_mkt_listing_proj_org_type_generated", table_name="marketplace_listing_projections")
    op.drop_index("ix_mkt_listing_proj_draft_generated", table_name="marketplace_listing_projections")
    op.drop_table("marketplace_listing_projections")

    op.drop_index(op.f("ix_marketplace_listing_drafts_validation_status"), table_name="marketplace_listing_drafts")
    op.drop_index(op.f("ix_marketplace_listing_drafts_organization_id"), table_name="marketplace_listing_drafts")
    op.drop_index(op.f("ix_marketplace_listing_drafts_marketplace_account_id"), table_name="marketplace_listing_drafts")
    op.drop_index(op.f("ix_marketplace_listing_drafts_listing_status"), table_name="marketplace_listing_drafts")
    op.drop_index(op.f("ix_marketplace_listing_drafts_inventory_item_id"), table_name="marketplace_listing_drafts")
    op.drop_index(op.f("ix_marketplace_listing_drafts_created_by_user_id"), table_name="marketplace_listing_drafts")
    op.drop_index("ix_mkt_listing_draft_org_inventory_created", table_name="marketplace_listing_drafts")
    op.drop_index("ix_mkt_listing_draft_org_account_created", table_name="marketplace_listing_drafts")
    op.drop_index("ix_mkt_listing_draft_org_status_created", table_name="marketplace_listing_drafts")
    op.drop_table("marketplace_listing_drafts")
