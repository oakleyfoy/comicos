"""Shared catalog-spine joins + display expressions for inventory reads (post–Phase D).

Legacy ``customer_order`` / ``order_item`` / ``variant`` / ``comic_issue`` tables
are dropped in migration ``20260626_0200``. Inventory identity and provenance come
from ``catalog_issue`` + ``acquisition`` and denormalized fields on ``inventory_copy``.
"""

from __future__ import annotations

from sqlalchemy import func, literal, literal_column

from app.models import (
    Acquisition,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    CatalogVariant,
    InventoryCopy,
)
from app.models.acquisition import AcquisitionPlaceholderIssue


# Inline constant fallbacks (literal_column) instead of bound parameters so the
# coalesce() SQL text is identical wherever the expression is reused. Postgres
# matches GROUP BY against SELECT by expression text; bound params get distinct
# placeholders in SELECT vs GROUP BY and break "must appear in GROUP BY" checks.
_UNKNOWN = literal_column("'Unknown'")
_EMPTY = literal_column("''")


def title_expr():
    return func.coalesce(CatalogSeries.name, AcquisitionPlaceholderIssue.title, _UNKNOWN)


def publisher_expr():
    return func.coalesce(CatalogPublisher.name, AcquisitionPlaceholderIssue.publisher, _UNKNOWN)


def issue_number_expr():
    return func.coalesce(CatalogIssue.issue_number, AcquisitionPlaceholderIssue.issue_number, _EMPTY)


def cover_name_expr():
    return func.coalesce(CatalogVariant.variant_name, InventoryCopy.variant_status)


def retailer_expr():
    return func.coalesce(
        InventoryCopy.order_retailer,
        Acquisition.seller_name,
        "Manual Acquisition",
    )


def purchase_date_expr():
    return func.coalesce(InventoryCopy.order_date, Acquisition.purchase_date)


def source_type_expr():
    return func.coalesce(InventoryCopy.order_source_type, Acquisition.acquisition_type)


def order_item_id_expr():
    return InventoryCopy.order_item_id


def order_id_expr():
    return InventoryCopy.order_item_id


def order_item_quantity_expr():
    return literal(1)


def apply_inventory_spine_joins(stmt):
    return (
        stmt.join(CatalogIssue, InventoryCopy.catalog_issue_id == CatalogIssue.id, isouter=True)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id, isouter=True)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
        .join(CatalogVariant, InventoryCopy.catalog_variant_id == CatalogVariant.id, isouter=True)
        .join(Acquisition, InventoryCopy.acquisition_id == Acquisition.id, isouter=True)
        .join(
            AcquisitionPlaceholderIssue,
            InventoryCopy.placeholder_issue_id == AcquisitionPlaceholderIssue.id,
            isouter=True,
        )
    )
