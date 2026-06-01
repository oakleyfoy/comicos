from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260927_0203"
down_revision = "20260926_0202"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_release_scan_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("releases_scanned", sa.Integer(), nullable=False),
        sa.Column("candidates_created", sa.Integer(), nullable=False),
        sa.Column("candidates_total", sa.Integer(), nullable=False),
        sa.Column("publishers_included", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_industry_release_scan_run_owner_started",
        "industry_release_scan_run",
        ["owner_user_id", "started_at", "id"],
    )
    op.create_index(
        "ix_industry_release_scan_run_owner_status",
        "industry_release_scan_run",
        ["owner_user_id", "status", "id"],
    )
    op.create_index(op.f("ix_industry_release_scan_run_owner_user_id"), "industry_release_scan_run", ["owner_user_id"])
    op.create_index(op.f("ix_industry_release_scan_run_status"), "industry_release_scan_run", ["status"])

    op.create_table(
        "industry_release_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_run_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("publisher_code", sa.String(length=32), nullable=False),
        sa.Column("publisher_name", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("foc_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("variant_count", sa.Integer(), nullable=False),
        sa.Column("monitoring_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["industry_release_scan_run.id"]),
        sa.ForeignKeyConstraint(["release_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_run_id", "release_id", name="uq_industry_release_candidate_run_release"),
    )
    op.create_index(
        "ix_industry_release_candidate_owner_created",
        "industry_release_candidate",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_industry_release_candidate_run_series",
        "industry_release_candidate",
        ["scan_run_id", "series_name", "id"],
    )
    op.create_index(op.f("ix_industry_release_candidate_owner_user_id"), "industry_release_candidate", ["owner_user_id"])
    op.create_index(op.f("ix_industry_release_candidate_scan_run_id"), "industry_release_candidate", ["scan_run_id"])
    op.create_index(op.f("ix_industry_release_candidate_release_id"), "industry_release_candidate", ["release_id"])
    op.create_index(op.f("ix_industry_release_candidate_publisher_code"), "industry_release_candidate", ["publisher_code"])
    op.create_index(op.f("ix_industry_release_candidate_series_name"), "industry_release_candidate", ["series_name"])
    op.create_index(op.f("ix_industry_release_candidate_foc_date"), "industry_release_candidate", ["foc_date"])
    op.create_index(op.f("ix_industry_release_candidate_release_date"), "industry_release_candidate", ["release_date"])
    op.create_index(
        op.f("ix_industry_release_candidate_monitoring_status"),
        "industry_release_candidate",
        ["monitoring_status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_industry_release_candidate_monitoring_status"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_release_date"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_foc_date"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_series_name"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_publisher_code"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_release_id"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_scan_run_id"), table_name="industry_release_candidate")
    op.drop_index(op.f("ix_industry_release_candidate_owner_user_id"), table_name="industry_release_candidate")
    op.drop_index("ix_industry_release_candidate_run_series", table_name="industry_release_candidate")
    op.drop_index("ix_industry_release_candidate_owner_created", table_name="industry_release_candidate")
    op.drop_table("industry_release_candidate")

    op.drop_index(op.f("ix_industry_release_scan_run_status"), table_name="industry_release_scan_run")
    op.drop_index(op.f("ix_industry_release_scan_run_owner_user_id"), table_name="industry_release_scan_run")
    op.drop_index("ix_industry_release_scan_run_owner_status", table_name="industry_release_scan_run")
    op.drop_index("ix_industry_release_scan_run_owner_started", table_name="industry_release_scan_run")
    op.drop_table("industry_release_scan_run")
