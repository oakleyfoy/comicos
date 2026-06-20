"""Standalone GPT Comic Read API.

Clean "photo -> GPT Vision -> answer" endpoint. Independent of the P100
photo-import pipeline: no sessions, detections, candidates, catalog, or inventory.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.models import User
from app.schemas.gpt_comic_read import GptComicReadResponse
from app.services.gpt_comic_read_service import (
    GptComicReadConfigError,
    GptComicReadError,
    GptComicReadImageError,
    read_comic_with_gpt,
)

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 20 * 1024 * 1024

gpt_comic_read_router = APIRouter(prefix="/api/v1", tags=["GPT Comic Read"])


def attach_gpt_comic_read_layer(app: FastAPI) -> None:
    app.include_router(gpt_comic_read_router)


@gpt_comic_read_router.post("/gpt-comic-read", response_model=GptComicReadResponse)
async def gpt_comic_read_endpoint(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
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
        result = read_comic_with_gpt(raw, filename=image.filename)
    except GptComicReadImageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GptComicReadConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GptComicReadError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    logger.info(
        "gpt_comic_read.success user_id=%s model=%s width=%d height=%d confidence=%.2f series=%r issue=%r",
        current_user.id,
        result.model,
        result.image_width,
        result.image_height,
        result.confidence,
        result.series,
        result.issue_number,
    )

    return GptComicReadResponse(
        publisher=result.publisher,
        series=result.series,
        issue_number=result.issue_number,
        issue_title=result.issue_title,
        year=result.year,
        cover_date=result.cover_date,
        variant_description=result.variant_description,
        barcode=result.barcode,
        confidence=result.confidence,
        reasoning=result.reasoning,
        possible_alternates=result.possible_alternates,
        raw_response=result.raw_response,
        model=result.model,
        image_width=result.image_width,
        image_height=result.image_height,
    )
