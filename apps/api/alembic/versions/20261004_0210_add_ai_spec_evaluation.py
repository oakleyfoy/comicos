from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_0210"
down_revision = "20261003_0209"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_spec_evaluation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("spec_input_id", sa.Integer(), nullable=False),
        sa.Column("baseline_score_id", sa.Integer(), nullable=False),
        sa.Column("ai_score", sa.Float(), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("ai_rationale", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("evaluation_status", sa.String(length=16), nullable=False),
        sa.Column("prompt_inputs_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["spec_input_id"], ["spec_input.id"]),
        sa.ForeignKeyConstraint(["baseline_score_id"], ["spec_baseline_score.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "spec_input_id",
            "baseline_score_id",
            "prompt_version",
            name="uq_ai_spec_eval_owner_input_baseline_prompt",
        ),
    )
    op.create_index("ix_ai_spec_eval_owner_created", "ai_spec_evaluation", ["owner_user_id", "created_at", "id"])
    op.create_index("ix_ai_spec_eval_owner_score", "ai_spec_evaluation", ["owner_user_id", "ai_score", "id"])
    op.create_index(op.f("ix_ai_spec_evaluation_owner_user_id"), "ai_spec_evaluation", ["owner_user_id"])
    op.create_index(op.f("ix_ai_spec_evaluation_spec_input_id"), "ai_spec_evaluation", ["spec_input_id"])
    op.create_index(op.f("ix_ai_spec_evaluation_baseline_score_id"), "ai_spec_evaluation", ["baseline_score_id"])
    op.create_index(op.f("ix_ai_spec_evaluation_ai_score"), "ai_spec_evaluation", ["ai_score"])
    op.create_index(op.f("ix_ai_spec_evaluation_risk_level"), "ai_spec_evaluation", ["risk_level"])
    op.create_index(op.f("ix_ai_spec_evaluation_prompt_version"), "ai_spec_evaluation", ["prompt_version"])
    op.create_index(op.f("ix_ai_spec_evaluation_evaluation_status"), "ai_spec_evaluation", ["evaluation_status"])
    op.create_index(op.f("ix_ai_spec_evaluation_prompt_inputs_hash"), "ai_spec_evaluation", ["prompt_inputs_hash"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_spec_evaluation_prompt_inputs_hash"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_evaluation_status"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_prompt_version"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_risk_level"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_ai_score"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_baseline_score_id"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_spec_input_id"), table_name="ai_spec_evaluation")
    op.drop_index(op.f("ix_ai_spec_evaluation_owner_user_id"), table_name="ai_spec_evaluation")
    op.drop_index("ix_ai_spec_eval_owner_score", table_name="ai_spec_evaluation")
    op.drop_index("ix_ai_spec_eval_owner_created", table_name="ai_spec_evaluation")
    op.drop_table("ai_spec_evaluation")
