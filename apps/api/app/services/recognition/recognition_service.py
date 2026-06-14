from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.services.cover_images import normalize_ocr_text
from app.services.import_catalog_resolution_service import (
    issue_number_variants,
    normalize_import_publisher_key,
    normalize_import_title,
)
from app.services.recognition.catalog_matcher import (
    CATALOG_FINGERPRINT_VERIFIED_THRESHOLD,
    CatalogFingerprintMatch,
    load_catalog_issue_identity,
    search_catalog_fingerprint_matches,
)
from app.services.recognition.confidence_service import bucket_for_confidence, combine_confidence
from app.services.recognition.cover_matcher import score_cover_image
from app.services.recognition.ocr_matcher import extract_ocr_signal, is_valid_comic_image
from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from app.services.recognition.recognition_types import RecognitionCandidate, RecognitionImageSignal, RecognitionOCRSignal, RecognitionResult

LOGGER = logging.getLogger(__name__)


@dataclass
class _RecognitionMetrics:
    recognition_attempts: int = 0
    verified_results: int = 0
    review_results: int = 0
    unknown_results: int = 0
    confidence_total: float = 0.0

    def snapshot(self) -> dict[str, float | int]:
        average_confidence = self.confidence_total / self.recognition_attempts if self.recognition_attempts else 0.0
        return {
            "recognition_attempts": self.recognition_attempts,
            "verified_results": self.verified_results,
            "review_results": self.review_results,
            "unknown_results": self.unknown_results,
            "average_confidence": round(average_confidence, 6),
        }


_METRICS = _RecognitionMetrics()
_METRICS_LOCK = threading.Lock()


def recognition_metrics_snapshot() -> dict[str, float | int]:
    with _METRICS_LOCK:
        return _METRICS.snapshot()


def _record_result(confidence: float, bucket: str) -> None:
    with _METRICS_LOCK:
        _METRICS.recognition_attempts += 1
        _METRICS.confidence_total += confidence
        if bucket == "VERIFIED":
            _METRICS.verified_results += 1
        elif bucket == "REVIEW":
            _METRICS.review_results += 1
        else:
            _METRICS.unknown_results += 1


def _compact_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    stop_words = {
        "the",
        "and",
        "for",
        "of",
        "a",
        "an",
        "vol",
        "volume",
        "comic",
        "comics",
        "issue",
        "variant",
        "cover",
    }
    tokens = []
    for raw in normalize_import_title(value).split():
        token = raw.strip().lower()
        if len(token) < 3 or token in stop_words:
            continue
        tokens.append(token)
    return tokens[:4]


def _string_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalize_import_title(left)
    right_norm = normalize_import_title(right)
    if not left_norm or not right_norm:
        return 0.0
    return round(SequenceMatcher(None, left_norm, right_norm).ratio(), 6)


def _issue_similarity(input_issue: str | None, candidate_issue: str | None) -> float:
    if not input_issue and not candidate_issue:
        return 0.35
    if not input_issue or not candidate_issue:
        return 0.50
    input_variants = set(issue_number_variants(input_issue))
    candidate_variants = set(issue_number_variants(candidate_issue))
    if input_variants & candidate_variants:
        return 1.0
    if normalize_import_title(input_issue) == normalize_import_title(candidate_issue):
        return 0.92
    return 0.0


def _publisher_similarity(input_publisher: str | None, candidate_publisher: str | None) -> float:
    if not input_publisher and not candidate_publisher:
        return 0.2
    if not input_publisher or not candidate_publisher:
        return 0.15
    return 1.0 if normalize_import_publisher_key(input_publisher) == normalize_import_publisher_key(candidate_publisher) else 0.0


def _variant_similarity(input_variant: str | None, variant_rows: list[ExternalCatalogVariant]) -> tuple[float, ExternalCatalogVariant | None]:
    if not input_variant:
        return 0.0, None
    input_norm = normalize_import_title(input_variant)
    best_score = 0.0
    best_row: ExternalCatalogVariant | None = None
    for row in variant_rows:
        options = [row.cover_label, row.variant_name]
        for option in options:
            score = _string_similarity(input_norm, option)
            if score > best_score:
                best_score = score
                best_row = row
    return best_score, best_row


def _catalog_candidate_to_read(candidate: RecognitionCandidate) -> RecognitionCandidateRead:
    return RecognitionCandidateRead(
        series=candidate.series,
        issue_number=candidate.issue_number,
        variant=candidate.variant,
        publisher=candidate.publisher,
        release_date=candidate.release_date,
        confidence=candidate.confidence,
        cover_image_url=candidate.cover_image_url,
        source=candidate.source,
        source_id=candidate.source_id,
    )


