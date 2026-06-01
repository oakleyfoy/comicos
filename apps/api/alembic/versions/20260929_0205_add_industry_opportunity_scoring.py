from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260929_0205"
down_revision = "20260928_0204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_opportunity_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("scan_run_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("publisher_code", sa.String(length=32), nullable=False),
        sa.Column("publisher_name", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["industry_release_candidate.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["industry_release_scan_run.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "candidate_id", name="uq_industry_opportunity_owner_candidate"),
    )
    op.create_index(
        "ix_industry_opportunity_owner_score",
        "industry_opportunity_score",
        ["owner_user_id", "opportunity_score", "id"],
    )
    op.create_index(
        "ix_industry_opportunity_scan_run",
        "industry_opportunity_score",
        ["scan_run_id", "opportunity_score", "id"],
    )
    op.create_index(
        "ix_industry_opportunity_owner_risk",
        "industry_opportunity_score",
        ["owner_user_id", "risk_level", "id"],
    )
    op.create_index(op.f("ix_industry_opportunity_score_owner_user_id"), "industry_opportunity_score", ["owner_user_id"])
    op.create_index(op.f("ix_industry_opportunity_score_candidate_id"), "industry_opportunity_score", ["candidate_id"])
    op.create_index(op.f("ix_industry_opportunity_score_scan_run_id"), "industry_opportunity_score", ["scan_run_id"])
    op.create_index(op.f("ix_industry_opportunity_score_release_id"), "industry_opportunity_score", ["release_id"])
    op.create_index(op.f("ix_industry_opportunity_score_publisher_code"), "industry_opportunity_score", ["publisher_code"])
    op.create_index(op.f("ix_industry_opportunity_score_series_name"), "industry_opportunity_score", ["series_name"])
    op.create_index(op.f("ix_industry_opportunity_score_opportunity_score"), "industry_opportunity_score", ["opportunity_score"])
    op.create_index(op.f("ix_industry_opportunity_score_risk_level"), "industry_opportunity_score", ["risk_level"])


def downgrade() -> None:
    op.drop_index(op.f("ix_industry_opportunity_score_risk_level"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_opportunity_score"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_series_name"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_publisher_code"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_release_id"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_scan_run_id"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_candidate_id"), table_name="industry_opportunity_score")
    op.drop_index(op.f("ix_industry_opportunity_score_owner_user_id"), table_name="industry_opportunity_score")
    op.drop_index("ix_industry_opportunity_owner_risk", table_name="industry_opportunity_score")
    op.drop_index("ix_industry_opportunity_scan_run", table_name="industry_opportunity_score")
    op.drop_index("ix_industry_opportunity_owner_score", table_name="industry_opportunity_score")
    op.drop_table("industry_opportunity_score")
