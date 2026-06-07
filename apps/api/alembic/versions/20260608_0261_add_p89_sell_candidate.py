"""add p89 sell candidate intelligence

Revision ID: 20260608_0261
Revises: 20260608_0260
Create Date: 2026-06-08 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0261"
down_revision = "20260608_0260"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p89_sell_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("sell_score", sa.Float(), nullable=False),
        sa.Column("hold_score", sa.Float(), nullable=False),
        sa.Column("grade_first_score", sa.Float(), nullable=False),
        sa.Column("monitor_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("estimated_sale_value", sa.Float(), nullable=False),
        sa.Column("estimated_profit", sa.Float(), nullable=False),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "inventory_copy_id", name="uq_p89_sell_candidate_copy"),
    )
    op.create_index(op.f("ix_p89_sell_candidate_owner_user_id"), "p89_sell_candidate", ["owner_user_id"])
    op.create_index(op.f("ix_p89_sell_candidate_inventory_copy_id"), "p89_sell_candidate", ["inventory_copy_id"])
    op.create_index(op.f("ix_p89_sell_candidate_recommendation"), "p89_sell_candidate", ["recommendation"])
    op.create_index(op.f("ix_p89_sell_candidate_confidence"), "p89_sell_candidate", ["confidence"])
    op.create_index(op.f("ix_p89_sell_candidate_status"), "p89_sell_candidate", ["status"])
    op.create_index("ix_p89_sell_cand_owner_rec", "p89_sell_candidate", ["owner_user_id", "recommendation", "status"])
    op.create_index("ix_p89_sell_cand_owner_score", "p89_sell_candidate", ["owner_user_id", "sell_score", "status"])


def downgrade() -> None:
    op.drop_index("ix_p89_sell_cand_owner_score", table_name="p89_sell_candidate")
    op.drop_index("ix_p89_sell_cand_owner_rec", table_name="p89_sell_candidate")
    op.drop_index(op.f("ix_p89_sell_candidate_status"), table_name="p89_sell_candidate")
    op.drop_index(op.f("ix_p89_sell_candidate_confidence"), table_name="p89_sell_candidate")
    op.drop_index(op.f("ix_p89_sell_candidate_recommendation"), table_name="p89_sell_candidate")
    op.drop_index(op.f("ix_p89_sell_candidate_inventory_copy_id"), table_name="p89_sell_candidate")
    op.drop_index(op.f("ix_p89_sell_candidate_owner_user_id"), table_name="p89_sell_candidate")
    op.drop_table("p89_sell_candidate")
