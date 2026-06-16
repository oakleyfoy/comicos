"""P98 master universe skeleton tables (additive only)."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260619_0210"
down_revision: str | None = "20260619_0209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universe_publisher",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comicvine_publisher_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_universe_publisher_normalized_name"),
    )
    op.create_index("ix_universe_publisher_comicvine_id", "universe_publisher", ["comicvine_publisher_id"])
    op.create_index("ix_universe_publisher_normalized_name", "universe_publisher", ["normalized_name"])

    op.create_table(
        "universe_volume",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comicvine_volume_id", sa.Integer(), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("normalized_name", sa.String(length=512), nullable=False),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("count_of_issues", sa.Integer(), nullable=True),
        sa.Column("volume_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["universe_publisher.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comicvine_volume_id", name="uq_universe_volume_comicvine_volume_id"),
    )
    op.create_index("ix_universe_volume_publisher_id", "universe_volume", ["publisher_id"])
    op.create_index("ix_universe_volume_normalized_name", "universe_volume", ["normalized_name"])
    op.create_index("ix_universe_volume_comicvine_volume_id", "universe_volume", ["comicvine_volume_id"])

    op.create_table(
        "universe_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comicvine_issue_id", sa.Integer(), nullable=True),
        sa.Column("volume_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("normalized_issue_number", sa.String(length=32), nullable=False),
        sa.Column("issue_title", sa.Text(), nullable=True),
        sa.Column("cover_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DISCOVERED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["universe_volume.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volume_id", "normalized_issue_number", name="uq_universe_issue_volume_number"),
    )
    op.create_index("ix_universe_issue_volume_id", "universe_issue", ["volume_id"])
    op.create_index("ix_universe_issue_number", "universe_issue", ["issue_number"])
    op.create_index("ix_universe_issue_comicvine_issue_id", "universe_issue", ["comicvine_issue_id"])
    op.create_index("ix_universe_issue_status", "universe_issue", ["status"])

    op.create_table(
        "universe_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("variant_type", sa.String(length=32), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("comicvine_variant_id", sa.Integer(), nullable=True),
        sa.Column("catalog_issue_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DISCOVERED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["universe_issue.id"]),
        sa.ForeignKeyConstraint(["catalog_issue_id"], ["catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issue_id",
            "variant_type",
            "variant_name",
            name="uq_universe_variant_issue_type_name",
        ),
    )
    op.create_index("ix_universe_variant_issue_id", "universe_variant", ["issue_id"])
    op.create_index("ix_universe_variant_variant_type", "universe_variant", ["variant_type"])
    op.create_index("ix_universe_variant_catalog_issue_id", "universe_variant", ["catalog_issue_id"])
    op.create_index("ix_universe_variant_status", "universe_variant", ["status"])

    op.create_table(
        "acquisition_universe_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("placeholder_id", sa.Integer(), nullable=False),
        sa.Column("universe_variant_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["placeholder_id"], ["acquisition_placeholder_issue.id"]),
        sa.ForeignKeyConstraint(["universe_variant_id"], ["universe_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("placeholder_id", name="uq_acquisition_universe_link_placeholder"),
    )
    op.create_index("ix_acquisition_universe_link_placeholder_id", "acquisition_universe_link", ["placeholder_id"])
    op.create_index(
        "ix_acquisition_universe_link_universe_variant_id",
        "acquisition_universe_link",
        ["universe_variant_id"],
    )

    op.add_column("collection_gap_target", sa.Column("universe_issue_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_collection_gap_target_universe_issue",
        "collection_gap_target",
        "universe_issue",
        ["universe_issue_id"],
        ["id"],
    )
    op.create_index(
        "ix_collection_gap_target_universe_issue_id",
        "collection_gap_target",
        ["universe_issue_id"],
    )

    op.add_column("want_list_item", sa.Column("universe_variant_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_want_list_item_universe_variant",
        "want_list_item",
        "universe_variant",
        ["universe_variant_id"],
        ["id"],
    )
    op.create_index("ix_want_list_item_universe_variant_id", "want_list_item", ["universe_variant_id"])


def downgrade() -> None:
    op.drop_index("ix_want_list_item_universe_variant_id", table_name="want_list_item")
    op.drop_constraint("fk_want_list_item_universe_variant", "want_list_item", type_="foreignkey")
    op.drop_column("want_list_item", "universe_variant_id")

    op.drop_index("ix_collection_gap_target_universe_issue_id", table_name="collection_gap_target")
    op.drop_constraint("fk_collection_gap_target_universe_issue", "collection_gap_target", type_="foreignkey")
    op.drop_column("collection_gap_target", "universe_issue_id")

    op.drop_index("ix_acquisition_universe_link_universe_variant_id", table_name="acquisition_universe_link")
    op.drop_index("ix_acquisition_universe_link_placeholder_id", table_name="acquisition_universe_link")
    op.drop_table("acquisition_universe_link")

    op.drop_index("ix_universe_variant_status", table_name="universe_variant")
    op.drop_index("ix_universe_variant_catalog_issue_id", table_name="universe_variant")
    op.drop_index("ix_universe_variant_variant_type", table_name="universe_variant")
    op.drop_index("ix_universe_variant_issue_id", table_name="universe_variant")
    op.drop_table("universe_variant")

    op.drop_index("ix_universe_issue_status", table_name="universe_issue")
    op.drop_index("ix_universe_issue_comicvine_issue_id", table_name="universe_issue")
    op.drop_index("ix_universe_issue_number", table_name="universe_issue")
    op.drop_index("ix_universe_issue_volume_id", table_name="universe_issue")
    op.drop_table("universe_issue")

    op.drop_index("ix_universe_volume_comicvine_volume_id", table_name="universe_volume")
    op.drop_index("ix_universe_volume_normalized_name", table_name="universe_volume")
    op.drop_index("ix_universe_volume_publisher_id", table_name="universe_volume")
    op.drop_table("universe_volume")

    op.drop_index("ix_universe_publisher_normalized_name", table_name="universe_publisher")
    op.drop_index("ix_universe_publisher_comicvine_id", table_name="universe_publisher")
    op.drop_table("universe_publisher")
