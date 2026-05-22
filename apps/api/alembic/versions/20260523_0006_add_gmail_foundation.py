"""Add Gmail foundation tables.

Revision ID: 20260523_0006
Revises: 20260522_0005
Create Date: 2026-05-23 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0006"
down_revision: str | None = "20260522_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gmail_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gmail_email", sa.String(length=320), nullable=False),
        sa.Column("google_subject_id", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.String(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.String(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_subject_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_gmail_account_google_subject_id"),
        "gmail_account",
        ["google_subject_id"],
    )
    op.create_index(op.f("ix_gmail_account_user_id"), "gmail_account", ["user_id"])

    op.create_table(
        "gmail_import_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gmail_account_id", sa.Integer(), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("draft_import_id", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_import_id"], ["draft_import.id"]),
        sa.ForeignKeyConstraint(["gmail_account_id"], ["gmail_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_message_id"),
    )
    op.create_index(
        op.f("ix_gmail_import_record_draft_import_id"),
        "gmail_import_record",
        ["draft_import_id"],
    )
    op.create_index(
        op.f("ix_gmail_import_record_external_message_id"),
        "gmail_import_record",
        ["external_message_id"],
    )
    op.create_index(
        op.f("ix_gmail_import_record_gmail_account_id"),
        "gmail_import_record",
        ["gmail_account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_gmail_import_record_gmail_account_id"),
        table_name="gmail_import_record",
    )
    op.drop_index(
        op.f("ix_gmail_import_record_external_message_id"),
        table_name="gmail_import_record",
    )
    op.drop_index(
        op.f("ix_gmail_import_record_draft_import_id"),
        table_name="gmail_import_record",
    )
    op.drop_table("gmail_import_record")

    op.drop_index(op.f("ix_gmail_account_user_id"), table_name="gmail_account")
    op.drop_index(op.f("ix_gmail_account_google_subject_id"), table_name="gmail_account")
    op.drop_table("gmail_account")
