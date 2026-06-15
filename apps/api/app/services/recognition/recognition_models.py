from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.recognition.recognition_types import RecognitionBucket


class RecognitionCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series: str
    issue_number: str
    variant: str | None = None
    publisher: str | None = None
    release_date: date | None = None
    confidence: float
    cover_image_url: str | None = None
    source: str = "catalog"
    source_id: int | None = None


class RecognitionCatalogCandidateRead(BaseModel):
    """P95-06 catalog candidate card for the recognition review modal."""

    model_config = ConfigDict(from_attributes=True)

    catalog_issue_id: int
    series: str
    issue_number: str
    issue_title: str | None = None
    series_start_year: int | None = None
    volume_number: int | None = None
    variant: str | None = None
    publisher: str | None = None
    cover_image_url: str | None = None
    cover_date: date | None = None
    release_date: date | None = None
    confidence: float = 0.0
    source: str = "catalog_search"


class RecognitionIdentifyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    bucket: RecognitionBucket
    confidence: float
    series: str | None = None
    issue_number: str | None = None
    variant: str | None = None
    publisher: str | None = None
    release_date: date | None = None
    cover_image_url: str | None = None
    catalog_issue_id: int | None = None
    winning_source: str = "none"
    catalog_fingerprint_score: float = 0.0
    external_catalog_score: float = 0.0
    ocr_score: float = 0.0
    final_confidence: float = 0.0
    visual_match_strength: Literal["exact", "possible", "weak", "none"] = "none"
    recognition_guidance: str | None = None
    candidate_count: int = 0
    candidates: list[RecognitionCandidateRead] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

