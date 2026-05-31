from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260824_0174"
down_revision = "20260823_0173"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_list_automation_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_time", sa.String(length=8), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pull_list_automation_schedule_next_run",
        "pull_list_automation_schedule",
        ["next_run_at", "enabled", "id"],
    )

    op.create_table(
        "pull_list_automation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("owners_processed", sa.Integer(), nullable=False),
        sa.Column("releases_processed", sa.Integer(), nullable=False),
        sa.Column("decisions_created", sa.Integer(), nullable=False),
        sa.Column("actions_generated", sa.Integer(), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_list_automation_run_started", "pull_list_automation_run", ["started_at", "id"])
    op.create_index("ix_pull_list_automation_run_status", "pull_list_automation_run", ["status", "id"])


def downgrade() -> None:
    op.drop_index("ix_pull_list_automation_run_status", table_name="pull_list_automation_run")
    op.drop_index("ix_pull_list_automation_run_started", table_name="pull_list_automation_run")
    op.drop_table("pull_list_automation_run")
    op.drop_index("ix_pull_list_automation_schedule_next_run", table_name="pull_list_automation_schedule")
    op.drop_table("pull_list_automation_schedule")
