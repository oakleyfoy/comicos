"""Attach full UPC+5 barcodes to catalog issues (learned map + catalog_upc when safe)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.models.intake_queue import (
    MATCH_SOURCE_LEARNED,
    MATCH_SOURCE_MANUAL,
    ComicIssueBarcode,
    IntakeSessionItem,
)
from app.models.p105_barcode_repair import (
    P105MissingBarcodeQueue,
    P105_QUEUE_CONFLICT,
    P105_QUEUE_PENDING,
    P105_QUEUE_RESOLVED,
    utc_now,
)
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    effective_publisher_for_barcode,
    validate_barcode_catalog_match,
)
from app.services.barcode_scan_consensus_service import validate_single_barcode_read
from app.services.catalog_ingestion_service import (
    direct_market_requires_supplement_key,
    normalize_upc,
)
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)

CATALOG_UPC_SOURCE_MANUAL = "manual"
CATALOG_UPC_SOURCE_LEARNED = "learned"


class BarcodeAttachError(Exception):
    """User-visible attach failure."""


class BarcodeAttachConflict(BarcodeAttachError):
    """UPC already mapped to a different catalog issue."""


@dataclass(frozen=True)
class BarcodeAttachPreview:
    normalized_barcode: str
    catalog_issue_id: int
    series: str
    issue_number: str
    publisher: str | None
    validation_status: str
    validation_detail: str
    will_create_catalog_upc: bool
    will_create_learned: bool


@dataclass
class BarcodeAttachResult:
    normalized_barcode: str
    catalog_issue_id: int
    catalog_upc_id: int | None
    catalog_upc_created: bool
    learned_barcode_id: int | None
    learned_created: bool


def require_full_direct_market_barcode(normalized: str) -> str:
    """Reject base-only direct-market UPCs for high-confidence attach."""
    digits = normalize_upc(normalized)
    if not digits:
        raise BarcodeAttachError("Barcode is empty.")
    scan = validate_single_barcode_read(digits)
    if scan.acceptance == "rejected_checksum":
        raise BarcodeAttachError("UPC/EAN check digit failed.")
    normalized = scan.normalized or digits
    if direct_market_requires_supplement_key(normalized) and len(normalized) < 17:
        raise BarcodeAttachError(
            "Base UPC only cannot be attached as high-confidence; need full UPC+5."
        )
    return normalized


def preview_barcode_attach(
    session: Session,
    *,
    barcode: str,
    catalog_issue_id: int,
    variant_id: int | None = None,
) -> BarcodeAttachPreview:
    normalized = require_full_direct_market_barcode(barcode)
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        raise BarcodeAttachError(f"Catalog issue #{catalog_issue_id} not found.")
    year = ""
    from app.models.catalog_master import CatalogIssue

    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is not None and issue.cover_date is not None:
        year = str(issue.cover_date.year)
    validation = validate_barcode_catalog_match(
        normalized,
        publisher=identity.publisher,
        issue_number=identity.issue_number,
        year=year,
    )
    existing_upc = session.exec(
        select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)
    ).first()
    existing_learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized)
    ).first()
    will_catalog = validation.status == "exact_match" and (
        existing_upc is None or int(existing_upc.issue_id or 0) == int(catalog_issue_id)
    )
    will_learned = existing_learned is None or int(existing_learned.catalog_issue_id) == int(
        catalog_issue_id
    )
    return BarcodeAttachPreview(
        normalized_barcode=normalized,
        catalog_issue_id=int(catalog_issue_id),
        series=identity.series,
        issue_number=identity.issue_number,
        publisher=identity.publisher,
        validation_status=validation.status,
        validation_detail=validation.reason,
        will_create_catalog_upc=will_catalog and existing_upc is None,
        will_create_learned=will_learned and existing_learned is None,
    )


def _assert_no_cross_issue_conflict(
    session: Session,
    *,
    normalized: str,
    catalog_issue_id: int,
) -> None:
    upc_row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if upc_row is not None and upc_row.issue_id is not None:
        if int(upc_row.issue_id) != int(catalog_issue_id):
            raise BarcodeAttachConflict(
                f"catalog_upc already maps {normalized} to issue #{upc_row.issue_id}, "
                f"not #{catalog_issue_id}."
            )
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized)
    ).first()
    if learned is not None and int(learned.catalog_issue_id) != int(catalog_issue_id):
        raise BarcodeAttachConflict(
            f"learned barcode already maps {normalized} to issue #{learned.catalog_issue_id}, "
            f"not #{catalog_issue_id}."
        )


def attach_barcode_to_catalog_issue(
    session: Session,
    *,
    barcode: str,
    catalog_issue_id: int,
    variant_id: int | None = None,
    user_id: int | None = None,
    learned_source: str = MATCH_SOURCE_MANUAL,
    catalog_upc_source: str = CATALOG_UPC_SOURCE_MANUAL,
    require_catalog_validation: bool = True,
) -> BarcodeAttachResult:
    normalized = require_full_direct_market_barcode(barcode)
    _assert_no_cross_issue_conflict(session, normalized=normalized, catalog_issue_id=catalog_issue_id)

    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        raise BarcodeAttachError(f"Catalog issue #{catalog_issue_id} not found.")

    from app.models.catalog_master import CatalogIssue

    issue = session.get(CatalogIssue, catalog_issue_id)
    year = str(issue.cover_date.year) if issue is not None and issue.cover_date else ""
    validation = validate_barcode_catalog_match(
        normalized,
        publisher=identity.publisher,
        issue_number=identity.issue_number,
        year=year,
    )
    if require_catalog_validation and validation.status != "exact_match":
        raise BarcodeAttachError(validation.reason)

    catalog_upc_id: int | None = None
    catalog_created = False
    upc_row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if validation.status == "exact_match":
        if upc_row is None:
            row = CatalogUpc(
                upc=normalized,
                normalized_upc=normalized,
                issue_id=int(catalog_issue_id),
                variant_id=variant_id,
                source=catalog_upc_source,
                confidence=Decimal("1.0"),
                barcode_type="upc",
            )
            session.add(row)
            session.flush()
            catalog_upc_id = int(row.id) if row.id is not None else None
            catalog_created = True
        else:
            catalog_upc_id = int(upc_row.id) if upc_row.id is not None else None

    learned_id: int | None = None
    learned_created = False
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized)
    ).first()
    if learned is None:
        learned = ComicIssueBarcode(
            normalized_barcode=normalized,
            catalog_issue_id=int(catalog_issue_id),
            variant_id=variant_id,
            source=learned_source,
            confirmed_by_user_id=user_id,
        )
        session.add(learned)
        session.flush()
        learned_id = int(learned.id) if learned.id is not None else None
        learned_created = True
    else:
        learned.catalog_issue_id = int(catalog_issue_id)
        learned.variant_id = variant_id
        learned.source = learned_source
        if user_id is not None:
            learned.confirmed_by_user_id = user_id
        learned.times_seen += 1
        learned.updated_at = utc_now()
        session.add(learned)
        session.flush()
        learned_id = int(learned.id) if learned.id is not None else None

    return BarcodeAttachResult(
        normalized_barcode=normalized,
        catalog_issue_id=int(catalog_issue_id),
        catalog_upc_id=catalog_upc_id,
        catalog_upc_created=catalog_created,
        learned_barcode_id=learned_id,
        learned_created=learned_created,
    )


def record_missing_barcode_queue(session: Session, *, item: IntakeSessionItem) -> None:
    """Enqueue intake items with full UPC+5 that did not resolve in catalog_upc."""
    normalized = (item.normalized_barcode or "").strip()
    if not normalized:
        return
    try:
        normalized = require_full_direct_market_barcode(normalized)
    except BarcodeAttachError:
        return

    encoded = barcode_encoded_issue_number(normalized)
    issue_from_supp = str(encoded) if encoded is not None else None
    publisher = effective_publisher_for_barcode(normalized, item.matched_publisher)

    row = session.exec(
        select(P105MissingBarcodeQueue)
        .where(P105MissingBarcodeQueue.barcode == normalized)
        .where(P105MissingBarcodeQueue.intake_item_id == int(item.id or 0))
    ).first()
    if row is None:
        row = P105MissingBarcodeQueue(
            barcode=normalized,
            publisher_guess=publisher,
            issue_number_from_supplement=issue_from_supp,
            intake_item_id=int(item.id) if item.id is not None else None,
            status=P105_QUEUE_PENDING,
        )
    else:
        row.publisher_guess = publisher
        row.issue_number_from_supplement = issue_from_supp
        row.status = P105_QUEUE_PENDING
        row.updated_at = utc_now()
    session.add(row)


def resolve_missing_barcode_queue(
    session: Session,
    *,
    barcode: str,
    catalog_issue_id: int,
    intake_item_id: int | None,
    attach: BarcodeAttachResult,
) -> None:
    normalized = normalize_upc(barcode)
    query = select(P105MissingBarcodeQueue).where(P105MissingBarcodeQueue.barcode == normalized)
    if intake_item_id is not None:
        query = query.where(P105MissingBarcodeQueue.intake_item_id == intake_item_id)
    rows = list(session.exec(query).all())
    if not rows:
        return
    for row in rows:
        row.status = P105_QUEUE_RESOLVED
        row.chosen_catalog_issue_id = int(catalog_issue_id)
        row.created_catalog_upc_id = attach.catalog_upc_id
        row.created_learned_barcode_id = attach.learned_barcode_id
        row.updated_at = utc_now()
        session.add(row)


def mark_missing_barcode_queue_conflict(
    session: Session,
    *,
    barcode: str,
    intake_item_id: int | None,
) -> None:
    normalized = normalize_upc(barcode)
    query = select(P105MissingBarcodeQueue).where(P105MissingBarcodeQueue.barcode == normalized)
    if intake_item_id is not None:
        query = query.where(P105MissingBarcodeQueue.intake_item_id == intake_item_id)
    for row in session.exec(query).all():
        row.status = P105_QUEUE_CONFLICT
        row.updated_at = utc_now()
        session.add(row)


def intake_repair_learned_source(match_source: str | None) -> str:
    if match_source in {MATCH_SOURCE_LEARNED, MATCH_SOURCE_MANUAL}:
        return match_source or MATCH_SOURCE_MANUAL
    return MATCH_SOURCE_LEARNED
