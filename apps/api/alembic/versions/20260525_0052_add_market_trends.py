"""P35-08 market trend snapshots.

Revision ID: 20260525_0052
Revises: 20260525_0051
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0052"
down_revision: str | None = "20260525_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_trend_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_issue_id", sa.Integer(), nullable=True),
        sa.Column("metadata_identity_key", sa.String(length=1024), nullable=True),
        sa.Column("snapshot_scope", sa.String(length=24), nullable=False),
        sa.Column("grading_company", sa.String(length=80), nullable=True),
        sa.Column("normalized_grade", sa.String(length=120), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("trend_window", sa.String(length=16), nullable=False),
        sa.Column("trend_direction", sa.String(length=16), nullable=False),
        sa.Column("trend_strength", sa.String(length=16), nullable=False),
        sa.Column("liquidity_direction", sa.String(length=16), nullable=False),
        sa.Column("comp_count", sa.Integer(), nullable=False),
        sa.Column("percent_change", sa.Numeric(10, 2), nullable=False),
        sa.Column("volatility_score", sa.Float(), nullable=False),
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
            "trend_window",
            name="uq_market_trend_snapshot_signature",
        ),
    )
    op.create_index(op.f("ix_market_trend_snapshot_canonical_issue_id"), "market_trend_snapshot", ["canonical_issue_id"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_metadata_identity_key"), "market_trend_snapshot", ["metadata_identity_key"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_snapshot_scope"), "market_trend_snapshot", ["snapshot_scope"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_grading_company"), "market_trend_snapshot", ["grading_company"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_normalized_grade"), "market_trend_snapshot", ["normalized_grade"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_currency_code"), "market_trend_snapshot", ["currency_code"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_trend_window"), "market_trend_snapshot", ["trend_window"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_trend_direction"), "market_trend_snapshot", ["trend_direction"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_trend_strength"), "market_trend_snapshot", ["trend_strength"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_liquidity_direction"), "market_trend_snapshot", ["liquidity_direction"], unique=False)
    op.create_index(op.f("ix_market_trend_snapshot_stale_data"), "market_trend_snapshot", ["stale_data"], unique=False)

    op.create_table(
        "market_trend_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_trend_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=True),
        sa.Column("market_fmv_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_fmv_snapshot_id"], ["market_fmv_snapshot.id"]),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.ForeignKeyConstraint(["market_trend_snapshot_id"], ["market_trend_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_trend_evidence_market_trend_snapshot_id"),
        "market_trend_evidence",
        ["market_trend_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_trend_evidence_market_sale_record_id"),
        "market_trend_evidence",
        ["market_sale_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_trend_evidence_market_fmv_snapshot_id"),
        "market_trend_evidence",
        ["market_fmv_snapshot_id"],
        unique=False,
    )
    op.create_index(op.f("ix_market_trend_evidence_evidence_type"), "market_trend_evidence", ["evidence_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_market_trend_evidence_evidence_type"), table_name="market_trend_evidence")
    op.drop_index(op.f("ix_market_trend_evidence_market_fmv_snapshot_id"), table_name="market_trend_evidence")
    op.drop_index(op.f("ix_market_trend_evidence_market_sale_record_id"), table_name="market_trend_evidence")
    op.drop_index(op.f("ix_market_trend_evidence_market_trend_snapshot_id"), table_name="market_trend_evidence")
    op.drop_table("market_trend_evidence")

    op.drop_index(op.f("ix_market_trend_snapshot_stale_data"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_liquidity_direction"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_trend_strength"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_trend_direction"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_trend_window"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_currency_code"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_normalized_grade"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_grading_company"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_snapshot_scope"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_metadata_identity_key"), table_name="market_trend_snapshot")
    op.drop_index(op.f("ix_market_trend_snapshot_canonical_issue_id"), table_name="market_trend_snapshot")
    op.drop_table("market_trend_snapshot")