def _choose_cover_url(issue: ExternalCatalogIssue, variants: list[ExternalCatalogVariant], *, input_variant: str | None) -> str | None:
    variant_score, matched_variant = _variant_similarity(input_variant, variants)
    if matched_variant is not None and matched_variant.image_url:
        return matched_variant.image_url
    if issue.high_resolution_image_url:
        return issue.high_resolution_image_url
    if issue.cover_image_url:
        return issue.cover_image_url
    if issue.thumbnail_url:
        return issue.thumbnail_url
    if variants:
        for row in variants:
            if row.image_url:
                return row.image_url
    del variant_score
    return None


def _best_series_title(issue: ExternalCatalogIssue) -> str:
    return issue.series_name or issue.title or "Unknown"


def _catalog_rank(
    *,
    ocr: RecognitionOCRSignal,
    issue: ExternalCatalogIssue,
    variants: list[ExternalCatalogVariant],
) -> tuple[float, float, float, float, ExternalCatalogVariant | None]:
    title_confidence = _string_similarity(ocr.title, issue.series_name or issue.title)
    issue_confidence = _issue_similarity(ocr.issue_number, issue.issue_number)
    publisher_confidence = _publisher_similarity(ocr.publisher, issue.publisher)
    variant_confidence, matched_variant = _variant_similarity(ocr.variant, variants)

    score = (
        0.55 * title_confidence
        + 0.25 * issue_confidence
        + 0.10 * publisher_confidence
        + 0.10 * variant_confidence
    )
    if issue.cover_image_url or issue.high_resolution_image_url or issue.thumbnail_url:
        score += 0.02
    if matched_variant and matched_variant.image_url:
        score += 0.02
    return round(min(score, 1.0), 6), title_confidence, issue_confidence, publisher_confidence, matched_variant


def _issue_variants_map(session: Session) -> dict[int, list[ExternalCatalogVariant]]:
    rows = session.exec(select(ExternalCatalogVariant)).all()
    mapping: dict[int, list[ExternalCatalogVariant]] = {}
    for row in rows:
        mapping.setdefault(int(row.external_issue_id), []).append(row)
    return mapping


def _search_external_catalog_candidates(
    session: Session,
    *,
    ocr: RecognitionOCRSignal,
) -> list[RecognitionCandidate]:
    issues = session.exec(select(ExternalCatalogIssue)).all()
    variants_by_issue = _issue_variants_map(session)
    ranked: list[tuple[float, RecognitionCandidate]] = []
    for issue in issues:
        if issue.id is None:
            continue
        variant_rows = variants_by_issue.get(int(issue.id), [])
        score, title_confidence, issue_confidence, publisher_confidence, matched_variant = _catalog_rank(
            ocr=ocr,
            issue=issue,
            variants=variant_rows,
        )
        if score < 0.20 and not ocr.title:
            continue
        candidate = RecognitionCandidate(
            series=_best_series_title(issue),
            issue_number=issue.issue_number or (ocr.issue_number or ""),
            variant=(matched_variant.cover_label or matched_variant.variant_name) if matched_variant else (ocr.variant or None),
            publisher=issue.publisher or ocr.publisher,
            release_date=issue.release_date,
            confidence=score,
            cover_image_url=_choose_cover_url(issue, variant_rows, input_variant=ocr.variant),
            source="ExternalCatalogIssue",
            source_id=int(issue.id),
        )
        ranked.append((score, candidate))
    ranked.sort(key=lambda row: (-row[0], row[1].series.lower(), row[1].issue_number))
    return [candidate for _score, candidate in ranked[:5]]


def _fallback_candidate_from_ocr(ocr: RecognitionOCRSignal) -> RecognitionCandidate | None:
    if not any((ocr.title, ocr.issue_number, ocr.publisher, ocr.variant)):
        return None
    return RecognitionCandidate(
        series=ocr.title or "Unknown",
        issue_number=ocr.issue_number or "",
        variant=ocr.variant,
        publisher=ocr.publisher,
        release_date=None,
        confidence=0.0,
        cover_image_url=None,
        source="ocr",
        source_id=None,
    )


