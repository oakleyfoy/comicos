from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260919_0195"
down_revision = "20260918_0194"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "final_platform_certification_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("release_intelligence_score", sa.Float(), nullable=False),
        sa.Column("recommendation_intelligence_score", sa.Float(), nullable=False),
        sa.Column("pull_list_score", sa.Float(), nullable=False),
        sa.Column("purchase_score", sa.Float(), nullable=False),
        sa.Column("portfolio_score", sa.Float(), nullable=False),
        sa.Column("acquisition_score", sa.Float(), nullable=False),
        sa.Column("exit_score", sa.Float(), nullable=False),
        sa.Column("unified_intelligence_score", sa.Float(), nullable=False),
        sa.Column("daily_action_score", sa.Float(), nullable=False),
        sa.Column("cross_system_score", sa.Float(), nullable=False),
        sa.Column("executive_dashboard_score", sa.Float(), nullable=False),
        sa.Column("determinism_score", sa.Float(), nullable=False),
        sa.Column("operations_score", sa.Float(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("certification_result", sa.String(length=32), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_final_platform_cert_run_started", "final_platform_certification_run", ["started_at", "id"])
    op.create_index(
        "ix_final_platform_cert_run_result",
        "final_platform_certification_run",
        ["certification_result", "id"],
    )
    op.create_index(
        "ix_final_platform_cert_run_health",
        "final_platform_certification_run",
        ["health_status", "id"],
    )
    op.create_index(
        op.f("ix_final_platform_certification_run_owner_user_id"),
        "final_platform_certification_run",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_final_platform_certification_run_owner_user_id"), table_name="final_platform_certification_run")
    op.drop_index("ix_final_platform_cert_run_health", table_name="final_platform_certification_run")
    op.drop_index("ix_final_platform_cert_run_result", table_name="final_platform_certification_run")
    op.drop_index("ix_final_platform_cert_run_started", table_name="final_platform_certification_run")
    op.drop_table("final_platform_certification_run")
