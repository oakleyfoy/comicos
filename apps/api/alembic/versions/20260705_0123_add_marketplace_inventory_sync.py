"""add marketplace inventory sync foundation

Revision ID: 20260705_0123
Revises: 20260704_0122
Create Date: 2026-07-05 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260705_0123"
down_revision = "20260704_0122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_inventory_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("sync_run_type", sa.String(length=32), nullable=False),
        sa.Column("sync_status", sa.String(length=24), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("conflicts_detected", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_inventory_sync_run_org_started", "marketplace_inventory_sync_runs", ["organization_id", "started_at", "id"])
    op.create_index(
        "ix_mkt_inventory_sync_run_org_account_started",
        "marketplace_inventory_sync_runs",
        ["organization_id", "marketplace_account_id", "started_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_inventory_sync_runs_marketplace_account_id"), "marketplace_inventory_sync_runs", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_inventory_sync_runs_organization_id"), "marketplace_inventory_sync_runs", ["organization_id"])
    op.create_index(op.f("ix_marketplace_inventory_sync_runs_sync_run_type"), "marketplace_inventory_sync_runs", ["sync_run_type"])
    op.create_index(op.f("ix_marketplace_inventory_sync_runs_sync_status"), "marketplace_inventory_sync_runs", ["sync_status"])

    op.create_table(
        "marketplace_inventory_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_draft_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_listing_identifier", sa.String(length=255), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("local_quantity", sa.Integer(), nullable=False),
        sa.Column("marketplace_quantity", sa.Integer(), nullable=False),
        sa.Column("sync_status", sa.String(length=24), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["marketplace_listing_draft_id"], ["marketplace_listing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "marketplace_account_id",
            "marketplace_listing_draft_id",
            name="uq_marketplace_inventory_state_account_draft",
        ),
    )
    op.create_index(
        "ix_mkt_inventory_state_org_status_created",
        "marketplace_inventory_states",
        ["organization_id", "sync_status", "created_at", "id"],
    )
    op.create_index(
        "ix_mkt_inventory_state_org_account_created",
        "marketplace_inventory_states",
        ["organization_id", "marketplace_account_id", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_inventory_states_created_at"), "marketplace_inventory_states", ["created_at"])
    op.create_index(op.f("ix_marketplace_inventory_states_inventory_item_id"), "marketplace_inventory_states", ["inventory_item_id"])
    op.create_index(op.f("ix_marketplace_inventory_states_marketplace_account_id"), "marketplace_inventory_states", ["marketplace_account_id"])
    op.create_index(
        op.f("ix_marketplace_inventory_states_marketplace_listing_draft_id"),
        "marketplace_inventory_states",
        ["marketplace_listing_draft_id"],
    )
    op.create_index(
        op.f("ix_marketplace_inventory_states_marketplace_listing_identifier"),
        "marketplace_inventory_states",
        ["marketplace_listing_identifier"],
    )
    op.create_index(op.f("ix_marketplace_inventory_states_organization_id"), "marketplace_inventory_states", ["organization_id"])
    op.create_index(op.f("ix_marketplace_inventory_states_sync_status"), "marketplace_inventory_states", ["sync_status"])

    op.create_table(
        "marketplace_inventory_conflicts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_inventory_state_id", sa.Integer(), nullable=False),
        sa.Column("conflict_type", sa.String(length=40), nullable=False),
        sa.Column("local_value_json", sa.JSON(), nullable=False),
        sa.Column("marketplace_value_json", sa.JSON(), nullable=False),
        sa.Column("conflict_status", sa.String(length=24), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["marketplace_inventory_state_id"], ["marketplace_inventory_states.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mkt_inventory_conflict_org_detected",
        "marketplace_inventory_conflicts",
        ["organization_id", "detected_at", "id"],
    )
    op.create_index(
        "ix_mkt_inventory_conflict_state_detected",
        "marketplace_inventory_conflicts",
        ["marketplace_inventory_state_id", "detected_at", "id"],
    )
    op.create_index(
        "ix_mkt_inventory_conflict_org_status_detected",
        "marketplace_inventory_conflicts",
        ["organization_id", "conflict_status", "detected_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_inventory_conflicts_conflict_status"), "marketplace_inventory_conflicts", ["conflict_status"])
    op.create_index(op.f("ix_marketplace_inventory_conflicts_conflict_type"), "marketplace_inventory_conflicts", ["conflict_type"])
    op.create_index(
        op.f("ix_marketplace_inventory_conflicts_marketplace_inventory_state_id"),
        "marketplace_inventory_conflicts",
        ["marketplace_inventory_state_id"],
    )
    op.create_index(op.f("ix_marketplace_inventory_conflicts_organization_id"), "marketplace_inventory_conflicts", ["organization_id"])

    op.create_table(
        "marketplace_inventory_sync_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=True),
        sa.Column("sync_run_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["marketplace_account_id"], ["marketplace_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sync_run_id"], ["marketplace_inventory_sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mkt_inventory_sync_event_org_created", "marketplace_inventory_sync_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_inventory_sync_event_account_created",
        "marketplace_inventory_sync_events",
        ["marketplace_account_id", "created_at", "id"],
    )
    op.create_index("ix_mkt_inventory_sync_event_run_created", "marketplace_inventory_sync_events", ["sync_run_id", "created_at", "id"])
    op.create_index(
        "ix_mkt_inventory_sync_event_org_type_created",
        "marketplace_inventory_sync_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_marketplace_inventory_sync_events_actor_user_id"), "marketplace_inventory_sync_events", ["actor_user_id"])
    op.create_index(op.f("ix_marketplace_inventory_sync_events_event_type"), "marketplace_inventory_sync_events", ["event_type"])
    op.create_index(op.f("ix_marketplace_inventory_sync_events_marketplace_account_id"), "marketplace_inventory_sync_events", ["marketplace_account_id"])
    op.create_index(op.f("ix_marketplace_inventory_sync_events_organization_id"), "marketplace_inventory_sync_events", ["organization_id"])
    op.create_index(op.f("ix_marketplace_inventory_sync_events_sync_run_id"), "marketplace_inventory_sync_events", ["sync_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_marketplace_inventory_sync_events_sync_run_id"), table_name="marketplace_inventory_sync_events")
    op.drop_index(op.f("ix_marketplace_inventory_sync_events_organization_id"), table_name="marketplace_inventory_sync_events")
    op.drop_index(op.f("ix_marketplace_inventory_sync_events_marketplace_account_id"), table_name="marketplace_inventory_sync_events")
    op.drop_index(op.f("ix_marketplace_inventory_sync_events_event_type"), table_name="marketplace_inventory_sync_events")
    op.drop_index(op.f("ix_marketplace_inventory_sync_events_actor_user_id"), table_name="marketplace_inventory_sync_events")
    op.drop_index("ix_mkt_inventory_sync_event_org_type_created", table_name="marketplace_inventory_sync_events")
    op.drop_index("ix_mkt_inventory_sync_event_run_created", table_name="marketplace_inventory_sync_events")
    op.drop_index("ix_mkt_inventory_sync_event_account_created", table_name="marketplace_inventory_sync_events")
    op.drop_index("ix_mkt_inventory_sync_event_org_created", table_name="marketplace_inventory_sync_events")
    op.drop_table("marketplace_inventory_sync_events")

    op.drop_index(op.f("ix_marketplace_inventory_conflicts_organization_id"), table_name="marketplace_inventory_conflicts")
    op.drop_index(op.f("ix_marketplace_inventory_conflicts_marketplace_inventory_state_id"), table_name="marketplace_inventory_conflicts")
    op.drop_index(op.f("ix_marketplace_inventory_conflicts_conflict_type"), table_name="marketplace_inventory_conflicts")
    op.drop_index(op.f("ix_marketplace_inventory_conflicts_conflict_status"), table_name="marketplace_inventory_conflicts")
    op.drop_index("ix_mkt_inventory_conflict_org_status_detected", table_name="marketplace_inventory_conflicts")
    op.drop_index("ix_mkt_inventory_conflict_state_detected", table_name="marketplace_inventory_conflicts")
    op.drop_index("ix_mkt_inventory_conflict_org_detected", table_name="marketplace_inventory_conflicts")
    op.drop_table("marketplace_inventory_conflicts")

    op.drop_index(op.f("ix_marketplace_inventory_states_sync_status"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_organization_id"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_marketplace_listing_identifier"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_marketplace_listing_draft_id"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_marketplace_account_id"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_inventory_item_id"), table_name="marketplace_inventory_states")
    op.drop_index(op.f("ix_marketplace_inventory_states_created_at"), table_name="marketplace_inventory_states")
    op.drop_index("ix_mkt_inventory_state_org_account_created", table_name="marketplace_inventory_states")
    op.drop_index("ix_mkt_inventory_state_org_status_created", table_name="marketplace_inventory_states")
    op.drop_table("marketplace_inventory_states")

    op.drop_index(op.f("ix_marketplace_inventory_sync_runs_sync_status"), table_name="marketplace_inventory_sync_runs")
    op.drop_index(op.f("ix_marketplace_inventory_sync_runs_sync_run_type"), table_name="marketplace_inventory_sync_runs")
    op.drop_index(op.f("ix_marketplace_inventory_sync_runs_organization_id"), table_name="marketplace_inventory_sync_runs")
    op.drop_index(op.f("ix_marketplace_inventory_sync_runs_marketplace_account_id"), table_name="marketplace_inventory_sync_runs")
    op.drop_index("ix_mkt_inventory_sync_run_org_account_started", table_name="marketplace_inventory_sync_runs")
    op.drop_index("ix_mkt_inventory_sync_run_org_started", table_name="marketplace_inventory_sync_runs")
    op.drop_table("marketplace_inventory_sync_runs")