def _candidate_from_catalog_match(session: Session, match: CatalogFingerprintMatch) -> RecognitionCandidate | None:
    identity = load_catalog_issue_identity(session, match.issue_id)
    if identity is None:
        return None
    return RecognitionCandidate(
        series=identity.series,
        issue_number=identity.issue_number,
        variant=None,
        publisher=identity.publisher,
        release_date=None,
        confidence=match.confidence,
        cover_image_url=identity.cover_image_url,
        source="CatalogIssue",
        source_id=identity.catalog_issue_id,
    )


def _winning_source(
    *,
    catalog_fingerprint_score: float,
    external_catalog_score: float,
    ocr_score: float,
    best_candidate: RecognitionCandidate | None,
) -> str:
    if catalog_fingerprint_score >= CATALOG_FINGERPRINT_VERIFIED_THRESHOLD:
        return "catalog_image_fingerprint"
    scores: list[tuple[float, str]] = [
        (catalog_fingerprint_score, "catalog_image_fingerprint"),
        (external_catalog_score, "ExternalCatalogIssue"),
        (ocr_score, "ocr"),
    ]
    scores.sort(key=lambda row: row[0], reverse=True)
    if scores[0][0] <= 0.0:
        if best_candidate is not None:
            return best_candidate.source
        return "none"
    return scores[0][1]


def identify_comic_cover(
    session: Session,
    *,
    image_bytes: bytes,
    source_name: str = "upload",
    record_metrics: bool = True,
) -> RecognitionResult:
    if not is_valid_comic_image(image_bytes):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid comic image")

    image_signal: RecognitionImageSignal = score_cover_image(session, image_bytes)
    ocr_signal = extract_ocr_signal(image_bytes, source_name=source_name)
    ocr_score = ocr_signal.confidence

    catalog_matches = search_catalog_fingerprint_matches(session, image_bytes)
    catalog_fingerprint_score = catalog_matches[0].confidence if catalog_matches else 0.0

    if catalog_matches and catalog_fingerprint_score >= CATALOG_FINGERPRINT_VERIFIED_THRESHOLD:
        top_match = catalog_matches[0]
        identity = load_catalog_issue_identity(session, top_match.issue_id)
        catalog_candidate = _candidate_from_catalog_match(session, top_match)
        candidates = [catalog_candidate] if catalog_candidate is not None else []
        confidence = catalog_fingerprint_score
        bucket: str = "VERIFIED"
        result = RecognitionResult(
            bucket=bucket,
            confidence=confidence,
            series=identity.series if identity else (catalog_candidate.series if catalog_candidate else None),
            issue_number=identity.issue_number if identity else (catalog_candidate.issue_number if catalog_candidate else None),
            variant=None,
            publisher=identity.publisher if identity else (catalog_candidate.publisher if catalog_candidate else None),
            release_date=None,
            cover_image_url=identity.cover_image_url if identity else (catalog_candidate.cover_image_url if catalog_candidate else None),
            candidate_count=len(candidates),
            candidates=candidates,
            image_confidence=image_signal.confidence,
            ocr_confidence=ocr_score,
            title_match_confidence=catalog_fingerprint_score,
            issue_match_confidence=1.0,
            ocr_text=normalize_ocr_text(ocr_signal.raw_text),
            catalog_issue_id=top_match.issue_id,
            winning_source="catalog_image_fingerprint",
            catalog_fingerprint_score=catalog_fingerprint_score,
            external_catalog_score=0.0,
            ocr_score=ocr_score,
            final_confidence=confidence,
        )
        if record_metrics:
            _record_result(confidence, bucket)
        LOGGER.info(
            "recognition_attempt bucket=%s confidence=%.3f catalog_fp=%.3f winning=%s catalog_issue_id=%s",
            bucket,
            confidence,
            catalog_fingerprint_score,
            result.winning_source,
            top_match.issue_id,
        )
        return result

    external_candidates = _search_external_catalog_candidates(session, ocr=ocr_signal)
    external_catalog_score = external_candidates[0].confidence if external_candidates else 0.0

    catalog_candidate = _candidate_from_catalog_match(session, catalog_matches[0]) if catalog_matches else None
    prefer_catalog = (
        catalog_candidate is not None
        and catalog_fingerprint_score >= external_catalog_score
        and catalog_fingerprint_score >= 0.70
    )

    if prefer_catalog and catalog_candidate is not None:
        best_candidate = catalog_candidate
        title_match_confidence = catalog_fingerprint_score
        issue_match_confidence = 1.0
        candidates = [catalog_candidate, *external_candidates[:4]]
    else:
        best_candidate = external_candidates[0] if external_candidates else _fallback_candidate_from_ocr(ocr_signal)
        title_match_confidence = best_candidate.confidence if best_candidate is not None else 0.0
        if best_candidate and best_candidate.source == "CatalogIssue":
            issue_match_confidence = 1.0
        else:
            issue_match_confidence = (
                1.0
                if best_candidate
                and best_candidate.issue_number
                and ocr_signal.issue_number
                and issue_number_variants(best_candidate.issue_number) & set(issue_number_variants(ocr_signal.issue_number))
                else 0.0
            )
        candidates = external_candidates
        if catalog_candidate is not None and catalog_candidate not in candidates:
            candidates = [catalog_candidate, *candidates[:4]]

    confidence = combine_confidence(
        image_confidence=image_signal.confidence,
        ocr_confidence=ocr_score,
        title_match_confidence=title_match_confidence,
        issue_match_confidence=issue_match_confidence,
    )
    bucket = bucket_for_confidence(confidence)

    catalog_issue_id = None
    if best_candidate and best_candidate.source == "CatalogIssue" and best_candidate.source_id is not None:
        catalog_issue_id = int(best_candidate.source_id)
    elif prefer_catalog and catalog_matches:
        catalog_issue_id = catalog_matches[0].issue_id

    winning_source = _winning_source(
        catalog_fingerprint_score=catalog_fingerprint_score,
        external_catalog_score=external_catalog_score,
        ocr_score=ocr_score,
        best_candidate=best_candidate,
    )

    series = best_candidate.series if best_candidate else ocr_signal.title
    issue_number = best_candidate.issue_number if best_candidate else ocr_signal.issue_number
    variant = best_candidate.variant if best_candidate else ocr_signal.variant
    publisher = best_candidate.publisher if best_candidate else ocr_signal.publisher
    release_date = best_candidate.release_date if best_candidate else None
    cover_image_url = best_candidate.cover_image_url if best_candidate else None

    result = RecognitionResult(
        bucket=bucket,
        confidence=confidence,
        series=series,
        issue_number=issue_number,
        variant=variant,
        publisher=publisher,
        release_date=release_date,
        cover_image_url=cover_image_url,
        candidate_count=len(candidates),
        candidates=candidates,
        image_confidence=image_signal.confidence,
        ocr_confidence=ocr_score,
        title_match_confidence=title_match_confidence,
        issue_match_confidence=issue_match_confidence,
        ocr_text=normalize_ocr_text(ocr_signal.raw_text),
        catalog_issue_id=catalog_issue_id,
        winning_source=winning_source,
        catalog_fingerprint_score=catalog_fingerprint_score,
        external_catalog_score=external_catalog_score,
        ocr_score=ocr_score,
        final_confidence=confidence,
    )
    if record_metrics:
        _record_result(confidence, bucket)
    LOGGER.info(
        "recognition_attempt bucket=%s confidence=%.3f candidates=%d image=%.3f ocr=%.3f title=%.3f issue=%.3f catalog_fp=%.3f external=%.3f winning=%s",
        bucket,
        confidence,
        len(candidates),
        image_signal.confidence,
        ocr_score,
        title_match_confidence,
        issue_match_confidence,
        catalog_fingerprint_score,
        external_catalog_score,
        winning_source,
    )
    return result


