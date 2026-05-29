"""add convention mode

Revision ID: 20260716_0134
Revises: 20260715_0133
Create Date: 2026-07-16 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0134"
down_revision = "20260715_0133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "convention_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("session_name", sa.String(length=200), nullable=False),
        sa.Column("session_status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_convention_session_org_created", "convention_sessions", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_convention_session_org_status_created",
        "convention_sessions",
        ["organization_id", "session_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_convention_sessions_organization_id"), "convention_sessions", ["organization_id"])
    op.create_index(op.f("ix_convention_sessions_session_status"), "convention_sessions", ["session_status"])

    op.create_table(
        "convention_booths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("convention_session_id", sa.Integer(), nullable=False),
        sa.Column("booth_name", sa.String(length=200), nullable=False),
        sa.Column("booth_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["convention_session_id"], ["convention_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_convention_booth_org_created", "convention_booths", ["organization_id", "created_at", "id"])
    op.create_index("ix_convention_booth_session_created", "convention_booths", ["convention_session_id", "created_at", "id"])
    op.create_index(
        "ix_convention_booth_org_status_created",
        "convention_booths",
        ["organization_id", "booth_status", "created_at", "id"],
    )
    op.create_index(op.f("ix_convention_booths_organization_id"), "convention_booths", ["organization_id"])
    op.create_index(op.f("ix_convention_booths_convention_session_id"), "convention_booths", ["convention_session_id"])
    op.create_index(op.f("ix_convention_booths_booth_status"), "convention_booths", ["booth_status"])

    op.create_table(
        "convention_inventory_stages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("convention_session_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("stage_status", sa.String(length=24), nullable=False),
        sa.Column("staged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["convention_session_id"], ["convention_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_convention_inv_stage_org_staged",
        "convention_inventory_stages",
        ["organization_id", "staged_at", "id"],
    )
    op.create_index(
        "ix_convention_inv_stage_session_staged",
        "convention_inventory_stages",
        ["convention_session_id", "staged_at", "id"],
    )
    op.create_index(
        "ix_convention_inv_stage_org_status_staged",
        "convention_inventory_stages",
        ["organization_id", "stage_status", "staged_at", "id"],
    )
    op.create_index(op.f("ix_convention_inventory_stages_organization_id"), "convention_inventory_stages", ["organization_id"])
    op.create_index(op.f("ix_convention_inventory_stages_convention_session_id"), "convention_inventory_stages", ["convention_session_id"])
    op.create_index(op.f("ix_convention_inventory_stages_inventory_item_id"), "convention_inventory_stages", ["inventory_item_id"])
    op.create_index(op.f("ix_convention_inventory_stages_stage_status"), "convention_inventory_stages", ["stage_status"])

    op.create_table(
        "convention_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("convention_session_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("activity_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["convention_session_id"], ["convention_sessions.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_convention_activity_org_created", "convention_activities", ["organization_id", "created_at", "id"])
    op.create_index("ix_convention_activity_session_created", "convention_activities", ["convention_session_id", "created_at", "id"])
    op.create_index(
        "ix_convention_activity_org_type_created",
        "convention_activities",
        ["organization_id", "activity_type", "created_at", "id"],
    )
    op.create_index(op.f("ix_convention_activities_organization_id"), "convention_activities", ["organization_id"])
    op.create_index(op.f("ix_convention_activities_convention_session_id"), "convention_activities", ["convention_session_id"])
    op.create_index(op.f("ix_convention_activities_activity_type"), "convention_activities", ["activity_type"])

    op.create_table(
        "convention_mode_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_convention_mode_event_org_created", "convention_mode_events", ["organization_id", "created_at", "id"])
    op.create_index(
        "ix_convention_mode_event_org_type_created",
        "convention_mode_events",
        ["organization_id", "event_type", "created_at", "id"],
    )
    op.create_index("ix_convention_mode_event_actor_created", "convention_mode_events", ["actor_user_id", "created_at", "id"])
    op.create_index(op.f("ix_convention_mode_events_organization_id"), "convention_mode_events", ["organization_id"])
    op.create_index(op.f("ix_convention_mode_events_actor_user_id"), "convention_mode_events", ["actor_user_id"])
    op.create_index(op.f("ix_convention_mode_events_event_type"), "convention_mode_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_convention_mode_events_event_type"), table_name="convention_mode_events")
    op.drop_index(op.f("ix_convention_mode_events_actor_user_id"), table_name="convention_mode_events")
    op.drop_index(op.f("ix_convention_mode_events_organization_id"), table_name="convention_mode_events")
    op.drop_index("ix_convention_mode_event_actor_created", table_name="convention_mode_events")
    op.drop_index("ix_convention_mode_event_org_type_created", table_name="convention_mode_events")
    op.drop_index("ix_convention_mode_event_org_created", table_name="convention_mode_events")
    op.drop_table("convention_mode_events")

    op.drop_index(op.f("ix_convention_activities_activity_type"), table_name="convention_activities")
    op.drop_index(op.f("ix_convention_activities_convention_session_id"), table_name="convention_activities")
    op.drop_index(op.f("ix_convention_activities_organization_id"), table_name="convention_activities")
    op.drop_index("ix_convention_activity_org_type_created", table_name="convention_activities")
    op.drop_index("ix_convention_activity_session_created", table_name="convention_activities")
    op.drop_index("ix_convention_activity_org_created", table_name="convention_activities")
    op.drop_table("convention_activities")

    op.drop_index(op.f("ix_convention_inventory_stages_stage_status"), table_name="convention_inventory_stages")
    op.drop_index(op.f("ix_convention_inventory_stages_inventory_item_id"), table_name="convention_inventory_stages")
    op.drop_index(op.f("ix_convention_inventory_stages_convention_session_id"), table_name="convention_inventory_stages")
    op.drop_index(op.f("ix_convention_inventory_stages_organization_id"), table_name="convention_inventory_stages")
    op.drop_index("ix_convention_inv_stage_org_status_staged", table_name="convention_inventory_stages")
    op.drop_index("ix_convention_inv_stage_session_staged", table_name="convention_inventory_stages")
    op.drop_index("ix_convention_inv_stage_org_staged", table_name="convention_inventory_stages")
    op.drop_table("convention_inventory_stages")

    op.drop_index(op.f("ix_convention_booths_booth_status"), table_name="convention_booths")
    op.drop_index(op.f("ix_convention_booths_convention_session_id"), table_name="convention_booths")
    op.drop_index(op.f("ix_convention_booths_organization_id"), table_name="convention_booths")
    op.drop_index("ix_convention_booth_org_status_created", table_name="convention_booths")
    op.drop_index("ix_convention_booth_session_created", table_name="convention_booths")
    op.drop_index("ix_convention_booth_org_created", table_name="convention_booths")
    op.drop_table("convention_booths")

    op.drop_index(op.f("ix_convention_sessions_session_status"), table_name="convention_sessions")
    op.drop_index(op.f("ix_convention_sessions_organization_id"), table_name="convention_sessions")
    op.drop_index("ix_convention_session_org_status_created", table_name="convention_sessions")
    op.drop_index("ix_convention_session_org_created", table_name="convention_sessions")
    op.drop_table("convention_sessions")
