"""add live sale workflow foundation

Revision ID: 20260709_0127
Revises: 20260708_0126
Create Date: 2026-07-09 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260709_0127"
down_revision = "20260708_0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_sale_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("session_name", sa.String(length=255), nullable=False),
        sa.Column("session_status", sa.String(length=24), nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_sale_session_org_created", "live_sale_sessions", ["organization_id", "created_at", "id"])
    op.create_index("ix_live_sale_session_org_status_created", "live_sale_sessions", ["organization_id", "session_status", "created_at", "id"])
    op.create_index(op.f("ix_live_sale_sessions_created_by_user_id"), "live_sale_sessions", ["created_by_user_id"])
    op.create_index(op.f("ix_live_sale_sessions_marketplace_account_id"), "live_sale_sessions", ["marketplace_account_id"])
    op.create_index(op.f("ix_live_sale_sessions_organization_id"), "live_sale_sessions", ["organization_id"])
    op.create_index(op.f("ix_live_sale_sessions_session_status"), "live_sale_sessions", ["session_status"])

    op.create_table(
        "live_sale_queue_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("live_sale_session_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("item_status", sa.String(length=24), nullable=False),
        sa.Column("planned_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_sale_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["live_sale_session_id"], ["live_sale_sessions.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("live_sale_session_id", "inventory_item_id", name="uq_live_sale_queue_inventory"),
    )
    op.create_index("ix_live_sale_queue_org_position", "live_sale_queue_items", ["organization_id", "queue_position", "id"])
    op.create_index("ix_live_sale_queue_session_position", "live_sale_queue_items", ["live_sale_session_id", "queue_position", "id"])
    op.create_index("ix_live_sale_queue_org_status_position", "live_sale_queue_items", ["organization_id", "item_status", "queue_position", "id"])
    op.create_index(op.f("ix_live_sale_queue_items_inventory_item_id"), "live_sale_queue_items", ["inventory_item_id"])
    op.create_index(op.f("ix_live_sale_queue_items_item_status"), "live_sale_queue_items", ["item_status"])
    op.create_index(op.f("ix_live_sale_queue_items_live_sale_session_id"), "live_sale_queue_items", ["live_sale_session_id"])
    op.create_index(op.f("ix_live_sale_queue_items_marketplace_listing_draft_id"), "live_sale_queue_items", ["marketplace_listing_draft_id"])
    op.create_index(op.f("ix_live_sale_queue_items_organization_id"), "live_sale_queue_items", ["organization_id"])
    op.create_index(op.f("ix_live_sale_queue_items_queue_position"), "live_sale_queue_items", ["queue_position"])

    op.create_table(
        "live_sale_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("live_sale_session_id", sa.Integer(), nullable=False),
        sa.Column("live_sale_queue_item_id", sa.Integer(), nullable=False),
        sa.Column("buyer_identifier", sa.String(length=255), nullable=False),
        sa.Column("claim_status", sa.String(length=24), nullable=False),
        sa.Column("claimed_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["live_sale_queue_item_id"], ["live_sale_queue_items.id"]),
        sa.ForeignKeyConstraint(["live_sale_session_id"], ["live_sale_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("live_sale_session_id", "live_sale_queue_item_id", "buyer_identifier", name="uq_live_sale_claim_identity"),
    )
    op.create_index("ix_live_sale_claim_org_created", "live_sale_claims", ["organization_id", "created_at", "id"])
    op.create_index("ix_live_sale_claim_session_created", "live_sale_claims", ["live_sale_session_id", "created_at", "id"])
    op.create_index("ix_live_sale_claim_org_status_created", "live_sale_claims", ["organization_id", "claim_status", "created_at", "id"])
    op.create_index(op.f("ix_live_sale_claims_buyer_identifier"), "live_sale_claims", ["buyer_identifier"])
    op.create_index(op.f("ix_live_sale_claims_claim_status"), "live_sale_claims", ["claim_status"])
    op.create_index(op.f("ix_live_sale_claims_live_sale_queue_item_id"), "live_sale_claims", ["live_sale_queue_item_id"])
    op.create_index(op.f("ix_live_sale_claims_live_sale_session_id"), "live_sale_claims", ["live_sale_session_id"])
    op.create_index(op.f("ix_live_sale_claims_organization_id"), "live_sale_claims", ["organization_id"])

    op.create_table(
        "live_sale_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("live_sale_session_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["live_sale_session_id"], ["live_sale_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_sale_event_org_created", "live_sale_events", ["organization_id", "created_at", "id"])
    op.create_index("ix_live_sale_event_session_created", "live_sale_events", ["live_sale_session_id", "created_at", "id"])
    op.create_index("ix_live_sale_event_org_type_created", "live_sale_events", ["organization_id", "event_type", "created_at", "id"])
    op.create_index(op.f("ix_live_sale_events_actor_user_id"), "live_sale_events", ["actor_user_id"])
    op.create_index(op.f("ix_live_sale_events_event_type"), "live_sale_events", ["event_type"])
    op.create_index(op.f("ix_live_sale_events_live_sale_session_id"), "live_sale_events", ["live_sale_session_id"])
    op.create_index(op.f("ix_live_sale_events_organization_id"), "live_sale_events", ["organization_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_live_sale_events_organization_id"), table_name="live_sale_events")
    op.drop_index(op.f("ix_live_sale_events_live_sale_session_id"), table_name="live_sale_events")
    op.drop_index(op.f("ix_live_sale_events_event_type"), table_name="live_sale_events")
    op.drop_index(op.f("ix_live_sale_events_actor_user_id"), table_name="live_sale_events")
    op.drop_index("ix_live_sale_event_org_type_created", table_name="live_sale_events")
    op.drop_index("ix_live_sale_event_session_created", table_name="live_sale_events")
    op.drop_index("ix_live_sale_event_org_created", table_name="live_sale_events")
    op.drop_table("live_sale_events")

    op.drop_index(op.f("ix_live_sale_claims_organization_id"), table_name="live_sale_claims")
    op.drop_index(op.f("ix_live_sale_claims_live_sale_session_id"), table_name="live_sale_claims")
    op.drop_index(op.f("ix_live_sale_claims_live_sale_queue_item_id"), table_name="live_sale_claims")
    op.drop_index(op.f("ix_live_sale_claims_claim_status"), table_name="live_sale_claims")
    op.drop_index(op.f("ix_live_sale_claims_buyer_identifier"), table_name="live_sale_claims")
    op.drop_index("ix_live_sale_claim_org_status_created", table_name="live_sale_claims")
    op.drop_index("ix_live_sale_claim_session_created", table_name="live_sale_claims")
    op.drop_index("ix_live_sale_claim_org_created", table_name="live_sale_claims")
    op.drop_table("live_sale_claims")

    op.drop_index(op.f("ix_live_sale_queue_items_queue_position"), table_name="live_sale_queue_items")
    op.drop_index(op.f("ix_live_sale_queue_items_organization_id"), table_name="live_sale_queue_items")
    op.drop_index(op.f("ix_live_sale_queue_items_marketplace_listing_draft_id"), table_name="live_sale_queue_items")
    op.drop_index(op.f("ix_live_sale_queue_items_live_sale_session_id"), table_name="live_sale_queue_items")
    op.drop_index(op.f("ix_live_sale_queue_items_item_status"), table_name="live_sale_queue_items")
    op.drop_index(op.f("ix_live_sale_queue_items_inventory_item_id"), table_name="live_sale_queue_items")
    op.drop_index("ix_live_sale_queue_org_status_position", table_name="live_sale_queue_items")
    op.drop_index("ix_live_sale_queue_session_position", table_name="live_sale_queue_items")
    op.drop_index("ix_live_sale_queue_org_position", table_name="live_sale_queue_items")
    op.drop_table("live_sale_queue_items")

    op.drop_index(op.f("ix_live_sale_sessions_session_status"), table_name="live_sale_sessions")
    op.drop_index(op.f("ix_live_sale_sessions_organization_id"), table_name="live_sale_sessions")
    op.drop_index(op.f("ix_live_sale_sessions_marketplace_account_id"), table_name="live_sale_sessions")
    op.drop_index(op.f("ix_live_sale_sessions_created_by_user_id"), table_name="live_sale_sessions")
    op.drop_index("ix_live_sale_session_org_status_created", table_name="live_sale_sessions")
    op.drop_index("ix_live_sale_session_org_created", table_name="live_sale_sessions")
    op.drop_table("live_sale_sessions")
