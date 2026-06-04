"""Add collector ratio variant strategy fields to purchase_preference."""

from alembic import op
import sqlalchemy as sa

revision = "20260604_0213"
down_revision = "20261006_0212"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_preference",
        sa.Column("ratio_variant_strategy", sa.String(length=24), nullable=False, server_default="conservative"),
    )
    op.add_column(
        "purchase_preference",
        sa.Column("max_ratio_variant_price", sa.Float(), nullable=False, server_default="25.0"),
    )
    op.add_column(
        "purchase_preference",
        sa.Column("high_ratio_exception_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "purchase_preference",
        sa.Column("high_ratio_threshold", sa.Integer(), nullable=False, server_default="50"),
    )


def downgrade() -> None:
    op.drop_column("purchase_preference", "high_ratio_threshold")
    op.drop_column("purchase_preference", "high_ratio_exception_required")
    op.drop_column("purchase_preference", "max_ratio_variant_price")
    op.drop_column("purchase_preference", "ratio_variant_strategy")
