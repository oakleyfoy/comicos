"""P100 photo processing pipeline (placeholder + AI hook)."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.models.photo_import import (
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_PROCESSING,
    IMAGE_STATUS_PROCESSED,
    PhotoImportImage,
)
from app.services.photo_import_session_service import refresh_session_counts
from app.services.photo_import_vision_sandbox_service import run_vision_sandbox_for_image

logger = logging.getLogger(__name__)


def run_photo_import_image_processing(image_id: int) -> None:
    """Background worker entrypoint (opens its own DB session)."""
    from app.db.session import get_engine

    try:
        with Session(get_engine()) as session:
            process_photo_import_image(session, image_id=image_id)
    except Exception:
        logger.exception("photo_import.processing.background_failed image_id=%s", image_id)

def process_photo_import_image(session: Session, *, image_id: int) -> None:
    """Run pure GPT vision on each uploaded photo (no catalog detections/candidates)."""
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        return
    image.status = IMAGE_STATUS_PROCESSING
    session.add(image)
    session.commit()

    logger.info(
        "photo_import.processing.gpt_vision image_id=%s skipping_catalog_pipeline=true",
        image_id,
    )
    try:
        run_vision_sandbox_for_image(session, image_id=image_id)
        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_PROCESSED
            session.add(image)
            session.commit()
    except Exception:
        logger.exception("photo_import.processing.gpt_vision.failed image_id=%s", image_id)
        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_FAILED
            session.add(image)
            session.commit()
        raise

    refresh_session_counts(session, session_id=int(image.session_id) if image else 0)
    logger.info("photo_import.processing.gpt_vision.complete image_id=%s", image_id)
