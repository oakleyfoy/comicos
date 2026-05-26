"""P36-08 operational reporting registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0060"
down_revision: str | None = "20260525_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_report_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("report_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("generation_params_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("csv_row_count", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_operational_report_run_owner_replay"),
    )
    op.create_index(
        "ix_operational_report_run_owner_created",
        "operational_report_run",
        ["owner_user_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_operational_report_run_owner_status",
        "operational_report_run",
        ["owner_user_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_operational_report_run_type",
        "operational_report_run",
        ["owner_user_id", "report_type", "id"],
        unique=False,
    )

    op.create_table(
        "operational_report_file",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operational_report_run_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operational_report_run_id"], ["operational_report_run.id"]),
    )
    op.create_index(
        "ix_operational_report_file_run",
        "operational_report_file",
        ["operational_report_run_id", "id"],
        unique=False,
    )

    op.create_table(
        "operational_report_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operational_report_run_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("lineage_domain", sa.String(length=128), nullable=False),
        sa.Column("lineage_key", sa.String(length=256), nullable=False),
        sa.Column("lineage_json", sa.JSON(), nullable=False),
        sa.Column("row_checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operational_report_run_id"], ["operational_report_run.id"]),
    )
    op.create_index(
        "ix_operational_report_item_run_row",
        "operational_report_item",
        ["operational_report_run_id", "row_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_operational_report_item_run_row", table_name="operational_report_item")
    op.drop_table("operational_report_item")
    op.drop_index("ix_operational_report_file_run", table_name="operational_report_file")
    op.drop_table("operational_report_file")
    op.drop_index("ix_operational_report_run_type", table_name="operational_report_run")
    op.drop_index("ix_operational_report_run_owner_status", table_name="operational_report_run")
    op.drop_index("ix_operational_report_run_owner_created", table_name="operational_report_run")
    op.drop_table("operational_report_run")
