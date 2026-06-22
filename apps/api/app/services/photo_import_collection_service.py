"""Create an owned inventory copy from a GPT read (legacy spine — retired for new writes).

Vision-read intake now uses :mod:`photo_import_acquisition_service` (catalog issue +
acquisition only). This module remains for reference and for environments that
explicitly re-enable legacy customer order writes.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    Variant,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead, utc_now
from app.services.catalog_issue_link_service import resolve_catalog_issue_link
from app.services.legacy_customer_orders_policy import assert_legacy_customer_order_writes_allowed

logger = logging.getLogger(__name__)

PHOTO_IMPORT_RETAILER = "Photo Import"
_UNKNOWN_PUBLISHER = "Unknown Publisher"
_UNKNOWN_SERIES = "Untitled Series"


def _get_or_create_publisher(session: Session, name: str) -> Publisher:
    clean = (name or "").strip() or _UNKNOWN_PUBLISHER
    existing = session.exec(select(Publisher).where(Publisher.name == clean)).first()
    if existing is not None:
        return existing
    publisher = Publisher(name=clean[:255])
    session.add(publisher)
    session.flush()
    return publisher


def _get_or_create_title(session: Session, *, publisher_id: int, name: str) -> ComicTitle:
    clean = (name or "").strip() or _UNKNOWN_SERIES
    existing = session.exec(
        select(ComicTitle)
        .where(ComicTitle.publisher_id == publisher_id)
        .where(ComicTitle.name == clean)
    ).first()
    if existing is not None:
        return existing
    title = ComicTitle(publisher_id=publisher_id, name=clean[:255])
    session.add(title)
    session.flush()
    return title


def _get_or_create_issue(session: Session, *, comic_title_id: int, issue_number: str) -> ComicIssue:
    clean = (issue_number or "").strip()
    existing = session.exec(
        select(ComicIssue)
        .where(ComicIssue.comic_title_id == comic_title_id)
        .where(ComicIssue.issue_number == clean)
    ).first()
    if existing is not None:
        return existing
    issue = ComicIssue(comic_title_id=comic_title_id, issue_number=clean[:50])
    session.add(issue)
    session.flush()
    return issue


def _get_or_create_default_variant(session: Session, *, comic_issue_id: int) -> Variant:
    existing = session.exec(
        select(Variant).where(Variant.comic_issue_id == comic_issue_id).order_by(Variant.id.asc())
    ).first()
    if existing is not None:
        return existing
    variant = Variant(comic_issue_id=comic_issue_id, cover_name="Cover A")
    session.add(variant)
    session.flush()
    return variant


def _get_or_create_photo_import_order(session: Session, *, owner_user_id: int) -> Order:
    existing = session.exec(
        select(Order)
        .where(Order.user_id == owner_user_id)
        .where(Order.retailer == PHOTO_IMPORT_RETAILER)
        .order_by(Order.id.asc())
    ).first()
    if existing is not None:
        return existing
    order = Order(
        user_id=owner_user_id,
        retailer=PHOTO_IMPORT_RETAILER,
        order_date=date.today(),
        source_type="photo_import",
        notes="Comics added from phone photo GPT reads.",
    )
    session.add(order)
    session.flush()
    return order


def create_owned_copy_from_vision_read(
    session: Session,
    *,
    read: PhotoImportVisionRead,
    owner_user_id: int,
    source_image_url: str | None = None,
) -> InventoryCopy:
    """Build legacy asset-ledger rows from a GPT read and return the new owned copy.

    The copy is marked received/in-hand so it shows in the Inventory grid and counts
    toward collection value. Caller is responsible for commit.
    """
    assert_legacy_customer_order_writes_allowed()
    publisher = _get_or_create_publisher(session, read.publisher or "")
    title = _get_or_create_title(
        session,
        publisher_id=int(publisher.id),
        name=read.series or read.issue_title or "",
    )
    issue = _get_or_create_issue(
        session,
        comic_title_id=int(title.id),
        issue_number=read.issue_number or "",
    )
    variant = _get_or_create_default_variant(session, comic_issue_id=int(issue.id))
    order = _get_or_create_photo_import_order(session, owner_user_id=owner_user_id)

    order_item = OrderItem(
        order_id=int(order.id),
        variant_id=int(variant.id),
        quantity=1,
        raw_item_price=Decimal("0"),
        all_in_unit_cost=Decimal("0"),
    )
    session.add(order_item)
    session.flush()

    # Prefer the catalog match already chosen for this read (barcode/text/manual);
    # otherwise fall back to resolving from the free-text fields.
    catalog_issue_id = read.catalog_issue_id
    catalog_variant_id = read.catalog_variant_id
    if catalog_issue_id is None:
        link = resolve_catalog_issue_link(
            session,
            series=read.series,
            issue_number=read.issue_number,
            publisher=read.publisher,
            barcode=read.barcode,
        )
        catalog_issue_id = link.catalog_issue_id
        catalog_variant_id = link.catalog_variant_id

    copy = InventoryCopy(
        user_id=owner_user_id,
        order_item_id=int(order_item.id),
        variant_id=int(variant.id),
        copy_number=1,
        acquisition_cost=Decimal("0"),
        order_status="received",
        received_at=utc_now(),
        received_via="PHOTO_IMPORT",
        source_image_url=source_image_url,
        catalog_issue_id=catalog_issue_id,
        catalog_variant_id=catalog_variant_id,
    )
    session.add(copy)
    session.flush()
    logger.info(
        "photo_import.collection.owned_copy_created copy_id=%s variant_id=%s issue=%r series=%r",
        copy.id,
        variant.id,
        issue.issue_number,
        title.name,
    )
    return copy
