from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261007_0213"
down_revision = "20261006_0212"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_spec_certification_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_score", sa.Float(), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=False),
        sa.Column("ai_eval_score", sa.Float(), nullable=False),
        sa.Column("top20_score", sa.Float(), nullable=False),
        sa.Column("dashboard_score", sa.Float(), nullable=False),
        sa.Column("automation_score", sa.Float(), nullable=False),
        sa.Column("determinism_score", sa.Float(), nullable=False),
        sa.Column("operations_score", sa.Float(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("certification_result", sa.String(length=32), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_spec_cert_run_started", "ai_spec_certification_run", ["started_at", "id"])
    op.create_index("ix_ai_spec_cert_run_result", "ai_spec_certification_run", ["certification_result", "id"])
    op.create_index(
        op.f("ix_ai_spec_certification_run_owner_user_id"),
        "ai_spec_certification_run",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_spec_certification_run_owner_user_id"), table_name="ai_spec_certification_run")
    op.drop_index("ix_ai_spec_cert_run_result", table_name="ai_spec_certification_run")
    op.drop_index("ix_ai_spec_cert_run_started", table_name="ai_spec_certification_run")
    op.drop_table("ai_spec_certification_run")
