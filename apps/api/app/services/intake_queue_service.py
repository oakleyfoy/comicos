"""Async intake queue service: hands-free capture, counts, and review actions.

Capture is non-blocking: each enqueue saves the image, creates a ``queued`` item, kicks a
background worker, and returns immediately. Identification/inventory happen separately.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, func, select

from app.models import Acquisition, CatalogIssue
from app.models.acquisition import ACQUISITION_TYPE_OTHER
from app.models.intake_queue import (
    ComicIssueBarcode,
    INTAKE_SESSION_ACTIVE,
    INTAKE_SESSION_EXPIRED,
    INTAKE_SESSION_PAUSED,
    INTAKE_SESSION_STOPPED,
    ITEM_ADDED_TO_INVENTORY,
    ITEM_AUTO_MATCHED,
    ITEM_FAILED,
    ITEM_NEEDS_REVIEW,
    ITEM_PROCESSING,
    ITEM_QUEUED,
    ITEM_READY_FOR_REVIEW,
    ITEM_REJECTED,
    IntakeItemCandidate,
    IntakeSession,
    IntakeSessionItem,
    MATCH_SOURCE_MANUAL,
    utc_now,
)
from app.schemas.acquisition import AcquisitionCreatePayload
from app.services.acquisition.acquisition_inventory_service import create_received_catalog_copy
from app.services.acquisition.acquisition_service import (
    create_acquisition,
    get_acquisition_or_404,
    recompute_actual_book_count,
    require_open,
)
from app.services.barcode_scan_consensus_service import validate_single_barcode_read
from app.services.intake_worker_service import (
    SUSPICIOUS_MIN_IMAGE_BYTES,
    recognition_image_too_small,
    run_intake_item_async,
)
from app.services.photo_import_storage_service import (
    REPO_ROOT,
    relative_path_under_repo_root,
)
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)

INTAKE_TTL_HOURS = 12
MAX_FILE_BYTES = 15 * 1024 * 1024

HIGH_CONFIDENCE_STATUSES = {ITEM_AUTO_MATCHED}


# --- storage ---
def _intake_storage_dir(*, user_id: int, session_id: int) -> Path:
    path = REPO_ROOT / "data" / "intake" / str(user_id) / str(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- session lifecycle ---
def create_intake_session(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    source_device: str | None = None,
    name: str | None = None,
) -> IntakeSession:
    acq = get_acquisition_or_404(
        session, owner_user_id=owner_user_id, acquisition_id=acquisition_id
    )
    require_open(acq)
    now = utc_now()
    row = IntakeSession(
        user_id=owner_user_id,
        session_token=secrets.token_urlsafe(32),
        name=name,
        status=INTAKE_SESSION_ACTIVE,
        source_device=source_device,
        acquisition_id=int(acq.id or 0),
        created_at=now,
        expires_at=now + timedelta(hours=INTAKE_TTL_HOURS),
        last_seen_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _expire_stale(row: IntakeSession) -> None:
    if row.status in {INTAKE_SESSION_STOPPED, INTAKE_SESSION_EXPIRED}:
        return
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        row.status = INTAKE_SESSION_EXPIRED


def get_intake_session_by_token_or_404(session: Session, *, token: str) -> IntakeSession:
    row = session.exec(select(IntakeSession).where(IntakeSession.session_token == token)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake session not found")
    _expire_stale(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def assert_owner(row: IntakeSession, *, owner_user_id: int) -> None:
    if int(row.user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your intake session")


def set_session_status(session: Session, *, token: str, new_status: str) -> IntakeSession:
    row = get_intake_session_by_token_or_404(session, token=token)
    if new_status not in {INTAKE_SESSION_ACTIVE, INTAKE_SESSION_PAUSED, INTAKE_SESSION_STOPPED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session status")
    row.status = new_status
    row.last_seen_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# --- capture (non-blocking enqueue) ---
async def enqueue_intake_item(
    session: Session,
    *,
    token: str,
    upload: UploadFile,
    raw_barcode: str | None = None,
    frame_uploads: list[UploadFile] | None = None,
) -> IntakeSessionItem:
    row = get_intake_session_by_token_or_404(session, token=token)
    if row.status == INTAKE_SESSION_STOPPED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is stopped")

    if not upload.content_type or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are allowed")
    raw = await upload.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large")

    ext = Path(upload.filename or "scan.jpg").suffix or ".jpg"
    dest_dir = _intake_storage_dir(user_id=int(row.user_id), session_id=int(row.id or 0))
    file_stem = uuid.uuid4().hex
    dest_path = dest_dir / f"{file_stem}{ext}"
    dest_path.write_bytes(raw)

    frame_count = 0
    for idx, frame_upload in enumerate(frame_uploads or []):
        if frame_count >= 8:
            break
        if not frame_upload.content_type or not frame_upload.content_type.startswith("image/"):
            continue
        frame_raw = await frame_upload.read()
        if len(frame_raw) > MAX_FILE_BYTES:
            continue
        frame_path = dest_dir / f"{file_stem}_f{idx}{ext}"
        frame_path.write_bytes(frame_raw)
        frame_count += 1
    if frame_count:
        logger.info(
            "intake.enqueue.supplement_frames session=%s primary=%s frames=%s",
            row.id,
            dest_path.name,
            frame_count,
        )

    too_small, img_w, img_h, small_reason = recognition_image_too_small(raw)
    logger.info(
        "intake.enqueue.image session=%s bytes=%s width=%s height=%s stored_path=%s too_small=%s",
        row.id,
        len(raw),
        img_w,
        img_h,
        relative_path_under_repo_root(dest_path),
        too_small,
    )
    if len(raw) < SUSPICIOUS_MIN_IMAGE_BYTES:
        logger.warning(
            "intake.enqueue.suspicious_small_bytes session=%s bytes=%s width=%s height=%s",
            row.id,
            len(raw),
            img_w,
            img_h,
        )

    validation = None
    normalized = None
    raw_stored = (raw_barcode or "").strip()
    if raw_stored:
        validation = validate_single_barcode_read(raw_stored)
        if validation.acceptance == "rejected_checksum":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation.reason,
            )
        if validation.acceptance == "accepted":
            normalized = validation.normalized
            raw_stored = validation.raw_scan
    item = IntakeSessionItem(
        session_id=int(row.id or 0),
        user_id=int(row.user_id),
        storage_path=relative_path_under_repo_root(dest_path),
        mime_type=upload.content_type or "image/jpeg",
        file_size=len(raw),
        raw_barcode=raw_stored[:64] if raw_stored else None,
        normalized_barcode=(normalized[:64] if normalized else None),
        base_upc=(validation.base_upc[:16] if validation and validation.acceptance == "accepted" else None),
        extension=((validation.extension or None) if validation and validation.acceptance == "accepted" else None),
        status=ITEM_FAILED if too_small else ITEM_QUEUED,
    )
    if too_small:
        item.error = small_reason
        item.processed_at = utc_now()
    session.add(item)
    row.scanned_count = int(row.scanned_count) + 1
    row.last_seen_at = utc_now()
    if row.status == INTAKE_SESSION_PAUSED:
        row.status = INTAKE_SESSION_ACTIVE
    session.add(row)
    session.commit()
    session.refresh(item)

    if too_small:
        # Thumbnail-sized capture: flagged failed up front, never enters recognition.
        logger.warning(
            "intake.enqueue.rejected_small item_id=%s session=%s width=%s height=%s bytes=%s",
            item.id,
            row.id,
            img_w,
            img_h,
            len(raw),
        )
        return item

    # Kick the background worker; the scanner does not wait for this.
    run_intake_item_async(int(item.id or 0))
    logger.info("intake.enqueue item_id=%s session=%s scanned=%s", item.id, row.id, row.scanned_count)
    return item


# --- counts + listing ---
def intake_counts(session: Session, *, session_id: int) -> dict[str, int]:
    rows = session.exec(
        select(IntakeSessionItem.status, func.count(IntakeSessionItem.id))
        .where(IntakeSessionItem.session_id == session_id)
        .group_by(IntakeSessionItem.status)
    ).all()
    by_status = {str(s): int(c) for s, c in rows}
    queued = by_status.get(ITEM_QUEUED, 0)
    processing = by_status.get(ITEM_PROCESSING, 0)
    auto_matched = by_status.get(ITEM_AUTO_MATCHED, 0)
    ready = by_status.get(ITEM_READY_FOR_REVIEW, 0)
    needs = by_status.get(ITEM_NEEDS_REVIEW, 0)
    added = by_status.get(ITEM_ADDED_TO_INVENTORY, 0)
    rejected = by_status.get(ITEM_REJECTED, 0)
    failed = by_status.get("failed", 0)
    total = sum(by_status.values())
    return {
        "scanned": total,
        "queued": queued,
        "processing": processing,
        "auto_matched": auto_matched,
        "ready_for_review": ready,
        "needs_review": needs,
        "added_to_inventory": added,
        "rejected": rejected,
        "failed": failed,
    }


def list_intake_items(
    session: Session,
    *,
    session_id: int,
    status_filter: str | None = None,
    limit: int = 200,
) -> list[IntakeSessionItem]:
    query = select(IntakeSessionItem).where(IntakeSessionItem.session_id == session_id)
    if status_filter:
        query = query.where(IntakeSessionItem.status == status_filter)
    query = query.order_by(IntakeSessionItem.id.desc()).limit(max(1, min(int(limit), 500)))
    return list(session.exec(query).all())


def candidates_for_item(session: Session, *, item_id: int) -> list[IntakeItemCandidate]:
    return list(
        session.exec(
            select(IntakeItemCandidate)
            .where(IntakeItemCandidate.item_id == item_id)
            .order_by(IntakeItemCandidate.rank.asc())
        ).all()
    )


# --- review actions ---
def _load_owned_item(session: Session, *, item_id: int, owner_user_id: int) -> IntakeSessionItem:
    item = session.get(IntakeSessionItem, item_id)
    if item is None or int(item.user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake item not found")
    return item


def _learn_barcode(
    session: Session,
    *,
    normalized_barcode: str | None,
    catalog_issue_id: int,
    variant_id: int | None,
    source: str,
    user_id: int,
) -> None:
    """Upsert the barcode -> issue mapping so future scans match instantly."""
    if not normalized_barcode:
        return
    existing = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized_barcode)
    ).first()
    if existing is not None:
        existing.catalog_issue_id = catalog_issue_id
        existing.variant_id = variant_id
        existing.times_seen += 1
        existing.updated_at = utc_now()
        session.add(existing)
        return
    session.add(
        ComicIssueBarcode(
            normalized_barcode=normalized_barcode,
            catalog_issue_id=catalog_issue_id,
            variant_id=variant_id,
            source=source,
            confirmed_by_user_id=user_id,
        )
    )


def accept_intake_item(session: Session, *, item_id: int, owner_user_id: int) -> IntakeSessionItem:
    """Confirm the current match and learn the barcode mapping for instant future scans."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    if item.selected_catalog_issue_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No catalog match selected; choose an issue first.",
        )
    _learn_barcode(
        session,
        normalized_barcode=item.normalized_barcode,
        catalog_issue_id=int(item.selected_catalog_issue_id),
        variant_id=item.selected_variant_id,
        source=item.match_source or MATCH_SOURCE_MANUAL,
        user_id=owner_user_id,
    )
    item.status = ITEM_AUTO_MATCHED
    item.confidence = max(item.confidence, 0.99)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def choose_intake_item_issue(
    session: Session,
    *,
    item_id: int,
    owner_user_id: int,
    catalog_issue_id: int,
    variant_id: int | None = None,
) -> IntakeSessionItem:
    """Pick a catalog issue for an item: confirms the match and learns the barcode mapping."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found")
    item.selected_catalog_issue_id = catalog_issue_id
    item.selected_variant_id = variant_id
    item.matched_publisher = identity.publisher
    item.matched_series = identity.series
    item.matched_issue_number = identity.issue_number
    item.cover_url = identity.cover_image_url
    item.match_source = MATCH_SOURCE_MANUAL
    # Manual pick is a confirmation: learn the barcode and mark accepted so it can be added.
    _learn_barcode(
        session,
        normalized_barcode=item.normalized_barcode,
        catalog_issue_id=catalog_issue_id,
        variant_id=variant_id,
        source=MATCH_SOURCE_MANUAL,
        user_id=owner_user_id,
    )
    item.status = ITEM_AUTO_MATCHED
    item.confidence = max(item.confidence, 0.99)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def search_catalog_issues(
    session: Session,
    *,
    query: str,
    issue_number: str | None = None,
    limit: int = 25,
) -> list[dict[str, object]]:
    """Lightweight catalog issue search for the manual issue picker."""
    from app.models.catalog_master import CatalogSeries
    from app.services.catalog_ingestion_service import normalize_issue_number

    q = (query or "").strip()
    if not q:
        return []
    stmt = (
        select(CatalogIssue.id)
        .join(CatalogSeries, CatalogSeries.id == CatalogIssue.series_id)
        .where(CatalogSeries.name.ilike(f"%{q}%"))
    )
    if issue_number and issue_number.strip():
        stmt = stmt.where(CatalogIssue.normalized_issue_number == normalize_issue_number(issue_number))
    stmt = stmt.order_by(CatalogIssue.id.desc()).limit(max(1, min(int(limit), 50)))
    issue_ids = [int(i) for i in session.exec(stmt).all()]

    results: list[dict[str, object]] = []
    for issue_id in issue_ids:
        identity = load_catalog_issue_identity(session, issue_id)
        if identity is None:
            continue
        results.append(
            {
                "catalog_issue_id": issue_id,
                "series": identity.series,
                "issue_number": identity.issue_number,
                "publisher": identity.publisher,
                "cover_url": identity.cover_image_url,
            }
        )
    return results


def _parse_year(value: str | None) -> int | None:
    import re

    match = re.search(r"(18|19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def _find_comicvine_volume_for_item(importer, item: IntakeSessionItem) -> int | None:
    from app.services.photo_import_comicvine_ondemand_service import select_comicvine_volume_id

    # Barcode-first: the supplement-bearing UPC usually resolves a single volume.
    if item.normalized_barcode:
        try:
            rows = importer.search_issues_by_barcode(item.normalized_barcode)
            for row in rows:
                vid = importer.volume_id_from_issue_api_row(row)
                if vid is not None:
                    return int(vid)
        except Exception:
            logger.warning("intake.import.barcode_search_failed item_id=%s", item.id, exc_info=True)

    series = (item.matched_series or "").strip()
    if not series:
        return None
    issue_number = (item.matched_issue_number or "").strip()
    year = _parse_year(item.matched_year)
    publisher = (item.matched_publisher or "").strip()
    queries = [series] + ([f"{series} {publisher}"] if publisher else [])
    seen: set[str] = set()
    for query in queries:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            candidates = importer.search_volumes(query, limit=30)
        except Exception:
            logger.warning("intake.import.volume_search_failed item_id=%s query=%r", item.id, query, exc_info=True)
            continue
        vid = select_comicvine_volume_id(
            candidates, series=series, issue_number=issue_number, year=year
        )
        if vid is not None:
            return int(vid)
    return None


def _resolve_imported_issue_id(
    session: Session,
    *,
    normalized_barcode: str | None,
    catalog_series_id: int | None,
    issue_number: str | None,
) -> tuple[int | None, int | None]:
    from app.models.catalog_master import CatalogUpc
    from app.services.catalog_ingestion_service import (
        comic_barcode_lookup_keys_for_search,
        normalize_issue_number,
    )

    if normalized_barcode:
        for key in comic_barcode_lookup_keys_for_search(normalized_barcode):
            row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).first()
            if row is not None and row.issue_id is not None:
                return int(row.issue_id), (int(row.variant_id) if row.variant_id is not None else None)

    if catalog_series_id is not None and (issue_number or "").strip():
        norm = normalize_issue_number(issue_number or "")
        issue = session.exec(
            select(CatalogIssue).where(
                CatalogIssue.series_id == catalog_series_id,
                CatalogIssue.normalized_issue_number == norm,
            )
        ).first()
        if issue is not None and issue.id is not None:
            return int(issue.id), None
    return None, None


def import_and_accept_intake_item(
    session: Session, *, item_id: int, owner_user_id: int
) -> IntakeSessionItem:
    """Import the ComicVine volume/issue into the local catalog, link it, accept, and learn the barcode."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    if item.selected_catalog_issue_id is not None:
        # Already resolvable locally — just confirm it.
        return accept_intake_item(session, item_id=item_id, owner_user_id=owner_user_id)

    from app.services.catalog_ingestion_service import catalog_series_id_for_comicvine_volume
    from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

    importer = ComicVineCatalogImporter()
    if importer.initialize_or_explain():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ComicVine is not configured on this server.",
        )

    volume_id = _find_comicvine_volume_for_item(importer, item)
    if volume_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not find this book on ComicVine. Use “Choose different issue”.",
        )

    try:
        stats = importer.import_single_volume(session, comicvine_volume_id=volume_id, import_issues=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("intake.import.failed item_id=%s volume_id=%s", item.id, volume_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ComicVine import failed. Try again or choose the issue manually.",
        ) from exc

    catalog_series_id = catalog_series_id_for_comicvine_volume(
        session,
        volume_id=volume_id,
        publisher_id=None,
        prefer_start_year=_parse_year(item.matched_year),
    )
    if catalog_series_id is None and stats.imported_series_ids:
        catalog_series_id = int(stats.imported_series_ids[0])

    issue_id, variant_id = _resolve_imported_issue_id(
        session,
        normalized_barcode=item.normalized_barcode,
        catalog_series_id=catalog_series_id,
        issue_number=item.matched_issue_number,
    )
    if issue_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Imported from ComicVine but could not resolve the exact issue. Use “Choose different issue”.",
        )

    identity = load_catalog_issue_identity(session, issue_id)
    item.selected_catalog_issue_id = issue_id
    item.selected_variant_id = variant_id
    if identity is not None:
        item.matched_publisher = identity.publisher
        item.matched_series = identity.series
        item.matched_issue_number = identity.issue_number
        item.cover_url = identity.cover_image_url or item.cover_url
    item.match_source = "comicvine"
    _learn_barcode(
        session,
        normalized_barcode=item.normalized_barcode,
        catalog_issue_id=issue_id,
        variant_id=variant_id,
        source="comicvine",
        user_id=owner_user_id,
    )
    item.status = ITEM_AUTO_MATCHED
    item.confidence = max(item.confidence, 0.95)
    session.add(item)
    session.commit()
    session.refresh(item)
    logger.info(
        "intake.import.accepted item_id=%s volume_id=%s catalog_issue_id=%s", item.id, volume_id, issue_id
    )
    return item


