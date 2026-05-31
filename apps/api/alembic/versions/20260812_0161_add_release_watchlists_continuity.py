"""add release watchlists continuity

Revision ID: 20260812_0161
Revises: 20260811_0160
Create Date: 2026-08-12 02:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260812_0161"
down_revision = "20260811_0160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("first_issue_owned", sa.String(length=24), nullable=False),
        sa.Column("latest_issue_owned", sa.String(length=24), nullable=False),
        sa.Column("issue_count_owned", sa.Integer(), nullable=False),
        sa.Column("continuity_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_run_owner_user_id", "collection_run", ["owner_user_id"])
    op.create_index("ix_collection_run_publisher", "collection_run", ["publisher"])
    op.create_index("ix_collection_run_series_name", "collection_run", ["series_name"])
    op.create_index("ix_collection_run_continuity_status", "collection_run", ["continuity_status"])
    op.create_index("ix_collection_run_created_at", "collection_run", ["created_at"])
    op.create_index("ix_collection_run_owner_created", "collection_run", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_collection_run_publisher_series", "collection_run", ["publisher", "series_name", "id"])

    op.create_table(
        "collection_continuity_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("alert_status", sa.String(length=24), nullable=False),
        sa.Column("alert_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_continuity_alert_owner_user_id", "collection_continuity_alert", ["owner_user_id"])
    op.create_index("ix_collection_continuity_alert_release_issue_id", "collection_continuity_alert", ["release_issue_id"])
    op.create_index("ix_collection_continuity_alert_alert_type", "collection_continuity_alert", ["alert_type"])
    op.create_index("ix_collection_continuity_alert_alert_status", "collection_continuity_alert", ["alert_status"])
    op.create_index("ix_collection_continuity_alert_created_at", "collection_continuity_alert", ["created_at"])
    op.create_index(
        "ix_collection_continuity_alert_owner_created",
        "collection_continuity_alert",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_collection_continuity_alert_type_status",
        "collection_continuity_alert",
        ["alert_type", "alert_status", "id"],
    )

    op.create_table(
        "release_watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("watchlist_name", sa.String(length=160), nullable=False),
        sa.Column("watchlist_type", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "watchlist_name", "watchlist_type", name="uq_release_watchlist_owner_identity"),
    )
    op.create_index("ix_release_watchlist_owner_user_id", "release_watchlist", ["owner_user_id"])
    op.create_index("ix_release_watchlist_watchlist_type", "release_watchlist", ["watchlist_type"])
    op.create_index("ix_release_watchlist_created_at", "release_watchlist", ["created_at"])
    op.create_index("ix_release_watchlist_owner_created", "release_watchlist", ["owner_user_id", "created_at", "id"])

    op.create_table(
        "release_watchlist_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=True),
        sa.Column("series_name", sa.String(length=200), nullable=True),
        sa.Column("character_name", sa.String(length=160), nullable=True),
        sa.Column("creator_name", sa.String(length=160), nullable=True),
        sa.Column("keyword", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], ["release_watchlist.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "watchlist_id",
            "publisher",
            "series_name",
            "character_name",
            "creator_name",
            "keyword",
            name="uq_release_watchlist_item_signature",
        ),
    )
    op.create_index("ix_release_watchlist_item_watchlist_id", "release_watchlist_item", ["watchlist_id"])
    op.create_index("ix_release_watchlist_item_publisher", "release_watchlist_item", ["publisher"])
    op.create_index("ix_release_watchlist_item_series_name", "release_watchlist_item", ["series_name"])
    op.create_index("ix_release_watchlist_item_character_name", "release_watchlist_item", ["character_name"])
    op.create_index("ix_release_watchlist_item_creator_name", "release_watchlist_item", ["creator_name"])
    op.create_index("ix_release_watchlist_item_keyword", "release_watchlist_item", ["keyword"])
    op.create_index("ix_release_watchlist_item_created_at", "release_watchlist_item", ["created_at"])
    op.create_index(
        "ix_release_watchlist_item_watchlist_created",
        "release_watchlist_item",
        ["watchlist_id", "created_at", "id"],
    )

    op.create_table(
        "release_reminder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("reminder_type", sa.String(length=64), nullable=False),
        sa.Column("reminder_date", sa.Date(), nullable=False),
        sa.Column("reminder_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_reminder_owner_user_id", "release_reminder", ["owner_user_id"])
    op.create_index("ix_release_reminder_release_issue_id", "release_reminder", ["release_issue_id"])
    op.create_index("ix_release_reminder_reminder_type", "release_reminder", ["reminder_type"])
    op.create_index("ix_release_reminder_reminder_date", "release_reminder", ["reminder_date"])
    op.create_index("ix_release_reminder_reminder_status", "release_reminder", ["reminder_status"])
    op.create_index("ix_release_reminder_created_at", "release_reminder", ["created_at"])
    op.create_index("ix_release_reminder_owner_created", "release_reminder", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_release_reminder_type_date", "release_reminder", ["reminder_type", "reminder_date", "id"])

    op.create_table(
        "watchlist_agent_execution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("execution_uuid", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_uuid", name="uq_watchlist_agent_execution_uuid"),
    )
    op.create_index("ix_watchlist_agent_execution_owner_user_id", "watchlist_agent_execution", ["owner_user_id"])
    op.create_index("ix_watchlist_agent_execution_agent_code", "watchlist_agent_execution", ["agent_code"])
    op.create_index("ix_watchlist_agent_execution_execution_uuid", "watchlist_agent_execution", ["execution_uuid"])
    op.create_index("ix_watchlist_agent_execution_status", "watchlist_agent_execution", ["status"])
    op.create_index("ix_watchlist_agent_execution_created_at", "watchlist_agent_execution", ["created_at"])
    op.create_index(
        "ix_watchlist_agent_execution_owner_started",
        "watchlist_agent_execution",
        ["owner_user_id", "started_at", "id"],
    )
    op.create_index(
        "ix_watchlist_agent_execution_agent_started",
        "watchlist_agent_execution",
        ["agent_code", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("watchlist_agent_execution")
    op.drop_table("release_reminder")
    op.drop_table("release_watchlist_item")
    op.drop_table("release_watchlist")
    op.drop_table("collection_continuity_alert")
    op.drop_table("collection_run")
