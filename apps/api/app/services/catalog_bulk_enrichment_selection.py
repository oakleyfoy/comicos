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
