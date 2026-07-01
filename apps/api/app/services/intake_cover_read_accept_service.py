"""Accept a GPT cover-read identity: catalog link + GCD barcode contribution."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogSeries
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    MATCH_SOURCE_COVER_READ,
    MATCH_SOURCE_MANUAL,
    IntakeSessionItem,
)
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.gcd_catalog_import_dashboard_service import resolve_gcd_path
from app.services.gcd_user_barcode_contribution_service import contribute_barcode_to_gcd
from app.services.intake_queue_service import (
    _attach_intake_barcode_repair,
    _load_owned_item,
)
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.p106_barcode_gap_resolver_service import (
    auto_attach_gcd_identity_for_barcode,
    auto_import_gcd_issue_for_barcode,
)
from app.services.p105_barcode_repair_service import BarcodeAttachConflict, BarcodeAttachError
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)

MATCH_SOURCE_COVER_READ = "cover_read"


def _recovery_hints_from_item(item: IntakeSessionItem) -> dict[str, Any]:
    raw = item.barcode_read_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    gap = parsed.get("barcode_gap")
    if not isinstance(gap, dict):
        return {}
    hints = gap.get("recovery_hints")
    return hints if isinstance(hints, dict) else {}


def _find_catalog_issue_by_identity(
    session: Session,
    *,
    series: str,
    issue_number: str,
    publisher: str | None,
) -> int | None:
    series_norm = normalize_series_name(series)
    issue_norm = normalize_issue_number(issue_number)
    if not series_norm or not issue_norm:
        return None
    stmt = (
        select(CatalogIssue.id)
        .join(CatalogSeries, CatalogSeries.id == CatalogIssue.series_id)
        .where(CatalogIssue.normalized_issue_number == issue_norm)
        .where(CatalogSeries.name.ilike(f"%{series.strip()}%"))
        .order_by(CatalogIssue.id.desc())
        .limit(25)
    )
    pub_norm = normalize_series_name(publisher or "") if publisher else ""
    for issue_id in session.exec(stmt).all():
        if issue_id is None:
            continue
        identity = load_catalog_issue_identity(session, int(issue_id))
        if identity is None:
            continue
        cand_series = normalize_series_name(identity.series or "")
        if cand_series != series_norm and not series_names_compatible(cand_series, series_norm):
            continue
        if pub_norm:
            id_pub = normalize_series_name(identity.publisher or "")
            if id_pub and id_pub != pub_norm and not series_names_compatible(id_pub, pub_norm):
                continue
        return int(issue_id)
    return None


def _catalog_id_for_gcd_issue(session: Session, gcd_issue_id: int) -> int | None:
    for issue_id, ext in session.exec(
        select(CatalogIssue.id, CatalogIssue.external_source_ids)
    ).all():
        if issue_id is None:
            continue
        if extract_gcd_issue_id(ext) == int(gcd_issue_id):
            return int(issue_id)
    return None


def accept_intake_cover_read_identity(
    session: Session,
    *,
    item_id: int,
    owner_user_id: int,
) -> IntakeSessionItem:
    """User confirms the GPT cover-read identity; write GCD + link catalog + learn barcode."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    hints = _recovery_hints_from_item(item)
    if not hints.get("vision_cover_read_used"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cover-read identification available for this item.",
        )
    series = str(hints.get("series") or hints.get("ocr_title") or "").strip()
    issue_number = str(
        hints.get("displayed_issue_number") or hints.get("issue_number") or ""
    ).strip()
    publisher = str(hints.get("publisher") or hints.get("ocr_publisher") or "").strip() or None
    if not series or not issue_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cover-read identity is incomplete (series or issue missing).",
        )
    barcode = (item.normalized_barcode or "").strip()
    if not barcode:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Barcode is required to contribute a GCD mapping.",
        )

    facsimile = bool(hints.get("facsimile_or_reprint"))
    year_raw = hints.get("year")
    year: int | None = None
    if year_raw is not None:
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            year = None

    gcd_path = resolve_gcd_path(None)
    try:
        gcd_issue_id = contribute_barcode_to_gcd(
            gcd_path,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            barcode=barcode,
            title=series,
            year=year,
            facsimile=facsimile,
            intake_item_id=int(item.id or 0),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GCD database is not available on this server.",
        ) from exc
    except OSError as exc:
        logger.warning(
            "intake.cover_read.gcd_write_failed item_id=%s error=%s",
            item.id,
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not write to the GCD database (read-only or missing).",
        ) from exc

    catalog_issue_id = _catalog_id_for_gcd_issue(session, int(gcd_issue_id))
    if catalog_issue_id is None:
        catalog_issue_id = _find_catalog_issue_by_identity(
            session,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
        )
    if catalog_issue_id is None:
        try:
            result = auto_import_gcd_issue_for_barcode(
                session,
                barcode=barcode,
                gcd_issue_id=int(gcd_issue_id),
                gcd_path=gcd_path,
            )
            catalog_issue_id = int(result["catalog_issue_id"])
        except ValueError as exc:
            logger.warning(
                "intake.cover_read.catalog_import_failed item_id=%s gcd_issue_id=%s error=%s",
                item.id,
                gcd_issue_id,
                str(exc)[:200],
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    else:
        try:
            auto_attach_gcd_identity_for_barcode(
                session,
                catalog_issue_id=int(catalog_issue_id),
                gcd_issue_id=int(gcd_issue_id),
                barcode=barcode,
                gcd_path=gcd_path,
            )
        except ValueError as exc:
            logger.info(
                "intake.cover_read.gcd_attach_skipped item_id=%s catalog_issue_id=%s reason=%s",
                item.id,
                catalog_issue_id,
                str(exc)[:200],
            )

    identity = load_catalog_issue_identity(session, int(catalog_issue_id))
    item.selected_catalog_issue_id = int(catalog_issue_id)
    if identity is not None:
        item.matched_publisher = identity.publisher
        item.matched_series = identity.series
        item.matched_issue_number = identity.issue_number
        item.cover_url = identity.cover_image_url or item.cover_url
    else:
        item.matched_series = series
        item.matched_issue_number = issue_number
        item.matched_publisher = publisher
    item.match_source = MATCH_SOURCE_COVER_READ
    session.add(item)
    session.flush()

    skip_barcode_validation = facsimile or hints.get("barcode_issue_authoritative") is False
    try:
        _attach_intake_barcode_repair(
            session,
            item=item,
            catalog_issue_id=int(catalog_issue_id),
            variant_id=item.selected_variant_id,
            user_id=owner_user_id,
            learned_source=MATCH_SOURCE_MANUAL,
            require_catalog_validation=not skip_barcode_validation,
        )
    except BarcodeAttachConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except BarcodeAttachError as exc:
        if skip_barcode_validation:
            _attach_intake_barcode_repair(
                session,
                item=item,
                catalog_issue_id=int(catalog_issue_id),
                variant_id=item.selected_variant_id,
                user_id=owner_user_id,
                learned_source=MATCH_SOURCE_MANUAL,
                require_catalog_validation=False,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    item.status = ITEM_AUTO_MATCHED
    item.reason = "Cover identity confirmed — add to inventory when ready."
    session.add(item)
    session.commit()
    logger.info(
        "intake.cover_read.accepted item_id=%s gcd_issue_id=%s catalog_issue_id=%s barcode=%s",
        item.id,
        gcd_issue_id,
        catalog_issue_id,
        barcode,
    )
    session.refresh(item)
    return item
