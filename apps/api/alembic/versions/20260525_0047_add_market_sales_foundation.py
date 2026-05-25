"""P35-02 market sales foundation.

Revision ID: 20260525_0047
Revises: 20260525_0046
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0047"
down_revision: str | None = "20260525_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_source",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("import_priority", sa.Integer(), nullable=False),
        sa.Column("supports_raw", sa.Boolean(), nullable=False),
        sa.Column("supports_graded", sa.Boolean(), nullable=False),
        sa.Column("supports_variants", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", name="uq_market_source_source_name"),
    )
    op.create_index(op.f("ix_market_source_source_name"), "market_source", ["source_name"], unique=False)
    op.create_index(op.f("ix_market_source_source_type"), "market_source", ["source_type"], unique=False)
    op.create_index(op.f("ix_market_source_import_priority"), "market_source", ["import_priority"], unique=False)

    op.create_table(
        "market_source_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("import_status", sa.String(length=32), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("imported_records", sa.Integer(), nullable=False),
        sa.Column("failed_records", sa.Integer(), nullable=False),
        sa.Column("skipped_records", sa.Integer(), nullable=False),
        sa.Column("source_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_source_id"], ["market_source.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_source_id", "snapshot_date", name="uq_market_source_snapshot_source_date"),
    )
    op.create_index(
        op.f("ix_market_source_snapshot_market_source_id"),
        "market_source_snapshot",
        ["market_source_id"],
        unique=False,
    )
    op.create_index(op.f("ix_market_source_snapshot_snapshot_date"), "market_source_snapshot", ["snapshot_date"], unique=False)
    op.create_index(op.f("ix_market_source_snapshot_import_status"), "market_source_snapshot", ["import_status"], unique=False)

    op.create_table(
        "market_sale_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_source_id", sa.Integer(), nullable=False),
        sa.Column("source_listing_id", sa.String(length=255), nullable=True),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("listing_type", sa.String(length=24), nullable=False),
        sa.Column("raw_title", sa.String(length=510), nullable=False),
        sa.Column("normalized_title", sa.String(length=510), nullable=True),
        sa.Column("raw_issue", sa.String(length=120), nullable=False),
        sa.Column("normalized_issue", sa.String(length=120), nullable=True),
        sa.Column("raw_publisher", sa.String(length=255), nullable=True),
        sa.Column("normalized_publisher", sa.String(length=255), nullable=True),
        sa.Column("raw_variant", sa.String(length=255), nullable=True),
        sa.Column("normalized_variant", sa.String(length=255), nullable=True),
        sa.Column("raw_grade", sa.String(length=120), nullable=True),
        sa.Column("normalized_grade", sa.String(length=120), nullable=True),
        sa.Column("raw_cert_number", sa.String(length=120), nullable=True),
        sa.Column("normalized_cert_number", sa.String(length=120), nullable=True),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("shipping_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=True),
        sa.Column("seller_name", sa.String(length=255), nullable=True),
        sa.Column("buyer_name", sa.String(length=255), nullable=True),
        sa.Column("is_graded", sa.Boolean(), nullable=False),
        sa.Column("grading_company", sa.String(length=80), nullable=True),
        sa.Column("is_signed", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("source_metadata_json", sa.JSON(), nullable=False),
        sa.Column("normalization_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_source_id"], ["market_source.id"]),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["market_source_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_source_id", "source_listing_id", name="uq_market_sale_record_source_listing"),
    )
    op.create_index(op.f("ix_market_sale_record_market_source_id"), "market_sale_record", ["market_source_id"], unique=False)
    op.create_index(op.f("ix_market_sale_record_source_listing_id"), "market_sale_record", ["source_listing_id"], unique=False)
    op.create_index(op.f("ix_market_sale_record_source_snapshot_id"), "market_sale_record", ["source_snapshot_id"], unique=False)
    op.create_index(op.f("ix_market_sale_record_listing_type"), "market_sale_record", ["listing_type"], unique=False)
    op.create_index(op.f("ix_market_sale_record_raw_title"), "market_sale_record", ["raw_title"], unique=False)
    op.create_index(op.f("ix_market_sale_record_normalized_title"), "market_sale_record", ["normalized_title"], unique=False)
    op.create_index(op.f("ix_market_sale_record_raw_issue"), "market_sale_record", ["raw_issue"], unique=False)
    op.create_index(op.f("ix_market_sale_record_normalized_issue"), "market_sale_record", ["normalized_issue"], unique=False)
    op.create_index(op.f("ix_market_sale_record_raw_publisher"), "market_sale_record", ["raw_publisher"], unique=False)
    op.create_index(op.f("ix_market_sale_record_normalized_publisher"), "market_sale_record", ["normalized_publisher"], unique=False)
    op.create_index(op.f("ix_market_sale_record_normalized_variant"), "market_sale_record", ["normalized_variant"], unique=False)
    op.create_index(op.f("ix_market_sale_record_normalized_grade"), "market_sale_record", ["normalized_grade"], unique=False)
    op.create_index(
        op.f("ix_market_sale_record_normalized_cert_number"),
        "market_sale_record",
        ["normalized_cert_number"],
        unique=False,
    )
    op.create_index(op.f("ix_market_sale_record_currency_code"), "market_sale_record", ["currency_code"], unique=False)
    op.create_index(op.f("ix_market_sale_record_sale_date"), "market_sale_record", ["sale_date"], unique=False)
    op.create_index(op.f("ix_market_sale_record_is_graded"), "market_sale_record", ["is_graded"], unique=False)
    op.create_index(op.f("ix_market_sale_record_grading_company"), "market_sale_record", ["grading_company"], unique=False)
    op.create_index(op.f("ix_market_sale_record_is_signed"), "market_sale_record", ["is_signed"], unique=False)
    op.create_index(
        op.f("ix_market_sale_record_normalization_status"),
        "market_sale_record",
        ["normalization_status"],
        unique=False,
    )

    op.create_table(
        "market_sale_record_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("image_sha256", sa.String(length=64), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market_sale_record_id", "display_order", name="uq_market_sale_record_image_order"),
    )
    op.create_index(
        op.f("ix_market_sale_record_image_market_sale_record_id"),
        "market_sale_record_image",
        ["market_sale_record_id"],
        unique=False,
    )
    op.create_index(op.f("ix_market_sale_record_image_image_sha256"), "market_sale_record_image", ["image_sha256"], unique=False)
    op.create_index(op.f("ix_market_sale_record_image_display_order"), "market_sale_record_image", ["display_order"], unique=False)

    op.create_table(
        "market_sale_normalization_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_sale_record_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_sale_record_id"], ["market_sale_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_market_sale_normalization_issue_market_sale_record_id"),
        "market_sale_normalization_issue",
        ["market_sale_record_id"],
        unique=False,
    )
    op.create_index(op.f("ix_market_sale_normalization_issue_issue_type"), "market_sale_normalization_issue", ["issue_type"], unique=False)
    op.create_index(op.f("ix_market_sale_normalization_issue_severity"), "market_sale_normalization_issue", ["severity"], unique=False)

    anchored = datetime.now(timezone.utc)
    seed_rows = [
        {
            "source_name": "eBay",
            "source_type": "marketplace",
            "enabled": True,
            "import_priority": 10,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Deterministic marketplace registry row for future manual imports.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "Heritage Auctions",
            "source_type": "auction",
            "enabled": True,
            "import_priority": 20,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Auction registry row for deterministic market-sale capture.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "MyComicShop",
            "source_type": "fixed_price",
            "enabled": True,
            "import_priority": 30,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Fixed-price marketplace row for catalog-style sales imports.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "ComicLink",
            "source_type": "auction",
            "enabled": True,
            "import_priority": 40,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Secondary auction registry row for comparables.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "GPA",
            "source_type": "historical_archive",
            "enabled": True,
            "import_priority": 50,
            "supports_raw": False,
            "supports_graded": True,
            "supports_variants": False,
            "notes": "Historical archive source row used for deterministic comps reference.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "Shortboxed",
            "source_type": "marketplace",
            "enabled": True,
            "import_priority": 60,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Marketplace registry row for modern market-sale records.",
            "created_at": anchored,
            "updated_at": anchored,
        },
        {
            "source_name": "HipComic",
            "source_type": "marketplace",
            "enabled": True,
            "import_priority": 70,
            "supports_raw": True,
            "supports_graded": True,
            "supports_variants": True,
            "notes": "Marketplace registry row for lightweight market-sale imports.",
            "created_at": anchored,
            "updated_at": anchored,
        },
    ]
    op.bulk_insert(
        sa.table(
            "market_source",
            sa.column("source_name", sa.String(length=120)),
            sa.column("source_type", sa.String(length=40)),
            sa.column("enabled", sa.Boolean()),
            sa.column("import_priority", sa.Integer()),
            sa.column("supports_raw", sa.Boolean()),
            sa.column("supports_graded", sa.Boolean()),
            sa.column("supports_variants", sa.Boolean()),
            sa.column("notes", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        seed_rows,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_market_sale_normalization_issue_severity"), table_name="market_sale_normalization_issue")
    op.drop_index(op.f("ix_market_sale_normalization_issue_issue_type"), table_name="market_sale_normalization_issue")
    op.drop_index(op.f("ix_market_sale_normalization_issue_market_sale_record_id"), table_name="market_sale_normalization_issue")
    op.drop_table("market_sale_normalization_issue")

    op.drop_index(op.f("ix_market_sale_record_image_display_order"), table_name="market_sale_record_image")
    op.drop_index(op.f("ix_market_sale_record_image_image_sha256"), table_name="market_sale_record_image")
    op.drop_index(op.f("ix_market_sale_record_image_market_sale_record_id"), table_name="market_sale_record_image")
    op.drop_table("market_sale_record_image")

    op.drop_index(op.f("ix_market_sale_record_normalization_status"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_is_signed"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_grading_company"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_is_graded"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_sale_date"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_currency_code"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_normalized_cert_number"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_normalized_grade"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_normalized_publisher"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_normalized_issue"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_normalized_title"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_raw_publisher"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_raw_issue"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_raw_title"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_listing_type"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_source_snapshot_id"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_source_listing_id"), table_name="market_sale_record")
    op.drop_index(op.f("ix_market_sale_record_market_source_id"), table_name="market_sale_record")
    op.drop_table("market_sale_record")

    op.drop_index(op.f("ix_market_source_snapshot_import_status"), table_name="market_source_snapshot")
    op.drop_index(op.f("ix_market_source_snapshot_snapshot_date"), table_name="market_source_snapshot")
    op.drop_index(op.f("ix_market_source_snapshot_market_source_id"), table_name="market_source_snapshot")
    op.drop_table("market_source_snapshot")

    op.drop_index(op.f("ix_market_source_import_priority"), table_name="market_source")
    op.drop_index(op.f("ix_market_source_source_type"), table_name="market_source")
    op.drop_index(op.f("ix_market_source_source_name"), table_name="market_source")
    op.drop_table("market_source")
