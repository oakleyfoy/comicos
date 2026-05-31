from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260905_0181"
down_revision = "20260904_0180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_certification_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("run_completeness_score", sa.Float(), nullable=False),
        sa.Column("missing_issue_score", sa.Float(), nullable=False),
        sa.Column("duplicate_analysis_score", sa.Float(), nullable=False),
        sa.Column("grade_candidate_score", sa.Float(), nullable=False),
        sa.Column("sell_candidate_score", sa.Float(), nullable=False),
        sa.Column("determinism_score", sa.Float(), nullable=False),
        sa.Column("operations_score", sa.Float(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("certification_result", sa.String(length=32), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_certification_run_started", "portfolio_certification_run", ["started_at", "id"])
    op.create_index(
        "ix_portfolio_certification_run_result",
        "portfolio_certification_run",
        ["certification_result", "id"],
    )
    op.create_index(
        op.f("ix_portfolio_certification_run_owner_user_id"),
        "portfolio_certification_run",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_certification_run_owner_user_id"), table_name="portfolio_certification_run")
    op.drop_index("ix_portfolio_certification_run_result", table_name="portfolio_certification_run")
    op.drop_index("ix_portfolio_certification_run_started", table_name="portfolio_certification_run")
    op.drop_table("portfolio_certification_run")
