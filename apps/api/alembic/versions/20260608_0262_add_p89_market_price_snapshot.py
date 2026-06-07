"""Add P89 market price snapshots."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0262"
down_revision = "20260608_0261"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "p89_market_price_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("variant", sa.String(length=200), nullable=False),
        sa.Column("quick_sale_price", sa.Float(), nullable=False),
        sa.Column("market_price", sa.Float(), nullable=False),
        sa.Column("premium_price", sa.Float(), nullable=False),
        sa.Column("pricing_confidence", sa.String(length=8), nullable=False),
        sa.Column("sales_velocity", sa.String(length=16), nullable=False),
        sa.Column("listing_count", sa.Integer(), nullable=False),
        sa.Column("sold_count", sa.Integer(), nullable=False),
        sa.Column("price_low", sa.Float(), nullable=False),
        sa.Column("price_high", sa.Float(), nullable=False),
        sa.Column("price_average", sa.Float(), nullable=False),
        sa.Column("trend_direction", sa.String(length=8), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "series",
            "issue_number",
            "variant",
            "snapshot_date",
            name="uq_p89_mkt_price_snap_day",
        ),
    )
    op.create_index(op.f("ix_p89_market_price_snapshot_owner_user_id"), "p89_market_price_snapshot", ["owner_user_id"])
    op.create_index(op.f("ix_p89_market_price_snapshot_series"), "p89_market_price_snapshot", ["series"])
    op.create_index(op.f("ix_p89_market_price_snapshot_issue_number"), "p89_market_price_snapshot", ["issue_number"])
    op.create_index(op.f("ix_p89_market_price_snapshot_pricing_confidence"), "p89_market_price_snapshot", ["pricing_confidence"])
    op.create_index("ix_p89_mkt_price_owner_date", "p89_market_price_snapshot", ["owner_user_id", "snapshot_date"])
    op.create_index("ix_p89_mkt_price_owner_conf", "p89_market_price_snapshot", ["owner_user_id", "pricing_confidence"])


def downgrade() -> None:
    op.drop_index("ix_p89_mkt_price_owner_conf", table_name="p89_market_price_snapshot")
    op.drop_index("ix_p89_mkt_price_owner_date", table_name="p89_market_price_snapshot")
    op.drop_index(op.f("ix_p89_market_price_snapshot_pricing_confidence"), table_name="p89_market_price_snapshot")
    op.drop_index(op.f("ix_p89_market_price_snapshot_issue_number"), table_name="p89_market_price_snapshot")
    op.drop_index(op.f("ix_p89_market_price_snapshot_series"), table_name="p89_market_price_snapshot")
    op.drop_index(op.f("ix_p89_market_price_snapshot_owner_user_id"), table_name="p89_market_price_snapshot")
    op.drop_table("p89_market_price_snapshot")