def identify_comic_cover_read(
    session: Session,
    *,
    image_bytes: bytes,
    source_name: str = "upload",
) -> RecognitionIdentifyRead:
    result = identify_comic_cover(session, image_bytes=image_bytes, source_name=source_name, record_metrics=True)
    return RecognitionIdentifyRead(
        bucket=result.bucket,
        confidence=result.confidence,
        series=result.series,
        issue_number=result.issue_number,
        variant=result.variant,
        publisher=result.publisher,
        release_date=result.release_date,
        cover_image_url=result.cover_image_url,
        catalog_issue_id=result.catalog_issue_id,
        winning_source=result.winning_source,
        catalog_fingerprint_score=result.catalog_fingerprint_score,
        external_catalog_score=result.external_catalog_score,
        ocr_score=result.ocr_score,
        final_confidence=result.final_confidence,
        candidate_count=result.candidate_count,
        candidates=[_catalog_candidate_to_read(candidate) for candidate in result.candidates],
        metrics=recognition_metrics_snapshot(),
    )


def list_recognition_candidates_read(
    session: Session,
    *,
    image_bytes: bytes,
    source_name: str = "upload",
) -> list[RecognitionCandidateRead]:
    result = identify_comic_cover(session, image_bytes=image_bytes, source_name=source_name, record_metrics=False)
    return [_catalog_candidate_to_read(candidate) for candidate in result.candidates]

