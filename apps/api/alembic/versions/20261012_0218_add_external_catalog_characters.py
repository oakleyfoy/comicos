"""add external catalog character rows

Revision ID: 20261012_0218
Revises: 20261011_0217
Create Date: 2026-10-12 02:18:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261012_0218"
down_revision = "20261011_0217"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_catalog_character",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_issue_id", sa.Integer(), nullable=False),
        sa.Column("character_name", sa.String(length=200), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("universe", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["external_issue_id"], ["external_catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_issue_id",
            "character_name",
            "role",
            name="uq_external_catalog_character_identity",
        ),
    )
    op.create_index(
        "ix_external_catalog_character_issue",
        "external_catalog_character",
        ["external_issue_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_catalog_character_issue", table_name="external_catalog_character")
    op.drop_table("external_catalog_character")
