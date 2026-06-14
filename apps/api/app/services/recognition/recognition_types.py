from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

RecognitionBucket = Literal["VERIFIED", "REVIEW", "UNKNOWN"]


@dataclass(frozen=True)
class RecognitionOCRSignal:
    raw_text: str
    normalized_text: str | None
    title: str | None
    issue_number: str | None
    publisher: str | None
    variant: str | None
    confidence: float


@dataclass(frozen=True)
class RecognitionImageSignal:
    sha256: str
    phash: str | None
    ahash: str | None
    dhash: str | None
    confidence: float
    best_fingerprint_match: dict[str, object] | None = None
    top_fingerprint_matches: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class RecognitionCandidate:
    series: str
    issue_number: str
    variant: str | None
    publisher: str | None
    release_date: date | None
    confidence: float
    cover_image_url: str | None = None
    source: str = "catalog"
    source_id: int | None = None


@dataclass(frozen=True)
class RecognitionResult:
    bucket: RecognitionBucket
    confidence: float
    series: str | None
    issue_number: str | None
    variant: str | None
    publisher: str | None
    release_date: date | None
    cover_image_url: str | None
    candidate_count: int
    candidates: list[RecognitionCandidate] = field(default_factory=list)
    image_confidence: float = 0.0
    ocr_confidence: float = 0.0
    title_match_confidence: float = 0.0
    issue_match_confidence: float = 0.0
    ocr_text: str | None = None
    catalog_issue_id: int | None = None
    winning_source: str = "none"
    catalog_fingerprint_score: float = 0.0
    external_catalog_score: float = 0.0
    ocr_score: float = 0.0
    final_confidence: float = 0.0

