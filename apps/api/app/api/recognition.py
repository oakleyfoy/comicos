from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.services.recognition import (
    RecognitionCandidateRead,
    RecognitionCatalogCandidateRead,
    RecognitionIdentifyRead,
    identify_comic_cover_read,
    list_recognition_candidates_read,
    search_catalog_candidates,
)

recognition_v1_router = APIRouter(prefix="/api/v1", tags=["Recognition API v1 (P95-01)"])


def attach_recognition_layer(app: FastAPI) -> None:
    app.include_router(recognition_v1_router)


async def _read_image_bytes(file: UploadFile) -> bytes:
    body = await file.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image upload is required")
    return body


@recognition_v1_router.post("/recognition/identify", response_model=RecognitionIdentifyRead)
async def identify_recognition(
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecognitionIdentifyRead:
    assert current_user.id is not None
    body = await _read_image_bytes(image)
    return identify_comic_cover_read(session, image_bytes=body, source_name=image.filename or "upload")


@recognition_v1_router.post("/recognition/candidates", response_model=list[RecognitionCandidateRead])
async def recognition_candidates(
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RecognitionCandidateRead]:
    assert current_user.id is not None
    body = await _read_image_bytes(image)
    return list_recognition_candidates_read(session, image_bytes=body, source_name=image.filename or "upload")


@recognition_v1_router.get(
    "/recognition/catalog-candidates",
    response_model=list[RecognitionCatalogCandidateRead],
)
def recognition_catalog_candidates(
    q: str | None = Query(default=None),
    series: str | None = Query(default=None),
    issue_number: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    catalog_issue_id: int | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RecognitionCatalogCandidateRead]:
    """P95-06 catalog candidate search + same-series nearby issues for review/correction."""
    assert current_user.id is not None
    return search_catalog_candidates(
        session,
        q=q,
        series=series,
        issue_number=issue_number,
        publisher=publisher,
        catalog_issue_id=catalog_issue_id,
        limit=limit,
    )

