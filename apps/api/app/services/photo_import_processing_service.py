"""P100 photo processing pipeline (placeholder + AI hook)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import Session, select

from app.models.photo_import import (
    IMAGE_STATUS_PROCESSING,
    IMAGE_STATUS_PROCESSED,
    PhotoImportDetectedBook,
    PhotoImportImage,
)
from app.services.photo_import_ai_recognition_service import run_ai_recognition_for_image
from app.services.photo_import_candidate_service import refresh_candidates_for_detection
from app.services.photo_import_session_service import refresh_session_counts

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _abs_path(relative: str) -> Path:
    return REPO_ROOT / relative.replace("/", "\\") if "\\" in relative else REPO_ROOT / relative


def process_photo_import_image(session: Session, *, image_id: int) -> None:
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        return
    image.status = IMAGE_STATUS_PROCESSING
    session.add(image)
    session.commit()

    run_ai_recognition_for_image(session, image_id=image_id)

    detections = session.exec(
        select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == image_id)
    ).all()
    logger.info(
        "photo_import.processing.detections image_id=%s crop_count=%d",
        image_id,
        len(detections),
    )
    for det in detections:
        refresh_candidates_for_detection(session, detected_book_id=int(det.id or 0))
        refreshed = session.get(PhotoImportDetectedBook, int(det.id or 0))
        logger.info(
            "photo_import.processing.candidates image_id=%s detection_id=%s series=%r issue=%r "
            "candidate_count=%s recognition_status=%s",
            image_id,
            det.id,
            (refreshed.ai_series if refreshed else None),
            (refreshed.ai_issue_number if refreshed else None),
            (refreshed.candidate_count if refreshed else None),
            (refreshed.recognition_status if refreshed else None),
        )

    image.status = IMAGE_STATUS_PROCESSED
    session.add(image)
    session.commit()
    refresh_session_counts(session, session_id=int(image.session_id))
    logger.info("photo_import.processing.complete image_id=%s status=%s", image_id, image.status)
