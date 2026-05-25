"""P35-03 market sale normalization review queue.

Revision ID: 20260525_0049
Revises: 20260525_0048
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0049"
down_revision: str | None = "20260525_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_sale_record",
        sa.Column(
            "review_status",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.create_index(op.f("ix_market_sale_record_review_status"), "market_sale_record", ["review_status"], unique=False)

    op.create_table(
        "market_sale_review_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("before_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("after_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_sale_review_action_market_sale_record_id"),
        "market_sale_review_action",
        ["market_sale_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_review_action_action_type"),
        "market_sale_review_action",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_review_action_actor_user_id"),
        "market_sale_review_action",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_review_action_created_at"),
        "market_sale_review_action",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_sale_review_action_created_at"), table_name="market_sale_review_action")
    op.drop_index(op.f("ix_market_sale_review_action_actor_user_id"), table_name="market_sale_review_action")
    op.drop_index(op.f("ix_market_sale_review_action_action_type"), table_name="market_sale_review_action")
    op.drop_index(op.f("ix_market_sale_review_action_market_sale_record_id"), table_name="market_sale_review_action")
    op.drop_table("market_sale_review_action")

    op.drop_index(op.f("ix_market_sale_record_review_status"), table_name="market_sale_record")
    op.drop_column("market_sale_record", "review_status")
