from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260911_0187"
down_revision = "20260910_0186"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exit_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("candidate_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("estimated_fmv", sa.Float(), nullable=False),
        sa.Column("acquisition_cost", sa.Float(), nullable=False),
        sa.Column("unrealized_gain", sa.Float(), nullable=False),
        sa.Column("candidate_reason", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exit_candidate_owner_item", "exit_candidate", ["owner_user_id", "inventory_item_id", "created_at", "id"])
    op.create_index("ix_exit_candidate_owner_reason", "exit_candidate", ["owner_user_id", "candidate_reason", "id"])
    op.create_index(op.f("ix_exit_candidate_owner_user_id"), "exit_candidate", ["owner_user_id"])
    op.create_index(op.f("ix_exit_candidate_inventory_item_id"), "exit_candidate", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_exit_candidate_inventory_item_id"), table_name="exit_candidate")
    op.drop_index(op.f("ix_exit_candidate_owner_user_id"), table_name="exit_candidate")
    op.drop_index("ix_exit_candidate_owner_reason", table_name="exit_candidate")
    op.drop_index("ix_exit_candidate_owner_item", table_name="exit_candidate")
    op.drop_table("exit_candidate")
