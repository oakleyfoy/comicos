"""Add canonical issue link suggestions.

Revision ID: 20260523_0037
Revises: 20260523_0036
Create Date: 2026-06-08 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0037"
down_revision: str | None = "20260523_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_issue_link_suggestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cover_image_id", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("canonical_issue_id", sa.Integer(), nullable=True),
        sa.Column("canonical_series_id", sa.Integer(), nullable=True),
        sa.Column("canonical_publisher_id", sa.Integer(), nullable=True),
        sa.Column("suggested_metadata_identity_key", sa.String(length=1024), nullable=True),
        sa.Column("suggestion_type", sa.String(length=50), nullable=False),
        sa.Column("confidence_bucket", sa.String(length=20), nullable=False),
        sa.Column("deterministic_score", sa.Float(), nullable=False),
        sa.Column("confidence_version", sa.String(length=100), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("suppression_reason", sa.Text(), nullable=True),
        sa.Column("review_state", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["canonical_publisher_id"], ["publisher.id"]),
        sa.ForeignKeyConstraint(["canonical_series_id"], ["canonical_series.id"]),
        sa.ForeignKeyConstraint(["cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_cover_image_id"),
        "canonical_issue_link_suggestion",
        ["cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_inventory_copy_id"),
        "canonical_issue_link_suggestion",
        ["inventory_copy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_issue_id"),
        "canonical_issue_link_suggestion",
        ["canonical_issue_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_series_id"),
        "canonical_issue_link_suggestion",
        ["canonical_series_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_publisher_id"),
        "canonical_issue_link_suggestion",
        ["canonical_publisher_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_suggestion_type"),
        "canonical_issue_link_suggestion",
        ["suggestion_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_confidence_bucket"),
        "canonical_issue_link_suggestion",
        ["confidence_bucket"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_confidence_version"),
        "canonical_issue_link_suggestion",
        ["confidence_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_review_state"),
        "canonical_issue_link_suggestion",
        ["review_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_issue_link_suggestion_reviewed_by_user_id"),
        "canonical_issue_link_suggestion",
        ["reviewed_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_reviewed_by_user_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_review_state"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_confidence_version"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_confidence_bucket"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_suggestion_type"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_publisher_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_series_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_canonical_issue_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_inventory_copy_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_index(
        op.f("ix_canonical_issue_link_suggestion_cover_image_id"),
        table_name="canonical_issue_link_suggestion",
    )
    op.drop_table("canonical_issue_link_suggestion")
