"""add p92 import line cover resolution

Revision ID: 20260608_0273
Revises: 20260608_0272
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0273"
down_revision = "20260608_0272"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p92_import_line_cover_resolution",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("draft_import_id", sa.Integer(), nullable=False),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_source", sa.String(length=32), nullable=True),
        sa.Column("cover_confidence", sa.Float(), nullable=True),
        sa.Column("variant_confidence", sa.Float(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_sku", sa.String(length=128), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(length=16), nullable=True),
        sa.Column("resolution_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["draft_import_id"], ["draft_import.id"]),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_p92_import_line_cover_draft_line",
        "p92_import_line_cover_resolution",
        ["draft_import_id", "line_index"],
        unique=True,
    )
    op.create_index(
        "ix_p92_import_line_cover_inventory",
        "p92_import_line_cover_resolution",
        ["inventory_copy_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_p92_import_line_cover_inventory", table_name="p92_import_line_cover_resolution")
    op.drop_index("ix_p92_import_line_cover_draft_line", table_name="p92_import_line_cover_resolution")
    op.drop_table("p92_import_line_cover_resolution")
