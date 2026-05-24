"""Add deterministic scan QA result snapshots (P34-04 routing / visibility).

Revision ID: 20260525_0043
Revises: 20260525_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0043"
down_revision: str | None = "20260525_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scan_qa_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_session_id", sa.Integer(), nullable=False),
        sa.Column("scan_session_item_id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=True),
        sa.Column("qa_classification", sa.String(length=48), nullable=False),
        sa.Column("routing_recommendation", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["scan_session_id"], ["scan_session.id"]),
        sa.ForeignKeyConstraint(["scan_session_item_id"], ["scan_session_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_session_item_id", name="uq_scan_qa_result_session_item"),
    )
    op.create_index(op.f("ix_scan_qa_result_cover_image_id"), "scan_qa_result", ["cover_image_id"], unique=False)
    op.create_index(
        op.f("ix_scan_qa_result_qa_classification"), "scan_qa_result", ["qa_classification"], unique=False
    )
    op.create_index(
        op.f("ix_scan_qa_result_routing_recommendation"),
        "scan_qa_result",
        ["routing_recommendation"],
        unique=False,
    )
    op.create_index(op.f("ix_scan_qa_result_scan_session_id"), "scan_qa_result", ["scan_session_id"], unique=False)
    op.create_index(op.f("ix_scan_qa_result_scan_session_item_id"), "scan_qa_result", ["scan_session_item_id"], unique=False)
    op.create_index(op.f("ix_scan_qa_result_severity"), "scan_qa_result", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scan_qa_result_severity"), table_name="scan_qa_result")
    op.drop_index(op.f("ix_scan_qa_result_scan_session_item_id"), table_name="scan_qa_result")
    op.drop_index(op.f("ix_scan_qa_result_scan_session_id"), table_name="scan_qa_result")
    op.drop_index(op.f("ix_scan_qa_result_routing_recommendation"), table_name="scan_qa_result")
    op.drop_index(op.f("ix_scan_qa_result_qa_classification"), table_name="scan_qa_result")
    op.drop_index(op.f("ix_scan_qa_result_cover_image_id"), table_name="scan_qa_result")
    op.drop_table("scan_qa_result")
