"""add external catalog importance and rich metadata columns

Revision ID: 20261010_0216
Revises: 20261009_0215
Create Date: 2026-10-10 02:16:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261010_0216"
down_revision = "20261009_0215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("external_catalog_issue", sa.Column("story_summary", sa.Text(), nullable=True))
    op.add_column("external_catalog_issue", sa.Column("imprint", sa.String(length=120), nullable=True))
    op.add_column("external_catalog_issue", sa.Column("universe", sa.String(length=120), nullable=True))
    op.add_column("external_catalog_issue", sa.Column("is_first_issue", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("external_catalog_issue", sa.Column("is_milestone_issue", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("external_catalog_issue", sa.Column("milestone_issue_number", sa.Integer(), nullable=True))
    op.add_column("external_catalog_issue", sa.Column("importance_signals_json", sa.JSON(), nullable=True))
    op.add_column("external_catalog_creator", sa.Column("role_display", sa.String(length=120), nullable=True))
    op.add_column("external_catalog_variant", sa.Column("variant_detail_url", sa.Text(), nullable=True))
    op.create_index("ix_external_catalog_issue_first_issue", "external_catalog_issue", ["is_first_issue"])
    op.create_index("ix_external_catalog_issue_milestone", "external_catalog_issue", ["is_milestone_issue"])


def downgrade() -> None:
    op.drop_index("ix_external_catalog_issue_milestone", table_name="external_catalog_issue")
    op.drop_index("ix_external_catalog_issue_first_issue", table_name="external_catalog_issue")
    op.drop_column("external_catalog_variant", "variant_detail_url")
    op.drop_column("external_catalog_creator", "role_display")
    op.drop_column("external_catalog_issue", "importance_signals_json")
    op.drop_column("external_catalog_issue", "milestone_issue_number")
    op.drop_column("external_catalog_issue", "is_milestone_issue")
    op.drop_column("external_catalog_issue", "is_first_issue")
    op.drop_column("external_catalog_issue", "universe")
    op.drop_column("external_catalog_issue", "imprint")
    op.drop_column("external_catalog_issue", "story_summary")
