"""Add metadata audit history.

Revision ID: 20260523_0015
Revises: 20260523_0014
Create Date: 2026-05-24 05:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260523_0015"
down_revision: str | None = "20260523_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metadata_audit_action"), "metadata_audit", ["action"], unique=False)
    op.create_index(
        op.f("ix_metadata_audit_actor_user_id"),
        "metadata_audit",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_metadata_audit_entity_id"),
        "metadata_audit",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_metadata_audit_entity_type"),
        "metadata_audit",
        ["entity_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_metadata_audit_entity_type"), table_name="metadata_audit")
    op.drop_index(op.f("ix_metadata_audit_entity_id"), table_name="metadata_audit")
    op.drop_index(op.f("ix_metadata_audit_actor_user_id"), table_name="metadata_audit")
    op.drop_index(op.f("ix_metadata_audit_action"), table_name="metadata_audit")
    op.drop_table("metadata_audit")
