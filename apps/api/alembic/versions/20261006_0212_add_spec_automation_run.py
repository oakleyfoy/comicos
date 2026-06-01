from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261006_0212"
down_revision = "20261005_0211"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_automation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("inputs_processed", sa.Integer(), nullable=False),
        sa.Column("baseline_scores_created", sa.Integer(), nullable=False),
        sa.Column("ai_evaluations_created", sa.Integer(), nullable=False),
        sa.Column("top_picks_created", sa.Integer(), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spec_automation_run_owner_started", "spec_automation_run", ["owner_user_id", "started_at", "id"])
    op.create_index("ix_spec_automation_run_owner_status", "spec_automation_run", ["owner_user_id", "status", "id"])
    op.create_index(op.f("ix_spec_automation_run_owner_user_id"), "spec_automation_run", ["owner_user_id"])
    op.create_index(op.f("ix_spec_automation_run_status"), "spec_automation_run", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_spec_automation_run_status"), table_name="spec_automation_run")
    op.drop_index(op.f("ix_spec_automation_run_owner_user_id"), table_name="spec_automation_run")
    op.drop_index("ix_spec_automation_run_owner_status", table_name="spec_automation_run")
    op.drop_index("ix_spec_automation_run_owner_started", table_name="spec_automation_run")
    op.drop_table("spec_automation_run")
