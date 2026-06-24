"""Standalone GPT Comic Read API.

Photo -> GPT Vision -> optional barcode extraction / ComicVine + local catalog verification.
Does not use the P100 photo-import session, detection, or candidate pipeline.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.gpt_comic_read import GptComicReadResponse
from app.services.gpt_comic_read_service import (
    GptComicReadConfigError,
    GptComicReadError,
    GptComicReadImageError,
)
from app.services.p100_gpt_comic_read_enrichment import run_gpt_comic_read_enriched

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 20 * 1024 * 1024

gpt_comic_read_router = APIRouter(prefix="/api/v1", tags=["GPT Comic Read"])


def attach_gpt_comic_read_layer(app: FastAPI) -> None:
    app.include_router(gpt_comic_read_router)


@gpt_comic_read_router.post("/gpt-comic-read", response_model=GptComicReadResponse)
async def gpt_comic_read_endpoint(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> GptComicReadResponse:
    logger.info("gpt_comic_read.called user_id=%s filename=%s", current_user.id, image.filename)

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are allowed")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image upload")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large")

    try:
        payload = run_gpt_comic_read_enriched(session, raw, filename=image.filename)
    except GptComicReadImageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GptComicReadConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GptComicReadError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    gpt = payload["gpt_read"]
    logger.info(
        "gpt_comic_read.success user_id=%s model=%s width=%d height=%d confidence=%.2f series=%r issue=%r "
        "final_match_source=%s barcode_method=%s",
        current_user.id,
        gpt["model"],
        gpt["image_width"],
        gpt["image_height"],
        gpt["confidence"],
        gpt["series"],
        gpt["issue_number"],
        payload["final_match_source"],
        payload["barcode_read"].get("method"),
    )

    return GptComicReadResponse.model_validate(payload)
