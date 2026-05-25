"""P35-06 market FMV snapshots.

Revision ID: 20260525_0051
Revises: 20260525_0050
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0051"
down_revision: str | None = "20260525_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_fmv_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_issue_id", sa.Integer(), nullable=True),
        sa.Column("metadata_identity_key", sa.String(length=1024), nullable=True),
        sa.Column("snapshot_scope", sa.String(length=24), nullable=False),
        sa.Column("grading_company", sa.String(length=80), nullable=True),
        sa.Column("normalized_grade", sa.String(length=120), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("comp_count", sa.Integer(), nullable=False),
        sa.Column("valuation_method", sa.String(length=32), nullable=False),
        sa.Column("estimated_fmv", sa.Numeric(12, 2), nullable=False),
        sa.Column("confidence_bucket", sa.String(length=16), nullable=False),
        sa.Column("liquidity_bucket", sa.String(length=16), nullable=False),
        sa.Column("volatility_bucket", sa.String(length=16), nullable=False),
        sa.Column("stale_data", sa.Boolean(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_issue_id"], ["comic_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_issue_id",
            "metadata_identity_key",
            "snapshot_scope",
            "grading_company",
            "normalized_grade",
            "currency_code",
            "snapshot_date",
            "valuation_method",
            name="uq_market_fmv_snapshot_signature",
        ),
    )
    op.create_index(op.f("ix_market_fmv_snapshot_canonical_issue_id"), "market_fmv_snapshot", ["canonical_issue_id"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_metadata_identity_key"), "market_fmv_snapshot", ["metadata_identity_key"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_snapshot_scope"), "market_fmv_snapshot", ["snapshot_scope"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_grading_company"), "market_fmv_snapshot", ["grading_company"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_normalized_grade"), "market_fmv_snapshot", ["normalized_grade"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_currency_code"), "market_fmv_snapshot", ["currency_code"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_snapshot_date"), "market_fmv_snapshot", ["snapshot_date"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_valuation_method"), "market_fmv_snapshot", ["valuation_method"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_confidence_bucket"), "market_fmv_snapshot", ["confidence_bucket"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_liquidity_bucket"), "market_fmv_snapshot", ["liquidity_bucket"], unique=False)
    op.create_index(op.f("ix_market_fmv_snapshot_stale_data"), "market_fmv_snapshot", ["stale_data"], unique=False)

    op.create_table(
        "market_fmv_comp_reference",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_fmv_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=False),
        sa.Column("weighting_factor", sa.Float(), nullable=False),
        sa.Column("included_reason", sa.String(length=120), nullable=False),
        sa.Column("excluded_reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_fmv_snapshot_id"], ["market_fmv_snapshot.id"]),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_fmv_snapshot_id",
            "market_sale_record_id",
            name="uq_market_fmv_comp_reference_snapshot_sale",
        ),
    )
    op.create_index(
        op.f("ix_market_fmv_comp_reference_market_fmv_snapshot_id"),
        "market_fmv_comp_reference",
        ["market_fmv_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_fmv_comp_reference_market_sale_record_id"),
        "market_fmv_comp_reference",
        ["market_sale_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_fmv_comp_reference_market_sale_record_id"), table_name="market_fmv_comp_reference")
    op.drop_index(op.f("ix_market_fmv_comp_reference_market_fmv_snapshot_id"), table_name="market_fmv_comp_reference")
    op.drop_table("market_fmv_comp_reference")

    op.drop_index(op.f("ix_market_fmv_snapshot_stale_data"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_liquidity_bucket"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_confidence_bucket"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_valuation_method"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_snapshot_date"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_currency_code"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_normalized_grade"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_grading_company"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_snapshot_scope"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_metadata_identity_key"), table_name="market_fmv_snapshot")
    op.drop_index(op.f("ix_market_fmv_snapshot_canonical_issue_id"), table_name="market_fmv_snapshot")
    op.drop_table("market_fmv_snapshot")
