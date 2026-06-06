"""add p80 mobile operations

Revision ID: 20260607_0246
Revises: 20260607_0245
Create Date: 2026-06-07 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260607_0246"
down_revision = "20260607_0245"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p80_mobile_intake_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("intake_mode", sa.String(length=16), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expected_count", sa.Integer(), nullable=False),
        sa.Column("scanned_count", sa.Integer(), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_scan_count", sa.Integer(), nullable=False),
        sa.Column("unknown_scan_count", sa.Integer(), nullable=False),
        sa.Column("scans_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["customer_order.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p80_intake_owner_created", "p80_mobile_intake_session", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_p80_mobile_intake_session_owner_user_id"), "p80_mobile_intake_session", ["owner_user_id"])
    op.create_index(op.f("ix_p80_mobile_intake_session_intake_mode"), "p80_mobile_intake_session", ["intake_mode"])
    op.create_index(op.f("ix_p80_mobile_intake_session_order_id"), "p80_mobile_intake_session", ["order_id"])
    op.create_index(op.f("ix_p80_mobile_intake_session_status"), "p80_mobile_intake_session", ["status"])

    op.create_table(
        "p80_mobile_audit_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("p79_audit_id", sa.Integer(), nullable=False),
        sa.Column("scope_box_id", sa.Integer(), nullable=True),
        sa.Column("scope_location_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_p80_audit_link_owner", "p80_mobile_audit_link", ["owner_user_id", "p79_audit_id", "id"])
    op.create_index(op.f("ix_p80_mobile_audit_link_owner_user_id"), "p80_mobile_audit_link", ["owner_user_id"])
    op.create_index(op.f("ix_p80_mobile_audit_link_p79_audit_id"), "p80_mobile_audit_link", ["p79_audit_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_p80_mobile_audit_link_p79_audit_id"), table_name="p80_mobile_audit_link")
    op.drop_index(op.f("ix_p80_mobile_audit_link_owner_user_id"), table_name="p80_mobile_audit_link")
    op.drop_index("ix_p80_audit_link_owner", table_name="p80_mobile_audit_link")
    op.drop_table("p80_mobile_audit_link")
    op.drop_index(op.f("ix_p80_mobile_intake_session_status"), table_name="p80_mobile_intake_session")
    op.drop_index(op.f("ix_p80_mobile_intake_session_order_id"), table_name="p80_mobile_intake_session")
    op.drop_index(op.f("ix_p80_mobile_intake_session_intake_mode"), table_name="p80_mobile_intake_session")
    op.drop_index(op.f("ix_p80_mobile_intake_session_owner_user_id"), table_name="p80_mobile_intake_session")
    op.drop_index("ix_p80_intake_owner_created", table_name="p80_mobile_intake_session")
    op.drop_table("p80_mobile_intake_session")
