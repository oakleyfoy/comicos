"""Backfill catalog_issue_id onto existing inventory copies (unification Phase 3).

Walks inventory copies that are not yet linked to the master catalog, resolves
their identity (legacy spine or stored metadata key), and attempts a confident
catalog match (UPC then scored text). Idempotent and supports a dry run so the
operator can review the match/miss report before committing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import InventoryCopy, Order, OrderItem
from app.services.canonical_inventory_identity_service import resolve_identity_for_copy
from app.services.catalog_issue_link_service import resolve_catalog_issue_link

logger = logging.getLogger(__name__)


@dataclass
class BackfillReport:
    scanned: int = 0
    already_linked: int = 0
    matched: int = 0
    unmatched: int = 0
    by_method: dict[str, int] = field(default_factory=dict)
    unmatched_samples: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "already_linked": self.already_linked,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "by_method": self.by_method,
            "unmatched_samples": self.unmatched_samples,
        }


def backfill_catalog_links(
    session: Session,
    *,
    dry_run: bool = True,
    user_id: int | None = None,
    sample_limit: int = 25,
) -> BackfillReport:
    report = BackfillReport()
    stmt = select(InventoryCopy)
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    copies = list(session.exec(stmt).all())

    for copy in copies:
        report.scanned += 1
        if copy.catalog_issue_id is not None:
            report.already_linked += 1
            continue

        identity = resolve_identity_for_copy(session, copy)
        link = resolve_catalog_issue_link(
            session,
            series=identity.title if identity.title != "Unknown" else None,
            issue_number=identity.issue_number or None,
            publisher=identity.publisher,
        )
        if link.catalog_issue_id is None:
            report.unmatched += 1
            if len(report.unmatched_samples) < sample_limit:
                report.unmatched_samples.append(
                    {
                        "inventory_copy_id": int(copy.id or 0),
                        "title": identity.title,
                        "issue_number": identity.issue_number,
                        "publisher": identity.publisher,
                        "source": identity.source,
                    }
                )
            continue

        report.matched += 1
        report.by_method[link.method] = report.by_method.get(link.method, 0) + 1
        if not dry_run:
            copy.catalog_issue_id = link.catalog_issue_id
            if link.catalog_variant_id is not None:
                copy.catalog_variant_id = link.catalog_variant_id
            session.add(copy)

    if not dry_run:
        session.commit()
    logger.info(
        "catalog_backfill dry_run=%s scanned=%s matched=%s unmatched=%s already=%s",
        dry_run,
        report.scanned,
        report.matched,
        report.unmatched,
        report.already_linked,
    )
    return report


@dataclass
class ProvenanceReport:
    scanned: int = 0
    snapshotted: int = 0
    skipped_no_order: int = 0
    already_snapshotted: int = 0

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "snapshotted": self.snapshotted,
            "skipped_no_order": self.skipped_no_order,
            "already_snapshotted": self.already_snapshotted,
        }


def snapshot_order_provenance_for_copy(
    session: Session, copy: InventoryCopy
) -> bool:
    """Copy financial provenance from the legacy order graph onto the copy.

    Returns True if anything was written. Idempotent: a copy that already has a
    retailer snapshot is left untouched.
    """
    if copy.order_item_id is None:
        return False
    if copy.order_retailer is not None or copy.order_date is not None:
        return False
    order_item = session.get(OrderItem, copy.order_item_id)
    if order_item is None:
        return False
    order = session.get(Order, order_item.order_id) if order_item.order_id is not None else None

    copy.order_raw_item_price = order_item.raw_item_price
    copy.order_shipping_paid = order_item.allocated_shipping
    copy.order_tax_paid = order_item.allocated_tax
    if order is not None:
        copy.order_retailer = order.retailer
        copy.order_date = order.order_date
        copy.order_source_type = order.source_type
    session.add(copy)
    return True


def backfill_order_provenance(
    session: Session,
    *,
    dry_run: bool = True,
    user_id: int | None = None,
) -> ProvenanceReport:
    report = ProvenanceReport()
    stmt = select(InventoryCopy)
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    for copy in session.exec(stmt).all():
        report.scanned += 1
        if copy.order_item_id is None:
            report.skipped_no_order += 1
            continue
        if copy.order_retailer is not None or copy.order_date is not None:
            report.already_snapshotted += 1
            continue
        if dry_run:
            # Count what would be written without mutating.
            report.snapshotted += 1
            continue
        if snapshot_order_provenance_for_copy(session, copy):
            report.snapshotted += 1

    if not dry_run:
        session.commit()
    logger.info(
        "order_provenance dry_run=%s scanned=%s snapshotted=%s skipped=%s already=%s",
        dry_run,
        report.scanned,
        report.snapshotted,
        report.skipped_no_order,
        report.already_snapshotted,
    )
    return report
