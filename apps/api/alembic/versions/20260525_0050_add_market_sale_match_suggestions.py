"""Add market sale match suggestions.

Revision ID: 20260525_0050
Revises: 20260525_0049
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0050"
down_revision: str | None = "20260525_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_sale_match_suggestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=False),
        sa.Column("canonical_issue_id", sa.Integer(), nullable=True),
        sa.Column("canonical_series_id", sa.Integer(), nullable=True),
        sa.Column("canonical_publisher_id", sa.Integer(), nullable=True),
        sa.Column("suggested_identity_key", sa.String(length=1024), nullable=True),
        sa.Column("suggestion_type", sa.String(length=50), nullable=False),
        sa.Column("confidence_bucket", sa.String(length=20), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("confidence_version", sa.String(length=100), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("review_state", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["canonical_publisher_id"], ["publisher.id"]),
        sa.ForeignKeyConstraint(["canonical_series_id"], ["canonical_series.id"]),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market_sale_record_id",
            "canonical_issue_id",
            "canonical_series_id",
            "suggested_identity_key",
            "suggestion_type",
            "confidence_version",
            name="uq_market_sale_match_suggestion_signature",
        ),
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_market_sale_record_id"),
        "market_sale_match_suggestion",
        ["market_sale_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_canonical_issue_id"),
        "market_sale_match_suggestion",
        ["canonical_issue_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_canonical_series_id"),
        "market_sale_match_suggestion",
        ["canonical_series_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_canonical_publisher_id"),
        "market_sale_match_suggestion",
        ["canonical_publisher_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_suggestion_type"),
        "market_sale_match_suggestion",
        ["suggestion_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_confidence_bucket"),
        "market_sale_match_suggestion",
        ["confidence_bucket"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_confidence_version"),
        "market_sale_match_suggestion",
        ["confidence_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_review_state"),
        "market_sale_match_suggestion",
        ["review_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_sale_match_suggestion_reviewed_by_user_id"),
        "market_sale_match_suggestion",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_sale_match_suggestion_reviewed_by_user_id"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_review_state"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_confidence_version"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_confidence_bucket"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_suggestion_type"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_canonical_publisher_id"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_canonical_series_id"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_canonical_issue_id"), table_name="market_sale_match_suggestion")
    op.drop_index(op.f("ix_market_sale_match_suggestion_market_sale_record_id"), table_name="market_sale_match_suggestion")
    op.drop_table("market_sale_match_suggestion")
