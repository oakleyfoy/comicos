"""Add cover relationship conflicts table.

Revision ID: 20260524_0039
Revises: 20260523_0038
Create Date: 2026-05-24 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260524_0039"
down_revision: str | None = "20260523_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_relationship_conflict",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conflict_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("source_cover_image_id", sa.Integer(), nullable=True),
        sa.Column("related_cover_image_id", sa.Integer(), nullable=True),
        sa.Column("link_decision_id", sa.Integer(), nullable=True),
        sa.Column("match_candidate_id", sa.Integer(), nullable=True),
        sa.Column("canonical_issue_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("conflict_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["canonical_issue_suggestion_id"], ["canonical_issue_link_suggestion.id"]),
        sa.ForeignKeyConstraint(["link_decision_id"], ["cover_image_link_decision.id"]),
        sa.ForeignKeyConstraint(["match_candidate_id"], ["cover_image_match_candidate.id"]),
        sa.ForeignKeyConstraint(["related_cover_image_id"], ["cover_image.id"]),
        sa.ForeignKeyConstraint(["source_cover_image_id"], ["cover_image.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conflict_key"),
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_conflict_type"),
        "cover_relationship_conflict",
        ["conflict_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_severity"),
        "cover_relationship_conflict",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_source_cover_image_id"),
        "cover_relationship_conflict",
        ["source_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_related_cover_image_id"),
        "cover_relationship_conflict",
        ["related_cover_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_link_decision_id"),
        "cover_relationship_conflict",
        ["link_decision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_match_candidate_id"),
        "cover_relationship_conflict",
        ["match_candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_canonical_issue_suggestion_id"),
        "cover_relationship_conflict",
        ["canonical_issue_suggestion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cover_relationship_conflict_status"),
        "cover_relationship_conflict",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cover_relationship_conflict_status"), table_name="cover_relationship_conflict")
    op.drop_index(
        op.f("ix_cover_relationship_conflict_canonical_issue_suggestion_id"),
        table_name="cover_relationship_conflict",
    )
    op.drop_index(op.f("ix_cover_relationship_conflict_match_candidate_id"), table_name="cover_relationship_conflict")
    op.drop_index(op.f("ix_cover_relationship_conflict_link_decision_id"), table_name="cover_relationship_conflict")
    op.drop_index(
        op.f("ix_cover_relationship_conflict_related_cover_image_id"),
        table_name="cover_relationship_conflict",
    )
    op.drop_index(
        op.f("ix_cover_relationship_conflict_source_cover_image_id"),
        table_name="cover_relationship_conflict",
    )
    op.drop_index(op.f("ix_cover_relationship_conflict_severity"), table_name="cover_relationship_conflict")
    op.drop_index(op.f("ix_cover_relationship_conflict_conflict_type"), table_name="cover_relationship_conflict")
    op.drop_table("cover_relationship_conflict")
