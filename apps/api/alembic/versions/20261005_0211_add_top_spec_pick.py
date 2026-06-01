from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261005_0211"
down_revision = "20261004_0210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "top_spec_pick",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=True),
        sa.Column("spec_input_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("suggested_quantity", sa.Integer(), nullable=True),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["spec_input_id"], ["spec_input.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "rank", name="uq_top_spec_pick_owner_rank"),
        sa.UniqueConstraint("owner_user_id", "spec_input_id", name="uq_top_spec_pick_owner_spec_input"),
    )
    op.create_index("ix_top_spec_pick_owner_created", "top_spec_pick", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_top_spec_pick_owner_score", "top_spec_pick", ["owner_user_id", "final_score", "id"])
    op.create_index(op.f("ix_top_spec_pick_owner_user_id"), "top_spec_pick", ["owner_user_id"])
    op.create_index(op.f("ix_top_spec_pick_rank"), "top_spec_pick", ["rank"])
    op.create_index(op.f("ix_top_spec_pick_release_id"), "top_spec_pick", ["release_id"])
    op.create_index(op.f("ix_top_spec_pick_spec_input_id"), "top_spec_pick", ["spec_input_id"])
    op.create_index(op.f("ix_top_spec_pick_publisher"), "top_spec_pick", ["publisher"])
    op.create_index(op.f("ix_top_spec_pick_final_score"), "top_spec_pick", ["final_score"])
    op.create_index(op.f("ix_top_spec_pick_risk_level"), "top_spec_pick", ["risk_level"])
    op.create_index(op.f("ix_top_spec_pick_foc_date"), "top_spec_pick", ["foc_date"])
    op.create_index(op.f("ix_top_spec_pick_release_date"), "top_spec_pick", ["release_date"])


def downgrade() -> None:
    op.drop_index(op.f("ix_top_spec_pick_release_date"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_foc_date"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_risk_level"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_final_score"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_publisher"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_spec_input_id"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_release_id"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_rank"), table_name="top_spec_pick")
    op.drop_index(op.f("ix_top_spec_pick_owner_user_id"), table_name="top_spec_pick")
    op.drop_index("ix_top_spec_pick_owner_score", table_name="top_spec_pick")
    op.drop_index("ix_top_spec_pick_owner_created", table_name="top_spec_pick")
    op.drop_table("top_spec_pick")
