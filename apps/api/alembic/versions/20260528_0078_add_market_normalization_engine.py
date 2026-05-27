"""P39-02 market normalization engine."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260528_0078"
down_revision: str | None = "20260527_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_acquisition_normalization_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("run_status", sa.String(length=24), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("successful_records", sa.Integer(), nullable=False),
        sa.Column("partial_records", sa.Integer(), nullable=False),
        sa.Column("failed_records", sa.Integer(), nullable=False),
        sa.Column("run_checksum", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["market_acquisition_ingestion_batch.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_batch_id",
            "run_checksum",
            name="uq_market_acquisition_norm_run_batch_checksum",
        ),
    )
    op.create_index(
        "ix_market_acquisition_norm_run_batch_status",
        "market_acquisition_normalization_run",
        ["ingestion_batch_id", "run_status"],
    )
    op.create_index(
        "ix_market_acquisition_norm_run_owner_created",
        "market_acquisition_normalization_run",
        ["owner_user_id", "created_at"],
    )

    op.create_table(
        "market_acquisition_normalized_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_candidate_id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("canonical_title", sa.String(length=510), nullable=False),
        sa.Column("canonical_publisher", sa.String(length=255), nullable=True),
        sa.Column("canonical_issue_number", sa.String(length=120), nullable=True),
        sa.Column("canonical_variant", sa.String(length=255), nullable=True),
        sa.Column("normalized_condition_band", sa.String(length=16), nullable=False),
        sa.Column("normalized_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("normalized_currency", sa.String(length=8), nullable=True),
        sa.Column("normalized_fmv_estimate", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("normalized_liquidity_hint", sa.String(length=64), nullable=True),
        sa.Column("normalized_grade_potential", sa.String(length=64), nullable=True),
        sa.Column("canonical_key", sa.String(length=64), nullable=False),
        sa.Column("normalization_flags_json", sa.JSON(), nullable=True),
        sa.Column("normalization_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_candidate_id"], ["market_acquisition_candidate.id"]),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["market_acquisition_normalization_run.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingestion_candidate_id", name="uq_market_acquisition_norm_candidate_unique"),
    )
    op.create_index(
        "ix_market_acquisition_norm_candidate_key",
        "market_acquisition_normalized_candidate",
        ["canonical_key"],
    )
    op.create_index(
        "ix_market_acquisition_norm_candidate_status",
        "market_acquisition_normalized_candidate",
        ["normalization_status"],
    )

    op.create_table(
        "market_acquisition_normalization_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_candidate_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("issue_detail_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["market_acquisition_normalization_run.id"]),
        sa.ForeignKeyConstraint(["ingestion_candidate_id"], ["market_acquisition_candidate.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_norm_issue_run_type",
        "market_acquisition_normalization_issue",
        ["normalization_run_id", "issue_type"],
    )

    op.create_table(
        "market_acquisition_normalization_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("normalization_run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["normalization_run_id"], ["market_acquisition_normalization_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_norm_event_run_created",
        "market_acquisition_normalization_event",
        ["normalization_run_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_acquisition_norm_event_run_created", table_name="market_acquisition_normalization_event")
    op.drop_table("market_acquisition_normalization_event")
    op.drop_index("ix_market_acquisition_norm_issue_run_type", table_name="market_acquisition_normalization_issue")
    op.drop_table("market_acquisition_normalization_issue")
    op.drop_index("ix_market_acquisition_norm_candidate_status", table_name="market_acquisition_normalized_candidate")
    op.drop_index("ix_market_acquisition_norm_candidate_key", table_name="market_acquisition_normalized_candidate")
    op.drop_table("market_acquisition_normalized_candidate")
    op.drop_index("ix_market_acquisition_norm_run_owner_created", table_name="market_acquisition_normalization_run")
    op.drop_index("ix_market_acquisition_norm_run_batch_status", table_name="market_acquisition_normalization_run")
    op.drop_table("market_acquisition_normalization_run")
