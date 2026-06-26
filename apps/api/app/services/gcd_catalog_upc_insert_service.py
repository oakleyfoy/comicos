"""Shared GCD catalog UPC insertion for P102/P103 write batches."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.services.catalog_ingestion_service import normalize_upc
from app.services.gcd_barcode_import_service import GCD_SOURCE

logger = logging.getLogger(__name__)


def _lookup_catalog_upc(session: Session, normalized: str) -> CatalogUpc | None:
    return session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()


def insert_catalog_upc_if_absent(
    session: Session,
    *,
    raw_upc: str,
    issue_id: int,
    variant_id: int | None,
    learned: set[str],
    upc_map: dict[str, int],
) -> tuple[int | None, bool]:
    """
    Insert a catalog UPC when absent.

    Returns (upc_id, created). ``created`` is True only when a new row was inserted.
    Never raises IntegrityError for duplicate normalized_upc; returns existing id when
    the UPC is already on the same issue_id.
    """
    normalized = normalize_upc(raw_upc)
    if not normalized:
        return None, False

    if normalized in learned:
        return None, False

    mapped_issue = upc_map.get(normalized)
    if mapped_issue is not None:
        if int(mapped_issue) != int(issue_id):
            return None, False
        existing = _lookup_catalog_upc(session, normalized)
        if existing is not None and existing.id is not None:
            return int(existing.id), False
        return None, False

    existing = _lookup_catalog_upc(session, normalized)
    if existing is not None:
        existing_issue = int(existing.issue_id or 0)
        upc_map[normalized] = existing_issue
        if existing_issue != int(issue_id):
            return None, False
        if existing.id is not None:
            return int(existing.id), False
        return None, False

    row = CatalogUpc(
        upc=raw_upc.strip(),
        normalized_upc=normalized,
        issue_id=issue_id,
        variant_id=variant_id,
        source=GCD_SOURCE,
        confidence=Decimal("1.0"),
        barcode_type="upc",
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
        upc_map[normalized] = int(issue_id)
        return (int(row.id) if row.id is not None else None), True
    except IntegrityError:
        logger.debug(
            "gcd_catalog_upc_insert duplicate normalized_upc=%s issue_id=%s; re-querying",
            normalized,
            issue_id,
        )
        existing = _lookup_catalog_upc(session, normalized)
        if existing is None or existing.id is None:
            return None, False
        existing_issue = int(existing.issue_id or 0)
        upc_map[normalized] = existing_issue
        if existing_issue != int(issue_id):
            return None, False
        return int(existing.id), False
