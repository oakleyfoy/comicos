"""eBay Marketplace Account Deletion compliance audit log

Revision ID: 20260605_0231
Revises: 20260615_0230
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260605_0231"
down_revision = "20260615_0230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ebay_account_deletion_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("external_notification_id", sa.String(length=128), nullable=True),
        sa.Column("payload_digest", sa.String(length=128), nullable=True),
        sa.Column("noop_action", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ebay_acct_del_audit_kind_created",
        "ebay_account_deletion_audit_log",
        ["event_kind", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_ebay_acct_del_audit_notif_id",
        "ebay_account_deletion_audit_log",
        ["external_notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ebay_account_deletion_audit_log_event_kind"),
        "ebay_account_deletion_audit_log",
        ["event_kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ebay_account_deletion_audit_log_event_kind"), table_name="ebay_account_deletion_audit_log")
    op.drop_index("ix_ebay_acct_del_audit_notif_id", table_name="ebay_account_deletion_audit_log")
    op.drop_index("ix_ebay_acct_del_audit_kind_created", table_name="ebay_account_deletion_audit_log")
    op.drop_table("ebay_account_deletion_audit_log")
