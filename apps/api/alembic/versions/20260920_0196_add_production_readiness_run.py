from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260920_0196"
down_revision = "20260919_0195"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_readiness_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("import_health_score", sa.Float(), nullable=False),
        sa.Column("inventory_health_score", sa.Float(), nullable=False),
        sa.Column("recommendation_health_score", sa.Float(), nullable=False),
        sa.Column("dashboard_health_score", sa.Float(), nullable=False),
        sa.Column("automation_health_score", sa.Float(), nullable=False),
        sa.Column("workflow_health_score", sa.Float(), nullable=False),
        sa.Column("operations_health_score", sa.Float(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("go_live_result", sa.String(length=32), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_readiness_run_started", "production_readiness_run", ["started_at", "id"])
    op.create_index("ix_production_readiness_run_go_live", "production_readiness_run", ["go_live_result", "id"])
    op.create_index("ix_production_readiness_run_health", "production_readiness_run", ["health_status", "id"])
    op.create_index(
        op.f("ix_production_readiness_run_owner_user_id"),
        "production_readiness_run",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_production_readiness_run_owner_user_id"), table_name="production_readiness_run")
    op.drop_index("ix_production_readiness_run_health", table_name="production_readiness_run")
    op.drop_index("ix_production_readiness_run_go_live", table_name="production_readiness_run")
    op.drop_index("ix_production_readiness_run_started", table_name="production_readiness_run")
    op.drop_table("production_readiness_run")
