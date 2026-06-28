"""Ops OCR engine health (Render / production observability)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.models import User
from app.services.ocr_health_service import probe_tesseract_health
from app.services.ops_admin import ensure_ops_admin_access

ocr_health_ops_router = APIRouter(prefix="/api/ops", tags=["ops"])


@ocr_health_ops_router.get("/ocr-health")
def get_ocr_health(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    ensure_ops_admin_access(current_user, settings)
    return probe_tesseract_health()


def attach_ocr_health_ops_layer(app: FastAPI) -> None:
    app.include_router(ocr_health_ops_router)
