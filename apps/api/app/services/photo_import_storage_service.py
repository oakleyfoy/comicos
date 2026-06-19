"""Canonical on-disk paths for P100 phone photo import (apps/api/data/photo_import)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT
# Pre-P100-15c uploads stored under monorepo apps/ (sibling of apps/api).
LEGACY_APPS_ROOT = REPO_ROOT.parent

PHOTO_IMPORT_ROOT = REPO_ROOT / "data" / "photo_import"


def normalize_relative_storage_path(relative: str) -> str:
    return str(relative or "").strip().replace("\\", "/").lstrip("/")


def relative_path_under_repo_root(absolute: Path) -> str:
    return str(absolute.relative_to(REPO_ROOT)).replace("\\", "/")


def resolve_photo_import_storage_path(relative: str, *, image_id: int | None = None) -> Path:
    """Resolve DB storage_path to an absolute file (canonical api root, then legacy apps root)."""
    rel = normalize_relative_storage_path(relative)
    canonical = REPO_ROOT / rel
    if canonical.is_file():
        logger.info(
            "photo_import.storage.resolve image_id=%s storage_path=%s resolved_path=%s exists=True root=canonical",
            image_id,
            rel,
            canonical,
        )
        return canonical
    legacy = LEGACY_APPS_ROOT / rel
    if legacy.is_file():
        logger.info(
            "photo_import.storage.resolve image_id=%s storage_path=%s resolved_path=%s exists=True root=legacy_apps",
            image_id,
            rel,
            legacy,
        )
        return legacy
    logger.warning(
        "photo_import.storage.resolve image_id=%s storage_path=%s resolved_path=%s exists=False "
        "legacy_path=%s legacy_exists=False",
        image_id,
        rel,
        canonical,
        legacy,
    )
    return canonical


def upload_storage_dir(*, user_id: int, session_id: int) -> Path:
    path = PHOTO_IMPORT_ROOT / str(user_id) / str(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_image_api_path(*, session_token: str, image_id: int) -> str:
    return f"/api/v1/photo-import/sessions/{session_token}/images/{int(image_id)}/original"