def reject_intake_item(session: Session, *, item_id: int, owner_user_id: int) -> IntakeSessionItem:
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    item.status = ITEM_REJECTED
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def requeue_intake_item(session: Session, *, item_id: int, owner_user_id: int) -> IntakeSessionItem:
    """Rescan/reprocess an item from scratch."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    item.status = ITEM_QUEUED
    item.reason = None
    item.error = None
    item.confidence = 0.0
    session.add(item)
    session.commit()
    session.refresh(item)
    run_intake_item_async(int(item.id or 0))
    return item


def _ensure_session_acquisition(session: Session, intake: IntakeSession) -> Acquisition:
    if intake.acquisition_id:
        return get_acquisition_or_404(
            session, owner_user_id=int(intake.user_id), acquisition_id=int(intake.acquisition_id)
        )
    acq_read = create_acquisition(
        session,
        owner_user_id=int(intake.user_id),
        payload=AcquisitionCreatePayload(
            acquisition_type=ACQUISITION_TYPE_OTHER,
            purchase_date=date.today(),
            seller_name="Intake Scan",
            notes=f"Intake session {intake.session_token}",
        ),
    )
    intake.acquisition_id = int(acq_read.id)
    session.add(intake)
    session.flush()
    return get_acquisition_or_404(
        session, owner_user_id=int(intake.user_id), acquisition_id=int(acq_read.id)
    )


def add_intake_item_to_inventory(
    session: Session, *, item_id: int, owner_user_id: int
) -> IntakeSessionItem:
    """Create a catalog-spine inventory copy from the accepted match. Learns the barcode too."""
    item = _load_owned_item(session, item_id=item_id, owner_user_id=owner_user_id)
    if item.status == ITEM_ADDED_TO_INVENTORY:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item already in inventory")
    if item.selected_catalog_issue_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No catalog match selected; choose an issue first.",
        )
    issue = session.get(CatalogIssue, int(item.selected_catalog_issue_id))
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found")

    intake = session.get(IntakeSession, int(item.session_id))
    acquisition = _ensure_session_acquisition(session, intake)
    require_open(acquisition)

    copy = create_received_catalog_copy(
        session,
        acquisition=acquisition,
        catalog_issue_id=int(item.selected_catalog_issue_id),
        catalog_variant_id=item.selected_variant_id,
        series_id=int(issue.series_id),
        issue_number=str(issue.issue_number or ""),
        received_via="INTAKE_SCAN",
        received_at=utc_now(),
    )
    session.flush()
    recompute_actual_book_count(session, acquisition)
    session.add(acquisition)

    _learn_barcode(
        session,
        normalized_barcode=item.normalized_barcode,
        catalog_issue_id=int(item.selected_catalog_issue_id),
        variant_id=item.selected_variant_id,
        source=item.match_source or MATCH_SOURCE_MANUAL,
        user_id=owner_user_id,
    )

    item.status = ITEM_ADDED_TO_INVENTORY
    item.acquisition_id = int(acquisition.id or 0)
    item.inventory_copy_id = int(copy.id or 0)
    session.add(item)
    session.commit()
    session.refresh(item)
    logger.info(
        "intake.add_to_inventory item_id=%s copy_id=%s acquisition_id=%s",
        item.id,
        item.inventory_copy_id,
        item.acquisition_id,
    )
    return item


def add_all_high_confidence(session: Session, *, token: str, owner_user_id: int) -> dict[str, int]:
    """Add every auto-matched (high-confidence) item to inventory in one action."""
    intake = get_intake_session_by_token_or_404(session, token=token)
    assert_owner(intake, owner_user_id=owner_user_id)
    items = session.exec(
        select(IntakeSessionItem).where(
            IntakeSessionItem.session_id == int(intake.id or 0),
            IntakeSessionItem.status == ITEM_AUTO_MATCHED,
        )
    ).all()
    added = 0
    for item in items:
        if item.selected_catalog_issue_id is None:
            continue
        try:
            add_intake_item_to_inventory(session, item_id=int(item.id or 0), owner_user_id=owner_user_id)
            added += 1
        except HTTPException:
            logger.warning("intake.add_all skipped item_id=%s", item.id)
    return {"added": added, "candidates": len(items)}
