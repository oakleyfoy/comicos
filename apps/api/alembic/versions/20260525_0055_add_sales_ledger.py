"""P36-03 sales ledger foundation (realized sale truth; append-only history).

Revision ID: 20260525_0055
Revises: 20260525_0054
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0055"
down_revision: str | None = "20260525_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sale_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("buyer_reference", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("gross_sale_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("item_subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_charged_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_collected_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("shipping_cost_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("other_cost_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_proceeds_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("acquisition_cost_basis_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("realized_profit_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("realized_margin_pct", sa.Numeric(18, 8), nullable=True),
        sa.Column("replay_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.UniqueConstraint("owner_user_id", "replay_key", name="uq_sale_record_owner_replay"),
    )
    op.create_index("ix_sale_record_owner_created_at", "sale_record", ["owner_user_id", "created_at", "id"], unique=False)
    op.create_index("ix_sale_record_owner_status", "sale_record", ["owner_user_id", "status"], unique=False)
    op.create_index(op.f("ix_sale_record_listing_id"), "sale_record", ["listing_id"], unique=False)
    op.create_index(op.f("ix_sale_record_channel"), "sale_record", ["channel"], unique=False)
    op.create_index(op.f("ix_sale_record_sale_date"), "sale_record", ["sale_date"], unique=False)
    op.create_index(op.f("ix_sale_record_currency"), "sale_record", ["currency"], unique=False)

    op.create_table(
        "sale_record_line_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sale_record_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("canonical_comic_issue_id", sa.Integer(), nullable=True),
        sa.Column("quantity_sold", sa.Integer(), nullable=False),
        sa.Column("unit_sale_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_subtotal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("cost_basis_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("realized_profit_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["canonical_comic_issue_id"], ["comic_issue.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["sale_record_id"], ["sale_record.id"]),
    )
    op.create_index(
        "ix_sale_line_item_sale_created",
        "sale_record_line_item",
        ["sale_record_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(op.f("ix_sale_record_line_item_sale_record_id"), "sale_record_line_item", ["sale_record_id"], unique=False)
    op.create_index(op.f("ix_sale_record_line_item_listing_id"), "sale_record_line_item", ["listing_id"], unique=False)
    op.create_index(
        op.f("ix_sale_record_line_item_inventory_item_id"),
        "sale_record_line_item",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sale_record_line_item_canonical_comic_issue_id"),
        "sale_record_line_item",
        ["canonical_comic_issue_id"],
        unique=False,
    )

    op.create_table(
        "sale_financial_adjustment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sale_record_id", sa.Integer(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["sale_record_id"], ["sale_record.id"]),
    )
    op.create_index(
        "ix_sale_fin_adjustment_sale_created",
        "sale_financial_adjustment",
        ["sale_record_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sale_financial_adjustment_sale_record_id"),
        "sale_financial_adjustment",
        ["sale_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sale_financial_adjustment_adjustment_type"),
        "sale_financial_adjustment",
        ["adjustment_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sale_financial_adjustment_currency"),
        "sale_financial_adjustment",
        ["currency"],
        unique=False,
    )

    op.create_table(
        "sale_lifecycle_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sale_record_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("prior_status", sa.String(length=24), nullable=True),
        sa.Column("new_status", sa.String(length=24), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["sale_record_id"], ["sale_record.id"]),
    )
    op.create_index(
        "ix_sale_lifecycle_event_sale_created",
        "sale_lifecycle_event",
        ["sale_record_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sale_lifecycle_event_sale_record_id"),
        "sale_lifecycle_event",
        ["sale_record_id"],
        unique=False,
    )
    op.create_index(op.f("ix_sale_lifecycle_event_event_type"), "sale_lifecycle_event", ["event_type"], unique=False)
    op.create_index(
        op.f("ix_sale_lifecycle_event_created_by_user_id"),
        "sale_lifecycle_event",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sale_lifecycle_event_created_by_user_id"), table_name="sale_lifecycle_event")
    op.drop_index(op.f("ix_sale_lifecycle_event_event_type"), table_name="sale_lifecycle_event")
    op.drop_index(op.f("ix_sale_lifecycle_event_sale_record_id"), table_name="sale_lifecycle_event")
    op.drop_index("ix_sale_lifecycle_event_sale_created", table_name="sale_lifecycle_event")
    op.drop_table("sale_lifecycle_event")

    op.drop_index(op.f("ix_sale_financial_adjustment_currency"), table_name="sale_financial_adjustment")
    op.drop_index(op.f("ix_sale_financial_adjustment_adjustment_type"), table_name="sale_financial_adjustment")
    op.drop_index(op.f("ix_sale_financial_adjustment_sale_record_id"), table_name="sale_financial_adjustment")
    op.drop_index("ix_sale_fin_adjustment_sale_created", table_name="sale_financial_adjustment")
    op.drop_table("sale_financial_adjustment")

    op.drop_index(op.f("ix_sale_record_line_item_canonical_comic_issue_id"), table_name="sale_record_line_item")
    op.drop_index(op.f("ix_sale_record_line_item_inventory_item_id"), table_name="sale_record_line_item")
    op.drop_index(op.f("ix_sale_record_line_item_listing_id"), table_name="sale_record_line_item")
    op.drop_index(op.f("ix_sale_record_line_item_sale_record_id"), table_name="sale_record_line_item")
    op.drop_index("ix_sale_line_item_sale_created", table_name="sale_record_line_item")
    op.drop_table("sale_record_line_item")

    op.drop_index(op.f("ix_sale_record_currency"), table_name="sale_record")
    op.drop_index(op.f("ix_sale_record_sale_date"), table_name="sale_record")
    op.drop_index(op.f("ix_sale_record_channel"), table_name="sale_record")
    op.drop_index(op.f("ix_sale_record_listing_id"), table_name="sale_record")
    op.drop_index("ix_sale_record_owner_status", table_name="sale_record")
    op.drop_index("ix_sale_record_owner_created_at", table_name="sale_record")
    op.drop_table("sale_record")
