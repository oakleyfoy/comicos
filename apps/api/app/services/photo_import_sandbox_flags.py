"""P100-24 vision sandbox feature flag."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import get_settings


def photo_import_vision_sandbox_enabled() -> bool:
    return bool(get_settings().photo_import_vision_sandbox)


def assert_photo_import_matching_allowed() -> None:
    if photo_import_vision_sandbox_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo import catalog matching is disabled (PHOTO_IMPORT_VISION_SANDBOX=true)",
        )
