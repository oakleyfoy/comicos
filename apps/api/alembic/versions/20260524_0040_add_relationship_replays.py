"""Add relationship replay run and item tables.

Revision ID: 20260524_0040
Revises: 20260524_0039
Create Date: 2026-05-24 02:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260524_0040"
down_revision: str | None = "20260524_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "relationship_replay_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("changed_items", sa.Integer(), nullable=False),
        sa.Column("unchanged_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("replay_version", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_relationship_replay_run_replay_type"), "relationship_replay_run", ["replay_type"], unique=False)
    op.create_index(op.f("ix_relationship_replay_run_status"), "relationship_replay_run", ["status"], unique=False)
    op.create_index(op.f("ix_relationship_replay_run_created_by"), "relationship_replay_run", ["created_by"], unique=False)
    op.create_index(op.f("ix_relationship_replay_run_replay_version"), "relationship_replay_run", ["replay_version"], unique=False)

    op.create_table(
        "relationship_replay_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("replay_run_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=True),
        sa.Column("relationship_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("previous_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("replay_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("diff_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["replay_run_id"], ["relationship_replay_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("replay_run_id", "relationship_key", name="uq_relationship_replay_item_run_key"),
    )
    op.create_index(op.f("ix_relationship_replay_item_replay_run_id"), "relationship_replay_item", ["replay_run_id"], unique=False)
    op.create_index(op.f("ix_relationship_replay_item_cover_image_id"), "relationship_replay_item", ["cover_image_id"], unique=False)
    op.create_index(op.f("ix_relationship_replay_item_relationship_key"), "relationship_replay_item", ["relationship_key"], unique=False)
    op.create_index(op.f("ix_relationship_replay_item_status"), "relationship_replay_item", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_relationship_replay_item_status"), table_name="relationship_replay_item")
    op.drop_index(op.f("ix_relationship_replay_item_relationship_key"), table_name="relationship_replay_item")
    op.drop_index(op.f("ix_relationship_replay_item_cover_image_id"), table_name="relationship_replay_item")
    op.drop_index(op.f("ix_relationship_replay_item_replay_run_id"), table_name="relationship_replay_item")
    op.drop_table("relationship_replay_item")

    op.drop_index(op.f("ix_relationship_replay_run_replay_version"), table_name="relationship_replay_run")
    op.drop_index(op.f("ix_relationship_replay_run_created_by"), table_name="relationship_replay_run")
    op.drop_index(op.f("ix_relationship_replay_run_status"), table_name="relationship_replay_run")
    op.drop_index(op.f("ix_relationship_replay_run_replay_type"), table_name="relationship_replay_run")
    op.drop_table("relationship_replay_run")
