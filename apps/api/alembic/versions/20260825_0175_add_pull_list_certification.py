from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0175"
down_revision = "20260824_0174"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pull_list_certification_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("foundation_score", sa.Float(), nullable=False),
        sa.Column("decision_engine_score", sa.Float(), nullable=False),
        sa.Column("dashboard_score", sa.Float(), nullable=False),
        sa.Column("automation_score", sa.Float(), nullable=False),
        sa.Column("determinism_score", sa.Float(), nullable=False),
        sa.Column("operations_score", sa.Float(), nullable=False),
        sa.Column("certification_result", sa.String(length=32), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_list_certification_run_started", "pull_list_certification_run", ["started_at", "id"])
    op.create_index(
        "ix_pull_list_certification_run_result",
        "pull_list_certification_run",
        ["certification_result", "id"],
    )
    op.create_index(op.f("ix_pull_list_certification_run_owner_user_id"), "pull_list_certification_run", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pull_list_certification_run_owner_user_id"), table_name="pull_list_certification_run")
    op.drop_index("ix_pull_list_certification_run_result", table_name="pull_list_certification_run")
    op.drop_index("ix_pull_list_certification_run_started", table_name="pull_list_certification_run")
    op.drop_table("pull_list_certification_run")
