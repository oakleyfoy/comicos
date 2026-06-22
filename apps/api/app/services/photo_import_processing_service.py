"""P100 photo processing pipeline (placeholder + AI hook)."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.models.photo_import import PhotoImportImage

logger = logging.getLogger(__name__)


def run_photo_import_image_processing(image_id: int, *, vision_mode: str = "quick") -> None:
    """Background worker entrypoint (opens its own DB session)."""
    from app.db.session import get_engine

    try:
        with Session(get_engine()) as session:
            process_photo_import_image(session, image_id=image_id, vision_mode=vision_mode)
    except Exception:
        logger.exception("photo_import.processing.background_failed image_id=%s", image_id)


def process_photo_import_image(
    session: Session,
    *,
    image_id: int,
    vision_mode: str = "quick",
) -> None:
    """Run pure GPT vision on each uploaded photo (no catalog detections/candidates)."""
    from app.services.comic_vision_read_mode import normalize_vision_read_mode
    from app.services.photo_import_vision_stream_service import run_vision_read_non_stream

    image = session.get(PhotoImportImage, image_id)
    if image is None:
        return
    mode = normalize_vision_read_mode(vision_mode)
    logger.info(
        "photo_import.processing.gpt_vision image_id=%s mode=%s skipping_catalog_pipeline=true",
        image_id,
        mode.value,
    )
    try:
        run_vision_read_non_stream(session, image_id=image_id, mode=mode)
    except Exception:
        logger.exception("photo_import.processing.gpt_vision.failed image_id=%s", image_id)
        raise
    logger.info("photo_import.processing.gpt_vision.complete image_id=%s", image_id)
