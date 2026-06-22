"""Quick vs accurate GPT vision profiles for phone photo import."""

from __future__ import annotations

from enum import StrEnum

from app.core.config import Settings
from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_QUICK_SYSTEM,
    COMIC_IDENTIFICATION_QUICK_USER,
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)


class ComicVisionReadMode(StrEnum):
    QUICK = "quick"
    ACCURATE = "accurate"


def normalize_vision_read_mode(value: str | None) -> ComicVisionReadMode:
    if value and value.strip().lower() == ComicVisionReadMode.ACCURATE:
        return ComicVisionReadMode.ACCURATE
    return ComicVisionReadMode.QUICK


def resolve_vision_profile(settings: Settings, mode: ComicVisionReadMode) -> dict[str, str | int]:
    """Model, image detail, max side, and prompts for one vision call."""
    if mode == ComicVisionReadMode.ACCURATE:
        model = (settings.photo_import_accurate_vision_model or "").strip() or settings.photo_import_vision_sandbox_model
        return {
            "mode": mode.value,
            "model": model,
            "image_detail": settings.photo_import_accurate_image_detail,
            "max_image_side_px": settings.photo_import_accurate_max_image_side_px,
            "system": COMIC_IDENTIFICATION_SYSTEM,
            "user": COMIC_IDENTIFICATION_USER,
        }
    return {
        "mode": mode.value,
        "model": settings.photo_import_quick_vision_model,
        "image_detail": settings.photo_import_quick_image_detail,
        "max_image_side_px": settings.photo_import_quick_max_image_side_px,
        "system": COMIC_IDENTIFICATION_QUICK_SYSTEM,
        "user": COMIC_IDENTIFICATION_QUICK_USER,
    }
