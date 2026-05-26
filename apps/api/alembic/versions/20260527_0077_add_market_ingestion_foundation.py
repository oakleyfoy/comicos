"""P39-01 market ingestion foundation."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0077"
down_revision: str | None = "20260527_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_acquisition_ingestion_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("batch_source_type", sa.String(length=40), nullable=False),
        sa.Column("batch_file_name", sa.String(length=512), nullable=True),
        sa.Column("batch_checksum", sa.String(length=64), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("successful_records", sa.Integer(), nullable=False),
        sa.Column("failed_records", sa.Integer(), nullable=False),
        sa.Column("ingestion_status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "batch_checksum",
            name="uq_market_acquisition_ingestion_batch_owner_checksum",
        ),
    )
    op.create_index(
        "ix_market_acquisition_ingestion_batch_owner_created",
        "market_acquisition_ingestion_batch",
        ["owner_user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_market_acquisition_ingestion_batch_status",
        "market_acquisition_ingestion_batch",
        ["ingestion_status", "created_at", "id"],
    )
    op.create_index(
        "ix_market_acquisition_ingestion_batch_checksum",
        "market_acquisition_ingestion_batch",
        ["batch_checksum"],
    )

    op.create_table(
        "market_acquisition_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("external_source_type", sa.String(length=40), nullable=False),
        sa.Column("external_listing_id", sa.String(length=255), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=510), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("issue_number", sa.String(length=120), nullable=True),
        sa.Column("variant", sa.String(length=255), nullable=True),
        sa.Column("condition_raw", sa.String(length=255), nullable=True),
        sa.Column("asking_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("external_fmv_estimate", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("normalized_flag", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["market_acquisition_ingestion_batch.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_candidate_batch",
        "market_acquisition_candidate",
        ["ingestion_batch_id", "id"],
    )
    op.create_index(
        "ix_market_acquisition_candidate_source",
        "market_acquisition_candidate",
        ["external_source_type", "source_name", "external_listing_id"],
    )

    op.create_table(
        "market_acquisition_raw_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("raw_record_json", sa.JSON(), nullable=False),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["market_acquisition_ingestion_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_raw_source_batch",
        "market_acquisition_raw_source",
        ["ingestion_batch_id", "created_at", "id"],
    )
    op.create_index(
        "ix_market_acquisition_raw_source_hash",
        "market_acquisition_raw_source",
        ["raw_hash"],
    )

    op.create_table(
        "market_acquisition_ingestion_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["market_acquisition_ingestion_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_acquisition_ingestion_event_batch",
        "market_acquisition_ingestion_event",
        ["ingestion_batch_id", "created_at", "id"],
    )
    op.create_index(
        "ix_market_acquisition_ingestion_event_type",
        "market_acquisition_ingestion_event",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_acquisition_ingestion_event_type", table_name="market_acquisition_ingestion_event")
    op.drop_index("ix_market_acquisition_ingestion_event_batch", table_name="market_acquisition_ingestion_event")
    op.drop_table("market_acquisition_ingestion_event")
    op.drop_index("ix_market_acquisition_raw_source_hash", table_name="market_acquisition_raw_source")
    op.drop_index("ix_market_acquisition_raw_source_batch", table_name="market_acquisition_raw_source")
    op.drop_table("market_acquisition_raw_source")
    op.drop_index("ix_market_acquisition_candidate_source", table_name="market_acquisition_candidate")
    op.drop_index("ix_market_acquisition_candidate_batch", table_name="market_acquisition_candidate")
    op.drop_table("market_acquisition_candidate")
    op.drop_index(
        "ix_market_acquisition_ingestion_batch_checksum",
        table_name="market_acquisition_ingestion_batch",
    )
    op.drop_index(
        "ix_market_acquisition_ingestion_batch_status",
        table_name="market_acquisition_ingestion_batch",
    )
    op.drop_index(
        "ix_market_acquisition_ingestion_batch_owner_created",
        table_name="market_acquisition_ingestion_batch",
    )
    op.drop_table("market_acquisition_ingestion_batch")
