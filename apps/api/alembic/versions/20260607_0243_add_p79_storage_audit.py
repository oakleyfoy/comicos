"""add P79-02 storage audit

Revision ID: 20260607_0243
Revises: 20260607_0242
Create Date: 2026-06-07 02:43:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0243"
down_revision = "20260607_0242"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p79_storage_audit_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("audit_name", sa.String(length=160), nullable=False),
        sa.Column("scope_kind", sa.String(length=16), nullable=False),
        sa.Column("scope_location_id", sa.Integer(), nullable=True),
        sa.Column("scope_box_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_count", sa.Integer(), nullable=False),
        sa.Column("verified_count", sa.Integer(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.Column("unexpected_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scope_location_id"], ["p79_storage_location.id"]),
        sa.ForeignKeyConstraint(["scope_box_id"], ["p79_storage_box.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_audit_session_owner",
        "p79_storage_audit_session",
        ["owner_user_id", "started_at", "id"],
    )

    op.create_table(
        "p79_storage_audit_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_session_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("storage_box_id", sa.Integer(), nullable=True),
        sa.Column("slot_number", sa.Integer(), nullable=True),
        sa.Column("entry_status", sa.String(length=16), nullable=False),
        sa.Column("title_snapshot", sa.String(length=256), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["audit_session_id"], ["p79_storage_audit_session.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["storage_box_id"], ["p79_storage_box.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p79_audit_entry_session",
        "p79_storage_audit_entry",
        ["audit_session_id", "entry_status", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p79_audit_entry_session", table_name="p79_storage_audit_entry")
    op.drop_table("p79_storage_audit_entry")
    op.drop_index("ix_p79_audit_session_owner", table_name="p79_storage_audit_session")
    op.drop_table("p79_storage_audit_session")
