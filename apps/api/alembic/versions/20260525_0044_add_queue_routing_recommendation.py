"""Add deterministic queue-routing recommendation snapshots (P34-05).

Revision ID: 20260525_0044
Revises: 20260525_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0044"
down_revision: str | None = "20260525_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "queue_routing_recommendation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_session_item_id", sa.Integer(), nullable=True),
        sa.Column("cover_image_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=48), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("routing_status", sa.String(length=20), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["scan_session_item_id"], ["scan_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_session_item_id", name="uq_queue_routing_recommendation_session_item"),
    )
    op.create_index(
        op.f("ix_queue_routing_recommendation_cover_image_id"),
        "queue_routing_recommendation",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_routing_recommendation_priority"),
        "queue_routing_recommendation",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_routing_recommendation_recommendation_type"),
        "queue_routing_recommendation",
        ["recommendation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_routing_recommendation_routing_status"),
        "queue_routing_recommendation",
        ["routing_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_routing_recommendation_scan_session_item_id"),
        "queue_routing_recommendation",
        ["scan_session_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_queue_routing_recommendation_scan_session_item_id"), table_name="queue_routing_recommendation")
    op.drop_index(op.f("ix_queue_routing_recommendation_routing_status"), table_name="queue_routing_recommendation")
    op.drop_index(op.f("ix_queue_routing_recommendation_recommendation_type"), table_name="queue_routing_recommendation")
    op.drop_index(op.f("ix_queue_routing_recommendation_priority"), table_name="queue_routing_recommendation")
    op.drop_index(op.f("ix_queue_routing_recommendation_cover_image_id"), table_name="queue_routing_recommendation")
    op.drop_table("queue_routing_recommendation")

