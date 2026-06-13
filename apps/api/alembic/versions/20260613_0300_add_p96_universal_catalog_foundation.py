"""add p96 universal catalog foundation

Revision ID: 20260613_0300
Revises: 20260612_0299
Create Date: 2026-06-13 03:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260613_0300"
down_revision = "20260612_0299"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_publisher",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_publisher_name"), "catalog_publisher", ["name"])
    op.create_index("ix_catalog_publisher_normalized_name", "catalog_publisher", ["normalized_name"])

    op.create_table(
        "catalog_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["catalog_publisher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_series_name"), "catalog_series", ["name"])
    op.create_index("ix_catalog_series_normalized_name", "catalog_series", ["normalized_name"])
    op.create_index("ix_catalog_series_publisher_id", "catalog_series", ["publisher_id"])

    op.create_table(
        "catalog_issue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=True),
        sa.Column("issue_number", sa.String(length=32), nullable=False),
        sa.Column("normalized_issue_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_date", sa.Date(), nullable=True),
        sa.Column("store_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("cover_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("source_confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publisher_id"], ["catalog_publisher.id"]),
        sa.ForeignKeyConstraint(["series_id"], ["catalog_series.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_issue_issue_number"), "catalog_issue", ["issue_number"])
    op.create_index(op.f("ix_catalog_issue_normalized_issue_number"), "catalog_issue", ["normalized_issue_number"])
    op.create_index(op.f("ix_catalog_issue_release_date"), "catalog_issue", ["release_date"])
    op.create_index(op.f("ix_catalog_issue_series_id"), "catalog_issue", ["series_id"])
    op.create_index("ix_catalog_issue_publisher_id", "catalog_issue", ["publisher_id"])
    op.create_index("ix_catalog_issue_series_number", "catalog_issue", ["series_id", "normalized_issue_number"])

    op.create_table(
        "catalog_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=True),
        sa.Column("cover_artist", sa.String(length=160), nullable=True),
        sa.Column("ratio", sa.String(length=32), nullable=True),
        sa.Column("print_run", sa.Integer(), nullable=True),
        sa.Column("printing", sa.String(length=64), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["catalog_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_variant_issue_id", "catalog_variant", ["issue_id"])
    op.create_index(op.f("ix_catalog_variant_sku"), "catalog_variant", ["sku"])

    op.create_table(
        "catalog_upc",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("upc", sa.String(length=32), nullable=False),
        sa.Column("normalized_upc", sa.String(length=32), nullable=False),
        sa.Column("barcode_type", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["catalog_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_upc", name="uq_catalog_upc_normalized_upc"),
    )
    op.create_index(op.f("ix_catalog_upc_issue_id"), "catalog_upc", ["issue_id"])
    op.create_index(op.f("ix_catalog_upc_normalized_upc"), "catalog_upc", ["normalized_upc"])
    op.create_index(op.f("ix_catalog_upc_source"), "catalog_upc", ["source"])
    op.create_index(op.f("ix_catalog_upc_upc"), "catalog_upc", ["upc"])
    op.create_index(op.f("ix_catalog_upc_variant_id"), "catalog_upc", ["variant_id"])

    op.create_table(
        "catalog_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("image_type", sa.String(length=32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_image_id", sa.String(length=128), nullable=True),
        sa.Column("download_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["catalog_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_image_checksum"), "catalog_image", ["checksum"])
    op.create_index(op.f("ix_catalog_image_download_status"), "catalog_image", ["download_status"])
    op.create_index(op.f("ix_catalog_image_image_type"), "catalog_image", ["image_type"])
    op.create_index("ix_catalog_image_issue_id", "catalog_image", ["issue_id"])
    op.create_index(op.f("ix_catalog_image_source"), "catalog_image", ["source"])
    op.create_index(op.f("ix_catalog_image_variant_id"), "catalog_image", ["variant_id"])

    op.create_table(
        "catalog_image_fingerprint",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("phash", sa.String(length=64), nullable=True),
        sa.Column("dhash", sa.String(length=64), nullable=True),
        sa.Column("ahash", sa.String(length=64), nullable=True),
        sa.Column("colorhash", sa.String(length=64), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["catalog_image.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["catalog_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id", name="uq_catalog_image_fingerprint_image_id"),
    )
    op.create_index(op.f("ix_catalog_image_fingerprint_ahash"), "catalog_image_fingerprint", ["ahash"])
    op.create_index(op.f("ix_catalog_image_fingerprint_dhash"), "catalog_image_fingerprint", ["dhash"])
    op.create_index(op.f("ix_catalog_image_fingerprint_image_id"), "catalog_image_fingerprint", ["image_id"])
    op.create_index(op.f("ix_catalog_image_fingerprint_issue_id"), "catalog_image_fingerprint", ["issue_id"])
    op.create_index(op.f("ix_catalog_image_fingerprint_phash"), "catalog_image_fingerprint", ["phash"])
    op.create_index(op.f("ix_catalog_image_fingerprint_variant_id"), "catalog_image_fingerprint", ["variant_id"])

    op.create_table(
        "catalog_ocr_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=True),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("extracted_series", sa.String(length=255), nullable=True),
        sa.Column("extracted_issue_number", sa.String(length=32), nullable=True),
        sa.Column("extracted_publisher", sa.String(length=255), nullable=True),
        sa.Column("extracted_price", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["catalog_image.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["catalog_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_ocr_metadata_image_id", "catalog_ocr_metadata", ["image_id"])
    op.create_index(op.f("ix_catalog_ocr_metadata_issue_id"), "catalog_ocr_metadata", ["issue_id"])
    op.create_index(op.f("ix_catalog_ocr_metadata_variant_id"), "catalog_ocr_metadata", ["variant_id"])

    op.create_table(
        "catalog_creator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_creator_name"), "catalog_creator", ["name"])
    op.create_index("ix_catalog_creator_normalized_name", "catalog_creator", ["normalized_name"])

    op.create_table(
        "catalog_character",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_character_name"), "catalog_character", ["name"])
    op.create_index("ix_catalog_character_normalized_name", "catalog_character", ["normalized_name"])

    op.create_table(
        "catalog_story_arc",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("external_source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_story_arc_name"), "catalog_story_arc", ["name"])
    op.create_index("ix_catalog_story_arc_normalized_name", "catalog_story_arc", ["normalized_name"])

    op.create_table(
        "catalog_relationship",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_relationship_relationship_type"), "catalog_relationship", ["relationship_type"])
    op.create_index(op.f("ix_catalog_relationship_source_id"), "catalog_relationship", ["source_id"])
    op.create_index(op.f("ix_catalog_relationship_source_type"), "catalog_relationship", ["source_type"])
    op.create_index(op.f("ix_catalog_relationship_target_id"), "catalog_relationship", ["target_id"])
    op.create_index(op.f("ix_catalog_relationship_target_type"), "catalog_relationship", ["target_type"])
    op.create_index(
        "ix_catalog_relationship_source",
        "catalog_relationship",
        ["source_type", "source_id", "relationship_type"],
    )
    op.create_index("ix_catalog_relationship_target", "catalog_relationship", ["target_type", "target_id"])

    op.create_table(
        "inventory_scan_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=True),
        sa.Column("storage_location_id", sa.Integer(), nullable=True),
        sa.Column("box_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_scanned", sa.Integer(), nullable=False),
        sa.Column("total_matched", sa.Integer(), nullable=False),
        sa.Column("total_unmatched", sa.Integer(), nullable=False),
        sa.Column("total_accepted", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["customer_order.id"]),
        sa.ForeignKeyConstraint(["storage_location_id"], ["p79_storage_location.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_scan_session_mode"), "inventory_scan_session", ["mode"])
    op.create_index(op.f("ix_inventory_scan_session_purchase_order_id"), "inventory_scan_session", ["purchase_order_id"])
    op.create_index(op.f("ix_inventory_scan_session_source_type"), "inventory_scan_session", ["source_type"])
    op.create_index(op.f("ix_inventory_scan_session_status"), "inventory_scan_session", ["status"])
    op.create_index(op.f("ix_inventory_scan_session_storage_location_id"), "inventory_scan_session", ["storage_location_id"])
    op.create_index(op.f("ix_inventory_scan_session_user_id"), "inventory_scan_session", ["user_id"])
    op.create_index("ix_inventory_scan_session_user_status", "inventory_scan_session", ["user_id", "status"])

    op.create_table(
        "inventory_scan_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("raw_upc", sa.String(length=32), nullable=True),
        sa.Column("submitted_image_path", sa.Text(), nullable=True),
        sa.Column("recognition_method", sa.String(length=32), nullable=True),
        sa.Column("predicted_issue_id", sa.Integer(), nullable=True),
        sa.Column("predicted_variant_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("inventory_copy_id", sa.Integer(), nullable=True),
        sa.Column("position_in_session", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inventory_copy_id"], ["inventory_copy.id"]),
        sa.ForeignKeyConstraint(["predicted_issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["predicted_variant_id"], ["catalog_variant.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["inventory_scan_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_scan_item_inventory_copy_id"), "inventory_scan_item", ["inventory_copy_id"])
    op.create_index(op.f("ix_inventory_scan_item_predicted_issue_id"), "inventory_scan_item", ["predicted_issue_id"])
    op.create_index(op.f("ix_inventory_scan_item_predicted_variant_id"), "inventory_scan_item", ["predicted_variant_id"])
    op.create_index(op.f("ix_inventory_scan_item_raw_upc"), "inventory_scan_item", ["raw_upc"])
    op.create_index(op.f("ix_inventory_scan_item_session_id"), "inventory_scan_item", ["session_id"])
    op.create_index(op.f("ix_inventory_scan_item_status"), "inventory_scan_item", ["status"])
    op.create_index("ix_inventory_scan_item_session_status", "inventory_scan_item", ["session_id", "status"])

    op.create_table(
        "catalog_match_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_session_id", sa.Integer(), nullable=True),
        sa.Column("scan_item_id", sa.Integer(), nullable=True),
        sa.Column("submitted_image_path", sa.Text(), nullable=True),
        sa.Column("submitted_upc", sa.String(length=32), nullable=True),
        sa.Column("predicted_issue_id", sa.Integer(), nullable=True),
        sa.Column("predicted_variant_id", sa.Integer(), nullable=True),
        sa.Column("correct_issue_id", sa.Integer(), nullable=True),
        sa.Column("correct_variant_id", sa.Integer(), nullable=True),
        sa.Column("confidence_before", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["correct_issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["correct_variant_id"], ["catalog_variant.id"]),
        sa.ForeignKeyConstraint(["predicted_issue_id"], ["catalog_issue.id"]),
        sa.ForeignKeyConstraint(["predicted_variant_id"], ["catalog_variant.id"]),
        sa.ForeignKeyConstraint(["scan_item_id"], ["inventory_scan_item.id"]),
        sa.ForeignKeyConstraint(["scan_session_id"], ["inventory_scan_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_catalog_match_feedback_feedback_type"), "catalog_match_feedback", ["feedback_type"])
    op.create_index(op.f("ix_catalog_match_feedback_scan_item_id"), "catalog_match_feedback", ["scan_item_id"])
    op.create_index(op.f("ix_catalog_match_feedback_scan_session_id"), "catalog_match_feedback", ["scan_session_id"])
    op.create_index("ix_catalog_match_feedback_scan_session", "catalog_match_feedback", ["scan_session_id"])

    op.add_column("inventory_copy", sa.Column("catalog_issue_id", sa.Integer(), nullable=True))
    op.add_column("inventory_copy", sa.Column("catalog_variant_id", sa.Integer(), nullable=True))
    op.add_column("inventory_copy", sa.Column("catalog_image_id", sa.Integer(), nullable=True))
    op.add_column("inventory_copy", sa.Column("inventory_scan_session_id", sa.Integer(), nullable=True))
    op.add_column("inventory_copy", sa.Column("inventory_scan_item_id", sa.Integer(), nullable=True))
    op.add_column("inventory_copy", sa.Column("acquisition_source_type", sa.String(length=40), nullable=True))
    op.add_column("inventory_copy", sa.Column("acquisition_source_name", sa.String(length=255), nullable=True))
    op.add_column("inventory_copy", sa.Column("acquisition_notes", sa.String(), nullable=True))
    op.create_index(op.f("ix_inventory_copy_acquisition_source_type"), "inventory_copy", ["acquisition_source_type"])
    op.create_index(op.f("ix_inventory_copy_catalog_image_id"), "inventory_copy", ["catalog_image_id"])
    op.create_index(op.f("ix_inventory_copy_catalog_issue_id"), "inventory_copy", ["catalog_issue_id"])
    op.create_index(op.f("ix_inventory_copy_catalog_variant_id"), "inventory_copy", ["catalog_variant_id"])
    op.create_index(op.f("ix_inventory_copy_inventory_scan_item_id"), "inventory_copy", ["inventory_scan_item_id"])
    op.create_index(op.f("ix_inventory_copy_inventory_scan_session_id"), "inventory_copy", ["inventory_scan_session_id"])
    op.create_foreign_key(
        "fk_inventory_copy_catalog_issue_id_catalog_issue",
        "inventory_copy",
        "catalog_issue",
        ["catalog_issue_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inventory_copy_catalog_variant_id_catalog_variant",
        "inventory_copy",
        "catalog_variant",
        ["catalog_variant_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inventory_copy_catalog_image_id_catalog_image",
        "inventory_copy",
        "catalog_image",
        ["catalog_image_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inv_copy_inv_scan_sess_id",
        "inventory_copy",
        "inventory_scan_session",
        ["inventory_scan_session_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inv_copy_inv_scan_item_id",
        "inventory_copy",
        "inventory_scan_item",
        ["inventory_scan_item_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inv_copy_inv_scan_item_id",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_inv_copy_inv_scan_sess_id",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_inventory_copy_catalog_image_id_catalog_image",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_inventory_copy_catalog_variant_id_catalog_variant",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_inventory_copy_catalog_issue_id_catalog_issue",
        "inventory_copy",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_inventory_copy_inventory_scan_session_id"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_inventory_scan_item_id"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_catalog_variant_id"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_catalog_issue_id"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_catalog_image_id"), table_name="inventory_copy")
    op.drop_index(op.f("ix_inventory_copy_acquisition_source_type"), table_name="inventory_copy")
    op.drop_column("inventory_copy", "acquisition_notes")
    op.drop_column("inventory_copy", "acquisition_source_name")
    op.drop_column("inventory_copy", "acquisition_source_type")
    op.drop_column("inventory_copy", "inventory_scan_item_id")
    op.drop_column("inventory_copy", "inventory_scan_session_id")
    op.drop_column("inventory_copy", "catalog_image_id")
    op.drop_column("inventory_copy", "catalog_variant_id")
    op.drop_column("inventory_copy", "catalog_issue_id")

    op.drop_index("ix_catalog_match_feedback_scan_session", table_name="catalog_match_feedback")
    op.drop_index(op.f("ix_catalog_match_feedback_scan_session_id"), table_name="catalog_match_feedback")
    op.drop_index(op.f("ix_catalog_match_feedback_scan_item_id"), table_name="catalog_match_feedback")
    op.drop_index(op.f("ix_catalog_match_feedback_feedback_type"), table_name="catalog_match_feedback")
    op.drop_table("catalog_match_feedback")

    op.drop_index("ix_inventory_scan_item_session_status", table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_status"), table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_session_id"), table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_raw_upc"), table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_predicted_variant_id"), table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_predicted_issue_id"), table_name="inventory_scan_item")
    op.drop_index(op.f("ix_inventory_scan_item_inventory_copy_id"), table_name="inventory_scan_item")
    op.drop_table("inventory_scan_item")

    op.drop_index("ix_inventory_scan_session_user_status", table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_user_id"), table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_storage_location_id"), table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_status"), table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_source_type"), table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_purchase_order_id"), table_name="inventory_scan_session")
    op.drop_index(op.f("ix_inventory_scan_session_mode"), table_name="inventory_scan_session")
    op.drop_table("inventory_scan_session")

    op.drop_index("ix_catalog_relationship_target", table_name="catalog_relationship")
    op.drop_index("ix_catalog_relationship_source", table_name="catalog_relationship")
    op.drop_index(op.f("ix_catalog_relationship_target_type"), table_name="catalog_relationship")
    op.drop_index(op.f("ix_catalog_relationship_target_id"), table_name="catalog_relationship")
    op.drop_index(op.f("ix_catalog_relationship_source_type"), table_name="catalog_relationship")
    op.drop_index(op.f("ix_catalog_relationship_source_id"), table_name="catalog_relationship")
    op.drop_index(op.f("ix_catalog_relationship_relationship_type"), table_name="catalog_relationship")
    op.drop_table("catalog_relationship")

    op.drop_index("ix_catalog_story_arc_normalized_name", table_name="catalog_story_arc")
    op.drop_index(op.f("ix_catalog_story_arc_name"), table_name="catalog_story_arc")
    op.drop_table("catalog_story_arc")

    op.drop_index("ix_catalog_character_normalized_name", table_name="catalog_character")
    op.drop_index(op.f("ix_catalog_character_name"), table_name="catalog_character")
    op.drop_table("catalog_character")

    op.drop_index("ix_catalog_creator_normalized_name", table_name="catalog_creator")
    op.drop_index(op.f("ix_catalog_creator_name"), table_name="catalog_creator")
    op.drop_table("catalog_creator")

    op.drop_index("ix_catalog_ocr_metadata_image_id", table_name="catalog_ocr_metadata")
    op.drop_index(op.f("ix_catalog_ocr_metadata_variant_id"), table_name="catalog_ocr_metadata")
    op.drop_index(op.f("ix_catalog_ocr_metadata_issue_id"), table_name="catalog_ocr_metadata")
    op.drop_table("catalog_ocr_metadata")

    op.drop_index(op.f("ix_catalog_image_fingerprint_variant_id"), table_name="catalog_image_fingerprint")
    op.drop_index(op.f("ix_catalog_image_fingerprint_phash"), table_name="catalog_image_fingerprint")
    op.drop_index(op.f("ix_catalog_image_fingerprint_issue_id"), table_name="catalog_image_fingerprint")
    op.drop_index(op.f("ix_catalog_image_fingerprint_image_id"), table_name="catalog_image_fingerprint")
    op.drop_index(op.f("ix_catalog_image_fingerprint_dhash"), table_name="catalog_image_fingerprint")
    op.drop_index(op.f("ix_catalog_image_fingerprint_ahash"), table_name="catalog_image_fingerprint")
    op.drop_table("catalog_image_fingerprint")

    op.drop_index("ix_catalog_image_issue_id", table_name="catalog_image")
    op.drop_index(op.f("ix_catalog_image_variant_id"), table_name="catalog_image")
    op.drop_index(op.f("ix_catalog_image_source"), table_name="catalog_image")
    op.drop_index(op.f("ix_catalog_image_image_type"), table_name="catalog_image")
    op.drop_index(op.f("ix_catalog_image_download_status"), table_name="catalog_image")
    op.drop_index(op.f("ix_catalog_image_checksum"), table_name="catalog_image")
    op.drop_table("catalog_image")

    op.drop_index(op.f("ix_catalog_upc_variant_id"), table_name="catalog_upc")
    op.drop_index(op.f("ix_catalog_upc_upc"), table_name="catalog_upc")
    op.drop_index(op.f("ix_catalog_upc_source"), table_name="catalog_upc")
    op.drop_index(op.f("ix_catalog_upc_normalized_upc"), table_name="catalog_upc")
    op.drop_index(op.f("ix_catalog_upc_issue_id"), table_name="catalog_upc")
    op.drop_table("catalog_upc")

    op.drop_index("ix_catalog_variant_issue_id", table_name="catalog_variant")
    op.drop_index(op.f("ix_catalog_variant_sku"), table_name="catalog_variant")
    op.drop_table("catalog_variant")

    op.drop_index("ix_catalog_issue_series_number", table_name="catalog_issue")
    op.drop_index("ix_catalog_issue_publisher_id", table_name="catalog_issue")
    op.drop_index(op.f("ix_catalog_issue_series_id"), table_name="catalog_issue")
    op.drop_index(op.f("ix_catalog_issue_release_date"), table_name="catalog_issue")
    op.drop_index(op.f("ix_catalog_issue_normalized_issue_number"), table_name="catalog_issue")
    op.drop_index(op.f("ix_catalog_issue_issue_number"), table_name="catalog_issue")
    op.drop_table("catalog_issue")

    op.drop_index("ix_catalog_series_publisher_id", table_name="catalog_series")
    op.drop_index("ix_catalog_series_normalized_name", table_name="catalog_series")
    op.drop_index(op.f("ix_catalog_series_name"), table_name="catalog_series")
    op.drop_table("catalog_series")

    op.drop_index("ix_catalog_publisher_normalized_name", table_name="catalog_publisher")
    op.drop_index(op.f("ix_catalog_publisher_name"), table_name="catalog_publisher")
    op.drop_table("catalog_publisher")
