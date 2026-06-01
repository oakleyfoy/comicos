from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261003_0209"
down_revision = "20261002_0208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_baseline_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spec_input_id", sa.Integer(), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spec_input_id"], ["spec_input.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "spec_input_id", name="uq_spec_baseline_score_owner_input"),
    )
    op.create_index("ix_spec_baseline_owner_score", "spec_baseline_score", ["owner_user_id", "baseline_score", "id"])
    op.create_index("ix_spec_baseline_owner_created", "spec_baseline_score", ["owner_user_id", "created_at", "id"])
    op.create_index(op.f("ix_spec_baseline_score_owner_user_id"), "spec_baseline_score", ["owner_user_id"])
    op.create_index(op.f("ix_spec_baseline_score_spec_input_id"), "spec_baseline_score", ["spec_input_id"])
    op.create_index(op.f("ix_spec_baseline_score_baseline_score"), "spec_baseline_score", ["baseline_score"])
    op.create_index(op.f("ix_spec_baseline_score_risk_score"), "spec_baseline_score", ["risk_score"])


def downgrade() -> None:
    op.drop_index(op.f("ix_spec_baseline_score_risk_score"), table_name="spec_baseline_score")
    op.drop_index(op.f("ix_spec_baseline_score_baseline_score"), table_name="spec_baseline_score")
    op.drop_index(op.f("ix_spec_baseline_score_spec_input_id"), table_name="spec_baseline_score")
    op.drop_index(op.f("ix_spec_baseline_score_owner_user_id"), table_name="spec_baseline_score")
    op.drop_index("ix_spec_baseline_owner_created", table_name="spec_baseline_score")
    op.drop_index("ix_spec_baseline_owner_score", table_name="spec_baseline_score")
    op.drop_table("spec_baseline_score")
