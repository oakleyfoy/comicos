"""Shared ready-cover selection for P97 bulk fingerprint and OCR jobs."""
from __future__ import annotations

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint, CatalogOcrMetadata
from app.services.catalog_cover_harvest_service import resolve_catalog_image_local_path

READY_DOWNLOAD_STATUS = "ready"
READY_IMAGE_TYPE = "cover"


def _ready_cover_filters():
    return (
        CatalogImage.image_type == READY_IMAGE_TYPE,
        CatalogImage.download_status == READY_DOWNLOAD_STATUS,
    )


def _missing_valid_fingerprint_clause():
    return or_(
        CatalogImageFingerprint.id.is_(None),
        (col(CatalogImageFingerprint.phash).is_(None))
        & (col(CatalogImageFingerprint.dhash).is_(None))
        & (col(CatalogImageFingerprint.ahash).is_(None)),
    )


def count_ready_covers(session: Session) -> int:
    """Same universe as p97_progress_watch / p97_catalog_health ready_covers."""
    statement = select(func.count()).select_from(CatalogImage).where(*_ready_cover_filters())
    return int(session.exec(statement).one())


def count_missing_fingerprints(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .outerjoin(CatalogImageFingerprint, CatalogImageFingerprint.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(_missing_valid_fingerprint_clause())
    )
    return int(session.exec(statement).one())


def count_missing_ocr(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .outerjoin(CatalogOcrMetadata, CatalogOcrMetadata.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(CatalogOcrMetadata.id.is_(None))
    )
    return int(session.exec(statement).one())


def select_ready_covers_needing_fingerprint(
    session: Session,
    *,
    limit: int,
    after_image_id: int | None = None,
) -> list[CatalogImage]:
    statement = (
        select(CatalogImage)
        .outerjoin(CatalogImageFingerprint, CatalogImageFingerprint.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(_missing_valid_fingerprint_clause())
        .order_by(CatalogImage.id)
    )
    if after_image_id is not None:
        statement = statement.where(CatalogImage.id > after_image_id)
    fetch_limit = max(limit * 5, limit)
    candidates = list(session.exec(statement.limit(fetch_limit)).all())
    return _filter_with_resolvable_local_path(session, candidates, limit)


def select_ready_covers_with_fingerprint(
    session: Session,
    *,
    limit: int,
) -> list[CatalogImage]:
    has_hash = or_(
        col(CatalogImageFingerprint.phash).is_not(None),
        col(CatalogImageFingerprint.dhash).is_not(None),
        col(CatalogImageFingerprint.ahash).is_not(None),
    )
    statement = (
        select(CatalogImage)
        .join(CatalogImageFingerprint, CatalogImageFingerprint.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(has_hash)
        .order_by(CatalogImage.id)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def select_ready_covers_needing_ocr(
    session: Session,
    *,
    limit: int,
    after_image_id: int | None = None,
) -> list[CatalogImage]:
    statement = (
        select(CatalogImage)
        .outerjoin(CatalogOcrMetadata, CatalogOcrMetadata.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(CatalogOcrMetadata.id.is_(None))
        .order_by(CatalogImage.id)
    )
    if after_image_id is not None:
        statement = statement.where(CatalogImage.id > after_image_id)
    fetch_limit = max(limit * 5, limit)
    candidates = list(session.exec(statement.limit(fetch_limit)).all())
    return _filter_with_resolvable_local_path(session, candidates, limit)


def select_ready_covers_with_ocr(
    session: Session,
    *,
    limit: int,
) -> list[CatalogImage]:
    statement = (
        select(CatalogImage)
        .join(CatalogOcrMetadata, CatalogOcrMetadata.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .order_by(CatalogImage.id)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def _filter_with_resolvable_local_path(
    session: Session,
    candidates: list[CatalogImage],
    limit: int,
) -> list[CatalogImage]:
    selected: list[CatalogImage] = []
    for image in candidates:
        if resolve_catalog_image_local_path(session, image) is None:
            continue
        selected.append(image)
        if len(selected) >= limit:
            break
    return selected


def count_valid_fingerprints_on_ready_covers(session: Session) -> int:
    has_hash = or_(
        col(CatalogImageFingerprint.phash).is_not(None),
        col(CatalogImageFingerprint.dhash).is_not(None),
        col(CatalogImageFingerprint.ahash).is_not(None),
    )
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .join(CatalogImageFingerprint, CatalogImageFingerprint.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
        .where(has_hash)
    )
    return int(session.exec(statement).one())


def count_ocr_rows_on_ready_covers(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .join(CatalogOcrMetadata, CatalogOcrMetadata.image_id == CatalogImage.id)
        .where(*_ready_cover_filters())
    )
    return int(session.exec(statement).one())


def count_ready_by_download_status_only(session: Session) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .where(CatalogImage.download_status == READY_DOWNLOAD_STATUS)
    )
    return int(session.exec(statement).one())


def count_missing_fingerprints_before_path_filter(session: Session) -> int:
    return count_missing_fingerprints(session)


def count_ready_with_resolvable_path(session: Session, *, sample_limit: int = 5000) -> int:
    statement = (
        select(CatalogImage)
        .where(*_ready_cover_filters())
        .order_by(CatalogImage.id)
        .limit(max(sample_limit, 1))
    )
    rows = list(session.exec(statement).all())
    return sum(1 for row in rows if resolve_catalog_image_local_path(session, row) is not None)


def distinct_image_types(session: Session, *, limit: int = 50) -> list[tuple[str | None, int]]:
    statement = (
        select(CatalogImage.image_type, func.count())
        .group_by(CatalogImage.image_type)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [(name, int(count)) for name, count in session.exec(statement).all()]


def distinct_download_statuses(session: Session, *, limit: int = 50) -> list[tuple[str | None, int]]:
    statement = (
        select(CatalogImage.download_status, func.count())
        .group_by(CatalogImage.download_status)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [(name, int(count)) for name, count in session.exec(statement).all()]


def sample_ready_cover_rows(session: Session, *, limit: int = 5) -> list[dict]:
    statement = (
        select(CatalogImage)
        .where(CatalogImage.download_status == READY_DOWNLOAD_STATUS)
        .order_by(CatalogImage.id)
        .limit(limit)
    )
    rows = list(session.exec(statement).all())
    samples: list[dict] = []
    for row in rows:
        resolved = resolve_catalog_image_local_path(session, row)
        samples.append(
            {
                "id": int(row.id or 0),
                "image_type": row.image_type,
                "download_status": row.download_status,
                "local_path": row.local_path,
                "resolved_local_path": str(resolved) if resolved else None,
                "path_resolvable": resolved is not None,
            }
        )
    return samples


def collect_enrichment_diagnostics(session: Session, *, batch_limit: int = 10) -> dict:
    missing_fp = count_missing_fingerprints(session)
    selected_fp = select_ready_covers_needing_fingerprint(session, limit=batch_limit)
    missing_ocr = count_missing_ocr(session)
    selected_ocr = select_ready_covers_needing_ocr(session, limit=batch_limit)
    total_images = int(session.exec(select(func.count()).select_from(CatalogImage)).one())
    return {
        "total_catalog_images": total_images,
        "ready_by_progress_watch_definition": count_ready_covers(session),
        "ready_by_selector_definition_before_path_filter": count_ready_covers(session),
        "ready_by_download_status_only": count_ready_by_download_status_only(session),
        "missing_fingerprints_before_path_filter": missing_fp,
        "missing_ocr_before_path_filter": missing_ocr,
        "ready_with_resolvable_path_sampled": count_ready_with_resolvable_path(session),
        "selected_for_fingerprint_batch": len(selected_fp),
        "selected_for_ocr_batch": len(selected_ocr),
        "distinct_image_type": distinct_image_types(session),
        "distinct_download_status": distinct_download_statuses(session),
        "sample_ready_cover_rows": sample_ready_cover_rows(session, limit=5),
    }
