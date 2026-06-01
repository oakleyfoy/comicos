from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260930_0206"
down_revision = "20260929_0205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_scanner_automation_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("scan_run_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("catalog_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("releases_scanned", sa.Integer(), nullable=False),
        sa.Column("candidates_created", sa.Integer(), nullable=False),
        sa.Column("signals_upserted", sa.Integer(), nullable=False),
        sa.Column("scores_updated", sa.Integer(), nullable=False),
        sa.Column("scan_skipped", sa.Boolean(), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["industry_release_scan_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_industry_scanner_auto_run_owner_started",
        "industry_scanner_automation_run",
        ["owner_user_id", "started_at", "id"],
    )
    op.create_index(
        "ix_industry_scanner_auto_run_owner_status",
        "industry_scanner_automation_run",
        ["owner_user_id", "status", "id"],
    )
    op.create_index(
        op.f("ix_industry_scanner_automation_run_owner_user_id"),
        "industry_scanner_automation_run",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_industry_scanner_automation_run_scan_run_id"),
        "industry_scanner_automation_run",
        ["scan_run_id"],
    )
    op.create_index(
        op.f("ix_industry_scanner_automation_run_trigger_type"),
        "industry_scanner_automation_run",
        ["trigger_type"],
    )
    op.create_index(
        op.f("ix_industry_scanner_automation_run_status"),
        "industry_scanner_automation_run",
        ["status"],
    )
    op.create_index(
        op.f("ix_industry_scanner_automation_run_catalog_fingerprint"),
        "industry_scanner_automation_run",
        ["catalog_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_industry_scanner_automation_run_catalog_fingerprint"),
        table_name="industry_scanner_automation_run",
    )
    op.drop_index(op.f("ix_industry_scanner_automation_run_status"), table_name="industry_scanner_automation_run")
    op.drop_index(op.f("ix_industry_scanner_automation_run_trigger_type"), table_name="industry_scanner_automation_run")
    op.drop_index(op.f("ix_industry_scanner_automation_run_scan_run_id"), table_name="industry_scanner_automation_run")
    op.drop_index(op.f("ix_industry_scanner_automation_run_owner_user_id"), table_name="industry_scanner_automation_run")
    op.drop_index("ix_industry_scanner_auto_run_owner_status", table_name="industry_scanner_automation_run")
    op.drop_index("ix_industry_scanner_auto_run_owner_started", table_name="industry_scanner_automation_run")
    op.drop_table("industry_scanner_automation_run")
