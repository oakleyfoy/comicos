from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260928_0204"
down_revision = "20260927_0203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_release_signal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("scan_run_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["industry_release_candidate.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["industry_release_scan_run.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "signal_type", name="uq_industry_release_signal_candidate_type"),
    )
    op.create_index(
        "ix_industry_release_signal_owner_created",
        "industry_release_signal",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_industry_release_signal_owner_type",
        "industry_release_signal",
        ["owner_user_id", "signal_type", "id"],
    )
    op.create_index(
        "ix_industry_release_signal_scan_run",
        "industry_release_signal",
        ["scan_run_id", "signal_type", "id"],
    )
    op.create_index(op.f("ix_industry_release_signal_owner_user_id"), "industry_release_signal", ["owner_user_id"])
    op.create_index(op.f("ix_industry_release_signal_candidate_id"), "industry_release_signal", ["candidate_id"])
    op.create_index(op.f("ix_industry_release_signal_scan_run_id"), "industry_release_signal", ["scan_run_id"])
    op.create_index(op.f("ix_industry_release_signal_release_id"), "industry_release_signal", ["release_id"])
    op.create_index(op.f("ix_industry_release_signal_signal_type"), "industry_release_signal", ["signal_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_industry_release_signal_signal_type"), table_name="industry_release_signal")
    op.drop_index(op.f("ix_industry_release_signal_release_id"), table_name="industry_release_signal")
    op.drop_index(op.f("ix_industry_release_signal_scan_run_id"), table_name="industry_release_signal")
    op.drop_index(op.f("ix_industry_release_signal_candidate_id"), table_name="industry_release_signal")
    op.drop_index(op.f("ix_industry_release_signal_owner_user_id"), table_name="industry_release_signal")
    op.drop_index("ix_industry_release_signal_scan_run", table_name="industry_release_signal")
    op.drop_index("ix_industry_release_signal_owner_type", table_name="industry_release_signal")
    op.drop_index("ix_industry_release_signal_owner_created", table_name="industry_release_signal")
    op.drop_table("industry_release_signal")
