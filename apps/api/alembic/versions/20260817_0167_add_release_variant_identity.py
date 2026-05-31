"""add release variant identity columns

Revision ID: 20260817_0167
Revises: 20260816_0166
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0167"
down_revision = "20260816_0166"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("release_variant", sa.Column("variant_uuid", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("release_variant", sa.Column("ratio_type", sa.String(length=24), nullable=True))
    op.add_column("release_variant", sa.Column("is_incentive_variant", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("release_variant", sa.Column("source_item_code", sa.String(length=64), nullable=False, server_default=""))
    op.execute("UPDATE release_variant SET variant_uuid = 'legacy-' || id::text WHERE variant_uuid = ''")
    op.create_unique_constraint("uq_release_variant_uuid", "release_variant", ["issue_id", "variant_uuid"])
    op.alter_column("release_variant", "variant_uuid", server_default=None)
    op.alter_column("release_variant", "is_incentive_variant", server_default=None)
    op.alter_column("release_variant", "source_item_code", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_release_variant_uuid", "release_variant", type_="unique")
    op.drop_column("release_variant", "source_item_code")
    op.drop_column("release_variant", "is_incentive_variant")
    op.drop_column("release_variant", "ratio_type")
    op.drop_column("release_variant", "variant_uuid")
