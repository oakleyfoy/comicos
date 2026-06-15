"""P97-23A ComicVine volume universe discovery table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260615_0101"
down_revision = "20260614_0402"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comicvine_volume_universe",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("volume_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("count_of_issues", sa.Integer(), nullable=True),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("volume_id", name="uq_comicvine_volume_universe_volume_id"),
    )
    op.create_index(
        "ix_comicvine_volume_universe_volume_id",
        "comicvine_volume_universe",
        ["volume_id"],
    )
    op.create_index(
        "ix_comicvine_volume_universe_publisher",
        "comicvine_volume_universe",
        ["publisher"],
    )
    op.create_index(
        "ix_comicvine_volume_universe_count_of_issues",
        "comicvine_volume_universe",
        ["count_of_issues"],
    )


def downgrade() -> None:
    op.drop_index("ix_comicvine_volume_universe_count_of_issues", table_name="comicvine_volume_universe")
    op.drop_index("ix_comicvine_volume_universe_publisher", table_name="comicvine_volume_universe")
    op.drop_index("ix_comicvine_volume_universe_volume_id", table_name="comicvine_volume_universe")
    op.drop_table("comicvine_volume_universe")
