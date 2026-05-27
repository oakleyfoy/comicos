from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanBoundaryRun,
    ScanOcrArtifact,
    ScanOcrCandidate,
    ScanOcrIssue,
    ScanOcrRun,
    ScanReconciliationArtifact,
    ScanReconciliationCandidate,
    ScanReconciliationDecision,
    ScanReconciliationHistory,
    ScanReconciliationIssue,
    ScanReconciliationRun,
)
from app.schemas.scan_reconciliation import (
    ScanReconciliationArtifactRead,
    ScanReconciliationCandidateListResponse,
    ScanReconciliationCandidateRead,
    ScanReconciliationDecisionRead,
    ScanReconciliationFailureListResponse,
    ScanReconciliationHistoryRead,
    ScanReconciliationIssueListResponse,
    ScanReconciliationIssueRead,
    ScanReconciliationRunCreate,
    ScanReconciliationRunDetail,
    ScanReconciliationRunListResponse,
    ScanReconciliationRunRead,
)
from app.services.canonical_comics import CanonicalComicRow, load_canonical_comic_dataset
from app.services.metadata_enrichment import normalize_issue_number, normalize_publisher_name, normalize_series_title_with_aliases

RECONCILIATION_ENGINE_VERSION = "P40-05-v1"
_PREVIEW_MAX = 420
_NO_MATCH_THRESHOLD = 0.55
_PROBABLE_THRESHOLD = 0.78
_CONFIRMED_THRESHOLD = 0.9
_HIGH_CONFIDENCE_MULTI_THRESHOLD = 0.88
_AMBIGUITY_GAP_THRESHOLD = 0.05


@dataclass(frozen=True)
class _OcrFacts:
    title_raw: str | None
    title_normalized: str | None
    title_confidence: float
    issue_raw: str | None
    issue_normalized: str | None
    issue_confidence: float
    publisher_raw: str | None
    publisher_normalized: str | None
    publisher_confidence: float
    date_raw: str | None
    date_normalized: str | None
    date_confidence: float
    ocr_confidence_summary: dict[str, Any]


@dataclass(frozen=True)
class _CandidateDraft:
    canonical_comic_id: int | None
    publisher: str | None
    series_title: str | None
    issue_number: str | None
    variant_description: str | None
    publication_date: str | None
    confidence_score: float
    title_similarity_score: float
    issue_similarity_score: float
    publisher_similarity_score: float
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _DecisionDraft:
    selected_candidate_index: int | None
    decision_status: str
    final_confidence_score: float
    decision_reason: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ArtifactDraft:
    artifact_type: str
    body: bytes
    metadata_json: dict[str, Any]
    ext: str


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]


def utc_now():
    from app.models.scan_reconciliation import utc_now as _utc_now

    return _utc_now()


def clamp_scan_reconciliation_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _resolve_normalization_artifact_path(settings: Settings, row: ScanNormalizationArtifact) -> Path:
    base = settings.scan_normalization_storage_root.resolve()
    target = (base / row.storage_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("normalization artifact path escapes configured root")
    return target


def _resolve_reconciliation_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_reconciliation_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan reconciliation storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    reconciliation_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-reconciliation/{owner_user_id}/{scan_image_id}/{reconciliation_run_id}/{safe_type}{ext}".replace("\\", "/")


def _data_url_for_image(image: Image.Image) -> str:
    preview = image.copy()
    if preview.mode not in {"RGB", "RGBA", "L"}:
        preview = preview.convert("RGB")
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    rendered = io.BytesIO()
    preview.save(rendered, format="PNG")
    return f"data:image/png;base64,{rendered.getvalue().hex()}"


def _load_source_preview(settings: Settings, source_artifact: ScanNormalizationArtifact) -> str | None:
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image:
            preview = image.copy()
            if preview.mode not in {"RGB", "RGBA", "L"}:
                preview = preview.convert("RGB")
            preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
            rendered = io.BytesIO()
            preview.save(rendered, format="PNG")
            import base64

            return f"data:image/png;base64,{base64.b64encode(rendered.getvalue()).decode('ascii')}"
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        return None


def normalize_title_candidate(value: str | None, *, session: Session) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "I", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "O", normalized)
    normalized = re.sub(r"[^A-Za-z0-9' ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None
    return normalize_series_title_with_aliases(normalized, session=session).canonical_value


def _title_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^A-Za-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def reconcile_issue_number(value: str | None) -> tuple[str | None, str | None]:
    raw_value = (value or "").strip() or None
    if raw_value is None:
        return None, None
    working = unicodedata.normalize("NFKC", raw_value)
    working = re.sub(r"^(?:issue|no\.?)\s+", "", working, flags=re.IGNORECASE).strip()
    working = working.lstrip("#").strip()
    annual = re.match(r"^annual\s+(.+)$", working, flags=re.IGNORECASE)
    if annual is not None:
        remainder_raw = annual.group(1).strip()
        base = normalize_issue_number(remainder_raw).canonical_value or remainder_raw
        return raw_value, f"Annual {base}"
    decimal = re.fullmatch(r"(\d+)\.([A-Za-z0-9]+)", working)
    if decimal is not None:
        return raw_value, f"{int(decimal.group(1))}.{decimal.group(2).upper()}"
    compact = re.sub(r"\s+", "", working)
    compact = compact.upper()
    if re.fullmatch(r"\d+[A-Z][A-Z0-9]*", compact):
        number = re.match(r"(\d+)", compact)
        assert number is not None
        return raw_value, f"{int(number.group(1))}{compact[number.end():]}"
    base = normalize_issue_number(compact).canonical_value or compact
    return raw_value, base


def _best_ocr_candidate(rows: list[ScanOcrCandidate], candidate_type: str) -> ScanOcrCandidate | None:
    typed = [row for row in rows if row.candidate_type == candidate_type]
    if not typed:
        return None
    return sorted(
        typed,
        key=lambda row: (
            -float(row.confidence_score),
            row.normalized_candidate_value or "",
            row.candidate_value,
            int(row.id or 0),
        ),
    )[0]


def _extract_ocr_facts(ocr_run: ScanOcrRun, rows: list[ScanOcrCandidate], *, session: Session) -> _OcrFacts:
    title = _best_ocr_candidate(rows, "TITLE")
    issue = _best_ocr_candidate(rows, "ISSUE_NUMBER")
    publisher = _best_ocr_candidate(rows, "PUBLISHER")
    date_row = _best_ocr_candidate(rows, "DATE")
    raw_issue, normalized_issue = reconcile_issue_number(issue.normalized_candidate_value if issue else None)
    return _OcrFacts(
        title_raw=title.candidate_value if title else None,
        title_normalized=normalize_title_candidate(title.normalized_candidate_value or title.candidate_value, session=session) if title else None,
        title_confidence=float(title.confidence_score) if title else 0.0,
        issue_raw=raw_issue or (issue.candidate_value if issue else None),
        issue_normalized=normalized_issue,
        issue_confidence=float(issue.confidence_score) if issue else 0.0,
        publisher_raw=publisher.candidate_value if publisher else None,
        publisher_normalized=normalize_publisher_name(
            publisher.normalized_candidate_value or publisher.candidate_value if publisher else None,
            session=session,
        ).canonical_value,
        publisher_confidence=float(publisher.confidence_score) if publisher else 0.0,
        date_raw=date_row.candidate_value if date_row else None,
        date_normalized=date_row.normalized_candidate_value if date_row else None,
        date_confidence=float(date_row.confidence_score) if date_row else 0.0,
        ocr_confidence_summary=dict(ocr_run.output_manifest_json.get("confidence_summary") or {}),
    )


def _sequence_score(left: str | None, right: str | None) -> float:
    lkey = _title_key(left)
    rkey = _title_key(right)
    if not lkey or not rkey:
        return 0.0
    if lkey == rkey:
        return 1.0
    return round(SequenceMatcher(a=lkey, b=rkey).ratio(), 6)


def _publisher_similarity(ocr_publisher: str | None, dataset_row: CanonicalComicRow) -> float:
    if not ocr_publisher:
        return 0.5
    okey = _title_key(ocr_publisher)
    publisher_terms = {dataset_row.publisher, *dataset_row.legacy_aliases}
    keys = {_title_key(value) for value in publisher_terms if value}
    if okey in keys:
        return 1.0
    if any(okey in key or key in okey for key in keys):
        return 0.7
    return 0.0


def _issue_similarity(ocr_issue: str | None, dataset_issue: str | None) -> float:
    if not ocr_issue or not dataset_issue:
        return 0.0
    _, normalized_dataset_issue = reconcile_issue_number(dataset_issue)
    if normalized_dataset_issue is None:
        return 0.0
    if ocr_issue.upper() == normalized_dataset_issue.upper():
        return 1.0
    if ocr_issue.split(".")[0].upper() == normalized_dataset_issue.split(".")[0].upper():
        return 0.8
    if ocr_issue.upper() in normalized_dataset_issue.upper() or normalized_dataset_issue.upper() in ocr_issue.upper():
        return 0.6
    return 0.0


def _date_score(ocr_date: str | None, publication_date: date | None) -> float:
    if not ocr_date or publication_date is None:
        return 0.5
    upper = ocr_date.upper()
    year_match = re.search(r"(19|20)\d{2}", upper)
    if year_match is None:
        return 0.5
    year = int(year_match.group(0))
    if year == publication_date.year:
        return 1.0
    if abs(year - publication_date.year) == 1:
        return 0.6
    return 0.2


def generate_match_candidates(
    *,
    snapshot_rows: tuple[CanonicalComicRow, ...],
    ocr_facts: _OcrFacts,
) -> list[_CandidateDraft]:
    drafts: list[_CandidateDraft] = []
    for row in snapshot_rows:
        title_score = max(
            _sequence_score(ocr_facts.title_normalized, row.title),
            *[_sequence_score(ocr_facts.title_normalized, alias) for alias in row.title_synonyms],
            0.0,
        )
        issue_score = _issue_similarity(ocr_facts.issue_normalized, row.issue_number)
        publisher_score = _publisher_similarity(ocr_facts.publisher_normalized, row)
        date_score = _date_score(ocr_facts.date_normalized, row.publication_date)
        ocr_weight = round(
            (
                ocr_facts.title_confidence
                + ocr_facts.issue_confidence
                + ocr_facts.publisher_confidence
                + ocr_facts.date_confidence
            )
            / 4,
            6,
        )
        final_score = round(
            min(
                1.0,
                max(
                    0.0,
                    title_score * 0.42
                    + issue_score * 0.28
                    + publisher_score * 0.18
                    + date_score * 0.06
                    + ocr_weight * 0.06,
                ),
            ),
            6,
        )
        if final_score < 0.2 and max(title_score, issue_score, publisher_score) <= 0.0:
            continue
        matched_via_alias = bool(row.title_synonyms and title_score >= 0.95 and _title_key(ocr_facts.title_normalized) not in {_title_key(row.title)})
        drafts.append(
            _CandidateDraft(
                canonical_comic_id=row.canonical_comic_id,
                publisher=row.publisher,
                series_title=row.title,
                issue_number=row.issue_number,
                variant_description=row.variant_description,
                publication_date=row.publication_date.isoformat() if row.publication_date else None,
                confidence_score=final_score,
                title_similarity_score=round(title_score, 6),
                issue_similarity_score=round(issue_score, 6),
                publisher_similarity_score=round(publisher_score, 6),
                metadata_json={
                    "date_score": round(date_score, 6),
                    "ocr_weight": round(ocr_weight, 6),
                    "matched_via_alias": matched_via_alias,
                    "title_synonyms": list(row.title_synonyms),
                    "legacy_aliases": list(row.legacy_aliases),
                },
            )
        )
    return sorted(
        drafts,
        key=lambda row: (
            -row.confidence_score,
            -(row.title_similarity_score + row.issue_similarity_score + row.publisher_similarity_score),
            row.publisher or "",
            row.series_title or "",
            row.issue_number or "",
            row.variant_description or "",
            row.canonical_comic_id or 0,
        ),
    )


def resolve_reconciliation_decision(candidates: list[_CandidateDraft]) -> _DecisionDraft:
    if not candidates:
        return _DecisionDraft(
            selected_candidate_index=None,
            decision_status="NO_MATCH_FOUND",
            final_confidence_score=0.0,
            decision_reason="No canonical dataset candidates met the deterministic threshold.",
            metadata_json={"top_score": 0.0, "candidate_count": 0},
        )
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    gap = round(top.confidence_score - (second.confidence_score if second else 0.0), 6)
    high_confidence_count = sum(1 for row in candidates if row.confidence_score >= _HIGH_CONFIDENCE_MULTI_THRESHOLD)
    if top.confidence_score < _NO_MATCH_THRESHOLD:
        return _DecisionDraft(
            selected_candidate_index=None,
            decision_status="NO_MATCH_FOUND",
            final_confidence_score=top.confidence_score,
            decision_reason="Top deterministic match score is below the no-match threshold.",
            metadata_json={"top_score": top.confidence_score, "gap_to_next": gap},
        )
    if high_confidence_count >= 2 and gap < _AMBIGUITY_GAP_THRESHOLD:
        return _DecisionDraft(
            selected_candidate_index=None,
            decision_status="MULTIPLE_HIGH_CONFIDENCE_MATCHES",
            final_confidence_score=top.confidence_score,
            decision_reason="Multiple high-confidence candidates remain too close to resolve deterministically.",
            metadata_json={"top_score": top.confidence_score, "gap_to_next": gap, "high_confidence_count": high_confidence_count},
        )
    if second is None and top.confidence_score >= _PROBABLE_THRESHOLD:
        return _DecisionDraft(
            selected_candidate_index=0,
            decision_status="MATCH_CONFIRMED",
            final_confidence_score=top.confidence_score,
            decision_reason="A single deterministic candidate cleared the probable threshold with no competing alternatives.",
            metadata_json={"top_score": top.confidence_score, "gap_to_next": gap},
        )
    if top.confidence_score >= _CONFIRMED_THRESHOLD and gap >= 0.07:
        return _DecisionDraft(
            selected_candidate_index=0,
            decision_status="MATCH_CONFIRMED",
            final_confidence_score=top.confidence_score,
            decision_reason="Top candidate exceeds confirmed threshold with clear separation from the next candidate.",
            metadata_json={"top_score": top.confidence_score, "gap_to_next": gap},
        )
    if top.confidence_score >= _PROBABLE_THRESHOLD and gap >= _AMBIGUITY_GAP_THRESHOLD:
        return _DecisionDraft(
            selected_candidate_index=0,
            decision_status="MATCH_PROBABLE",
            final_confidence_score=top.confidence_score,
            decision_reason="Top candidate exceeds probable threshold with deterministic separation.",
            metadata_json={"top_score": top.confidence_score, "gap_to_next": gap},
        )
    return _DecisionDraft(
        selected_candidate_index=None,
        decision_status="MATCH_AMBIGUOUS",
        final_confidence_score=top.confidence_score,
        decision_reason="Top candidates remain too close to deterministically choose a single comic identity.",
        metadata_json={"top_score": top.confidence_score, "gap_to_next": gap},
    )


def _build_issues(
    *,
    ocr_facts: _OcrFacts,
    candidates: list[_CandidateDraft],
    decision: _DecisionDraft,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    avg_conf = float(ocr_facts.ocr_confidence_summary.get("average_region_confidence") or 0.0)
    if avg_conf < 0.5:
        issues.append(_IssueDraft("OCR_CONFIDENCE_TOO_LOW", "WARNING", "OCR confidence is too low for strong reconciliation.", {"average_region_confidence": avg_conf}))
    if not ocr_facts.title_normalized or not ocr_facts.issue_normalized:
        issues.append(
            _IssueDraft(
                "INCOMPLETE_METADATA",
                "WARNING",
                "OCR candidates did not provide both title and issue number for reconciliation.",
                {"title": ocr_facts.title_normalized, "issue_number": ocr_facts.issue_normalized},
            )
        )
    if decision.decision_status == "NO_MATCH_FOUND":
        issues.append(_IssueDraft("NO_MATCH_FOUND", "ERROR", "No deterministic canonical comic match was found.", decision.metadata_json))
    if decision.decision_status in {"MATCH_AMBIGUOUS", "MULTIPLE_HIGH_CONFIDENCE_MATCHES"}:
        issues.append(_IssueDraft(decision.decision_status, "WARNING", decision.decision_reason, decision.metadata_json))
    if candidates:
        top = candidates[0]
        if top.confidence_score < _PROBABLE_THRESHOLD and top.confidence_score >= _NO_MATCH_THRESHOLD:
            issues.append(_IssueDraft("LOW_MATCH_CONFIDENCE", "WARNING", "Top canonical match confidence is below probable threshold.", {"confidence_score": top.confidence_score}))
        if top.publisher_similarity_score < 0.5 and ocr_facts.publisher_normalized:
            issues.append(_IssueDraft("PUBLISHER_CONFLICT", "INFO", "OCR publisher and canonical publisher did not align strongly.", {"ocr_publisher": ocr_facts.publisher_normalized, "canonical_publisher": top.publisher}))
        if top.issue_similarity_score < 0.8 and ocr_facts.issue_normalized:
            issues.append(_IssueDraft("ISSUE_NUMBER_CONFLICT", "INFO", "OCR issue number and canonical issue number differ.", {"ocr_issue": ocr_facts.issue_normalized, "canonical_issue": top.issue_number}))
        if len(candidates) > 1 and abs(candidates[0].title_similarity_score - candidates[1].title_similarity_score) < 0.02:
            issues.append(_IssueDraft("TITLE_AMBIGUITY", "INFO", "Title similarity remained ambiguous across top candidates.", {"top_two_title_scores": [candidates[0].title_similarity_score, candidates[1].title_similarity_score]}))
        if len({row.variant_description for row in candidates[:3] if row.variant_description}) > 1:
            issues.append(_IssueDraft("VARIANT_AMBIGUITY", "INFO", "Top candidates disagree on variant description.", {}))
        if any(bool(row.metadata_json.get("matched_via_alias")) for row in candidates[:1]):
            issues.append(_IssueDraft("LEGACY_SERIES_CONFLICT", "INFO", "Top candidate required a legacy title synonym.", {}))
    return issues


def build_reconciliation_manifest(
    *,
    original_scan_checksum: str,
    normalization_checksum: str,
    boundary_checksum: str,
    ocr_checksum: str,
    source_checksum: str,
    canonical_dataset_version: str,
    ocr_facts: _OcrFacts,
    candidates: list[_CandidateDraft],
    decision: _DecisionDraft,
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "reconciliation_engine_version": RECONCILIATION_ENGINE_VERSION,
        "canonical_dataset_version": canonical_dataset_version,
        "original_scan_checksum": original_scan_checksum,
        "normalization_checksum": normalization_checksum,
        "boundary_checksum": boundary_checksum,
        "ocr_checksum": ocr_checksum,
        "source_checksum": source_checksum,
        "ocr_facts": {
            "title_raw": ocr_facts.title_raw,
            "title_normalized": ocr_facts.title_normalized,
            "issue_raw": ocr_facts.issue_raw,
            "issue_normalized": ocr_facts.issue_normalized,
            "publisher_raw": ocr_facts.publisher_raw,
            "publisher_normalized": ocr_facts.publisher_normalized,
            "date_raw": ocr_facts.date_raw,
            "date_normalized": ocr_facts.date_normalized,
            "ocr_confidence_summary": ocr_facts.ocr_confidence_summary,
        },
        "candidates": [
            {
                "candidate_rank": index + 1,
                "canonical_comic_id": row.canonical_comic_id,
                "publisher": row.publisher,
                "series_title": row.series_title,
                "issue_number": row.issue_number,
                "variant_description": row.variant_description,
                "publication_date": row.publication_date,
                "confidence_score": row.confidence_score,
                "title_similarity_score": row.title_similarity_score,
                "issue_similarity_score": row.issue_similarity_score,
                "publisher_similarity_score": row.publisher_similarity_score,
                "metadata_json": row.metadata_json,
            }
            for index, row in enumerate(candidates)
        ],
        "decision": {
            "decision_status": decision.decision_status,
            "final_confidence_score": decision.final_confidence_score,
            "decision_reason": decision.decision_reason,
            "metadata_json": decision.metadata_json,
        },
        "issues": [
            {
                "issue_type": row.issue_type,
                "severity": row.severity,
                "issue_message": row.issue_message,
                "metadata_json": row.metadata_json,
            }
            for row in issues
        ],
        "artifact_checksums": sorted(artifact_checksums, key=lambda row: row["artifact_type"]),
    }
    return manifest, _hash_payload(manifest)


def _report_artifact(*, decision: _DecisionDraft, candidates: list[_CandidateDraft], dataset_version: str) -> _ArtifactDraft:
    lines = [
        f"decision_status={decision.decision_status}",
        f"final_confidence_score={decision.final_confidence_score}",
        f"canonical_dataset_version={dataset_version}",
        f"candidate_count={len(candidates)}",
    ]
    if candidates:
        top = candidates[0]
        lines.append(f"top_candidate={top.publisher} | {top.series_title} | {top.issue_number}")
    body = "\n".join(lines).encode("utf-8")
    return _ArtifactDraft("RECONCILIATION_REPORT", body, {"format": "txt"}, ".txt")


def _candidate_export_artifact(candidates: list[_CandidateDraft]) -> _ArtifactDraft:
    body = json.dumps([_json_safe(row.__dict__) for row in candidates], sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("MATCH_CANDIDATE_EXPORT", body, {"format": "json"}, ".json")


def _score_breakdown_artifact(candidates: list[_CandidateDraft]) -> _ArtifactDraft:
    payload = [
        {
            "canonical_comic_id": row.canonical_comic_id,
            "confidence_score": row.confidence_score,
            "title_similarity_score": row.title_similarity_score,
            "issue_similarity_score": row.issue_similarity_score,
            "publisher_similarity_score": row.publisher_similarity_score,
            "metadata_json": row.metadata_json,
        }
        for row in candidates
    ]
    body = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("SCORE_BREAKDOWN", body, {"format": "json"}, ".json")


def _debug_artifact(*, ocr_facts: _OcrFacts, candidates: list[_CandidateDraft]) -> _ArtifactDraft:
    payload = {
        "ocr_facts": _json_safe(ocr_facts.__dict__),
        "top_candidates": [_json_safe(row.__dict__) for row in candidates[:5]],
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("MATCH_DEBUG_PREVIEW", body, {"format": "json"}, ".json")


def _manifest_artifact(manifest: dict[str, Any]) -> _ArtifactDraft:
    body = json.dumps(_json_safe(manifest), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("RECONCILIATION_MANIFEST", body, {"format": "json"}, ".json")


def _history_event_checksum(
    *,
    reconciliation_run_id: int,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> str:
    return _hash_payload(
        {
            "reconciliation_run_id": reconciliation_run_id,
            "event_type": event_type,
            "event_message": event_message,
            "metadata_json": metadata_json,
        }
    )


def _resolve_context(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    ocr_run_id: int | None,
) -> tuple[ScanImage, ScanNormalizationRun, ScanBoundaryRun, ScanOcrRun, ScanNormalizationArtifact]:
    scan_image = session.get(ScanImage, scan_image_id)
    if scan_image is None or scan_image.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found")

    if ocr_run_id is not None:
        ocr_run = session.get(ScanOcrRun, ocr_run_id)
        if ocr_run is None or ocr_run.owner_user_id != owner_user_id or ocr_run.scan_image_id != scan_image_id:
            raise HTTPException(status_code=404, detail="OCR run not found")
    else:
        ocr_run = session.exec(
            select(ScanOcrRun)
            .where(
                ScanOcrRun.owner_user_id == owner_user_id,
                ScanOcrRun.scan_image_id == scan_image_id,
                ScanOcrRun.ocr_status == "COMPLETE",
            )
            .order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
        ).first()
        if ocr_run is None:
            raise HTTPException(status_code=422, detail="No completed OCR run exists for this scan image")

    normalization_run = session.get(ScanNormalizationRun, ocr_run.normalization_run_id)
    boundary_run = session.get(ScanBoundaryRun, ocr_run.boundary_run_id)
    source_artifact = session.get(ScanNormalizationArtifact, ocr_run.source_artifact_id)
    if normalization_run is None or boundary_run is None or source_artifact is None:
        raise HTTPException(status_code=422, detail="OCR run lineage is incomplete")
    return scan_image, normalization_run, boundary_run, ocr_run, source_artifact


def _persist_failed_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    normalization_run: ScanNormalizationRun,
    boundary_run: ScanBoundaryRun,
    ocr_run: ScanOcrRun,
    source_checksum: str,
    input_manifest: dict[str, Any],
    dataset_version: str,
    error_message: str,
) -> ScanReconciliationRun:
    checksum = _hash_payload({**input_manifest, "dataset_version": dataset_version, "error_message": error_message, "status": "FAILED"})
    existing = session.exec(
        select(ScanReconciliationRun)
        .where(
            ScanReconciliationRun.owner_user_id == owner_user_id,
            ScanReconciliationRun.reconciliation_checksum == checksum,
        )
        .order_by(col(ScanReconciliationRun.created_at).desc(), col(ScanReconciliationRun.id).desc())
    ).first()
    if existing is not None:
        return existing
    now = utc_now()
    run = ScanReconciliationRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(normalization_run.id or 0),
        boundary_run_id=int(boundary_run.id or 0),
        ocr_run_id=int(ocr_run.id or 0),
        source_checksum=source_checksum,
        reconciliation_checksum=checksum,
        reconciliation_status="FAILED",
        reconciliation_engine_version=RECONCILIATION_ENGINE_VERSION,
        canonical_dataset_version=dataset_version,
        input_manifest_json=input_manifest,
        output_manifest_json={"error_message": error_message},
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        ScanReconciliationIssue(
            owner_user_id=owner_user_id,
            reconciliation_run_id=int(run.id or 0),
            issue_type="NO_MATCH_FOUND",
            severity="ERROR",
            issue_message=error_message[:512],
            metadata_json={"error_message": error_message[:2000]},
            created_at=now,
        )
    )
    session.add(
        ScanReconciliationHistory(
            owner_user_id=owner_user_id,
            reconciliation_run_id=int(run.id or 0),
            event_type="FAILED",
            event_message=error_message[:512],
            event_checksum=_history_event_checksum(
                reconciliation_run_id=int(run.id or 0),
                event_type="FAILED",
                event_message=error_message[:512],
                metadata_json={"error_message": error_message[:2000]},
            ),
            metadata_json={"error_message": error_message[:2000]},
            created_at=now,
        )
    )
    session.commit()
    session.refresh(run)
    return run


def _candidate_read(row: ScanReconciliationCandidate) -> ScanReconciliationCandidateRead:
    return ScanReconciliationCandidateRead.model_validate(row, from_attributes=True)


def _decision_read(row: ScanReconciliationDecision) -> ScanReconciliationDecisionRead:
    return ScanReconciliationDecisionRead.model_validate(row, from_attributes=True)


def _artifact_read(row: ScanReconciliationArtifact) -> ScanReconciliationArtifactRead:
    return ScanReconciliationArtifactRead.model_validate({**row.model_dump(mode="json"), "preview_data_url": None})


def _issue_read(row: ScanReconciliationIssue) -> ScanReconciliationIssueRead:
    return ScanReconciliationIssueRead.model_validate(row, from_attributes=True)


def _history_read(row: ScanReconciliationHistory) -> ScanReconciliationHistoryRead:
    return ScanReconciliationHistoryRead.model_validate(row, from_attributes=True)


def _run_read(row: ScanReconciliationRun) -> ScanReconciliationRunRead:
    return ScanReconciliationRunRead.model_validate(row, from_attributes=True)


def _build_run_detail(
    session: Session,
    settings: Settings,
    *,
    run: ScanReconciliationRun,
    scan_image: ScanImage,
    source_artifact: ScanNormalizationArtifact | None = None,
) -> ScanReconciliationRunDetail:
    candidates = list(
        session.exec(
            select(ScanReconciliationCandidate)
            .where(ScanReconciliationCandidate.reconciliation_run_id == run.id)
            .order_by(col(ScanReconciliationCandidate.candidate_rank).asc(), col(ScanReconciliationCandidate.id).asc())
        ).all()
    )
    decision = session.exec(
        select(ScanReconciliationDecision)
        .where(ScanReconciliationDecision.reconciliation_run_id == run.id)
        .order_by(col(ScanReconciliationDecision.created_at).desc(), col(ScanReconciliationDecision.id).desc())
    ).first()
    artifacts = list(
        session.exec(
            select(ScanReconciliationArtifact)
            .where(ScanReconciliationArtifact.reconciliation_run_id == run.id)
            .order_by(col(ScanReconciliationArtifact.artifact_type).asc(), col(ScanReconciliationArtifact.id).asc())
        ).all()
    )
    issues = list(
        session.exec(
            select(ScanReconciliationIssue)
            .where(ScanReconciliationIssue.reconciliation_run_id == run.id)
            .order_by(col(ScanReconciliationIssue.created_at).asc(), col(ScanReconciliationIssue.id).asc())
        ).all()
    )
    history = list(
        session.exec(
            select(ScanReconciliationHistory)
            .where(ScanReconciliationHistory.reconciliation_run_id == run.id)
            .order_by(col(ScanReconciliationHistory.created_at).asc(), col(ScanReconciliationHistory.id).asc())
        ).all()
    )
    normalization_run = session.get(ScanNormalizationRun, run.normalization_run_id)
    boundary_run = session.get(ScanBoundaryRun, run.boundary_run_id)
    ocr_run = session.get(ScanOcrRun, run.ocr_run_id)
    source_artifact = source_artifact or session.get(ScanNormalizationArtifact, ocr_run.source_artifact_id if ocr_run else 0)
    selected_candidate = None
    if decision is not None and decision.selected_candidate_id is not None:
        selected_candidate = next((row for row in candidates if row.id == decision.selected_candidate_id), None)
    return ScanReconciliationRunDetail(
        **_run_read(run).model_dump(),
        candidates=[_candidate_read(row) for row in candidates],
        decision=_decision_read(decision) if decision is not None else None,
        artifacts=[_artifact_read(row) for row in artifacts],
        issues=[_issue_read(row) for row in issues],
        history=[_history_read(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum if normalization_run is not None else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run is not None else None,
        ocr_checksum=ocr_run.ocr_checksum if ocr_run is not None else None,
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact is not None else None,
        selected_candidate=_candidate_read(selected_candidate) if selected_candidate is not None else None,
    )


def run_scan_reconciliation(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanReconciliationRunCreate,
) -> tuple[ScanReconciliationRunDetail, bool]:
    scan_image, normalization_run, boundary_run, ocr_run, source_artifact = _resolve_context(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        ocr_run_id=payload.ocr_run_id,
    )
    dataset_snapshot = load_canonical_comic_dataset(session)
    input_manifest = {
        "scan_image_id": int(scan_image.id or 0),
        "normalization_run_id": int(normalization_run.id or 0),
        "boundary_run_id": int(boundary_run.id or 0),
        "ocr_run_id": int(ocr_run.id or 0),
        "source_checksum": ocr_run.ocr_checksum,
        "reconciliation_engine_version": RECONCILIATION_ENGINE_VERSION,
    }
    try:
        ocr_candidates = list(
            session.exec(
                select(ScanOcrCandidate)
                .where(ScanOcrCandidate.ocr_run_id == ocr_run.id)
                .order_by(col(ScanOcrCandidate.candidate_type).asc(), col(ScanOcrCandidate.confidence_score).desc(), col(ScanOcrCandidate.id).asc())
            ).all()
        )
        ocr_facts = _extract_ocr_facts(ocr_run, ocr_candidates, session=session)
        candidates = generate_match_candidates(snapshot_rows=dataset_snapshot.rows, ocr_facts=ocr_facts)
        decision = resolve_reconciliation_decision(candidates)
        issues = _build_issues(ocr_facts=ocr_facts, candidates=candidates, decision=decision)
    except ValueError as exc:
        failed = _persist_failed_run(
            session,
            owner_user_id=owner_user_id,
            scan_image=scan_image,
            normalization_run=normalization_run,
            boundary_run=boundary_run,
            ocr_run=ocr_run,
            source_checksum=ocr_run.ocr_checksum,
            input_manifest=input_manifest,
            dataset_version=dataset_snapshot.dataset_version,
            error_message=str(exc),
        )
        return _build_run_detail(session, settings, run=failed, scan_image=scan_image, source_artifact=source_artifact), False

    provisional_artifacts = [
        _report_artifact(decision=decision, candidates=candidates, dataset_version=dataset_snapshot.dataset_version),
        _candidate_export_artifact(candidates),
        _score_breakdown_artifact(candidates),
        _debug_artifact(ocr_facts=ocr_facts, candidates=candidates),
    ]
    provisional_checksums = [{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts]
    provisional_manifest, _ = build_reconciliation_manifest(
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum,
        boundary_checksum=boundary_run.boundary_checksum,
        ocr_checksum=ocr_run.ocr_checksum,
        source_checksum=ocr_run.ocr_checksum,
        canonical_dataset_version=dataset_snapshot.dataset_version,
        ocr_facts=ocr_facts,
        candidates=candidates,
        decision=decision,
        issues=issues,
        artifact_checksums=provisional_checksums,
    )
    final_artifacts = provisional_artifacts + [_manifest_artifact(provisional_manifest)]
    artifact_checksums = [{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in final_artifacts]
    output_manifest, reconciliation_checksum = build_reconciliation_manifest(
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum,
        boundary_checksum=boundary_run.boundary_checksum,
        ocr_checksum=ocr_run.ocr_checksum,
        source_checksum=ocr_run.ocr_checksum,
        canonical_dataset_version=dataset_snapshot.dataset_version,
        ocr_facts=ocr_facts,
        candidates=candidates,
        decision=decision,
        issues=issues,
        artifact_checksums=artifact_checksums,
    )
    final_artifacts = provisional_artifacts + [_manifest_artifact(output_manifest)]

    existing = session.exec(
        select(ScanReconciliationRun)
        .where(
            ScanReconciliationRun.owner_user_id == owner_user_id,
            ScanReconciliationRun.reconciliation_checksum == reconciliation_checksum,
        )
        .order_by(col(ScanReconciliationRun.created_at).desc(), col(ScanReconciliationRun.id).desc())
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing, scan_image=scan_image, source_artifact=source_artifact), False

    now = utc_now()
    run = ScanReconciliationRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(normalization_run.id or 0),
        boundary_run_id=int(boundary_run.id or 0),
        ocr_run_id=int(ocr_run.id or 0),
        source_checksum=ocr_run.ocr_checksum,
        reconciliation_checksum=reconciliation_checksum,
        reconciliation_status=decision.decision_status,
        reconciliation_engine_version=RECONCILIATION_ENGINE_VERSION,
        canonical_dataset_version=dataset_snapshot.dataset_version,
        input_manifest_json=input_manifest,
        output_manifest_json=output_manifest,
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    candidate_rows: list[ScanReconciliationCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        row = ScanReconciliationCandidate(
            owner_user_id=owner_user_id,
            reconciliation_run_id=int(run.id or 0),
            candidate_rank=index,
            canonical_comic_id=candidate.canonical_comic_id,
            publisher=candidate.publisher,
            series_title=candidate.series_title,
            issue_number=candidate.issue_number,
            variant_description=candidate.variant_description,
            publication_date=candidate.publication_date,
            confidence_score=candidate.confidence_score,
            title_similarity_score=candidate.title_similarity_score,
            issue_similarity_score=candidate.issue_similarity_score,
            publisher_similarity_score=candidate.publisher_similarity_score,
            metadata_json=candidate.metadata_json,
            created_at=now,
        )
        session.add(row)
        session.flush()
        candidate_rows.append(row)

    selected_candidate_id = None
    if decision.selected_candidate_index is not None and 0 <= decision.selected_candidate_index < len(candidate_rows):
        selected_candidate_id = int(candidate_rows[decision.selected_candidate_index].id or 0)
    decision_row = ScanReconciliationDecision(
        owner_user_id=owner_user_id,
        reconciliation_run_id=int(run.id or 0),
        selected_candidate_id=selected_candidate_id,
        decision_status=decision.decision_status,
        final_confidence_score=decision.final_confidence_score,
        decision_reason=decision.decision_reason,
        metadata_json=decision.metadata_json,
        created_at=now,
    )
    session.add(decision_row)

    for artifact in final_artifacts:
        rel_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=int(scan_image.id or 0),
            reconciliation_run_id=int(run.id or 0),
            artifact_type=artifact.artifact_type,
            ext=artifact.ext,
        )
        target = _resolve_reconciliation_storage_path(settings, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(artifact.body)
        session.add(
            ScanReconciliationArtifact(
                owner_user_id=owner_user_id,
                reconciliation_run_id=int(run.id or 0),
                artifact_type=artifact.artifact_type,
                storage_backend="filesystem",
                storage_path=rel_path,
                artifact_checksum=_sha256_bytes(artifact.body),
                metadata_json=artifact.metadata_json,
                created_at=now,
            )
        )

    for issue in issues:
        session.add(
            ScanReconciliationIssue(
                owner_user_id=owner_user_id,
                reconciliation_run_id=int(run.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
                created_at=now,
            )
        )

    history_rows = [
        _HistoryDraft("RUN_STARTED", "OCR reconciliation run started.", input_manifest),
        _HistoryDraft("CANDIDATES_RANKED", "Canonical comic candidates were scored and ranked.", {"candidate_count": len(candidates)}),
        _HistoryDraft("DECISION_MADE", "Deterministic reconciliation decision was recorded.", {"decision_status": decision.decision_status}),
        _HistoryDraft("RUN_COMPLETED", "OCR reconciliation run completed.", {"reconciliation_checksum": reconciliation_checksum}),
    ]
    for hist in history_rows:
        session.add(
            ScanReconciliationHistory(
                owner_user_id=owner_user_id,
                reconciliation_run_id=int(run.id or 0),
                event_type=hist.event_type,
                event_message=hist.event_message,
                event_checksum=_history_event_checksum(
                    reconciliation_run_id=int(run.id or 0),
                    event_type=hist.event_type,
                    event_message=hist.event_message,
                    metadata_json=hist.metadata_json,
                ),
                metadata_json=hist.metadata_json,
                created_at=now,
            )
        )

    session.commit()
    session.refresh(run)
    return _build_run_detail(session, settings, run=run, scan_image=scan_image, source_artifact=source_artifact), True


def _get_owner_run_or_404(session: Session, *, owner_user_id: int, run_id: int) -> ScanReconciliationRun:
    row = session.get(ScanReconciliationRun, run_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan reconciliation run not found")
    return row


def get_scan_reconciliation_run_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_id: int,
) -> ScanReconciliationRunDetail:
    run = _get_owner_run_or_404(session, owner_user_id=owner_user_id, run_id=run_id)
    scan_image = session.get(ScanImage, run.scan_image_id)
    if scan_image is None:
        raise HTTPException(status_code=404, detail="Scan image not found")
    return _build_run_detail(session, settings, run=run, scan_image=scan_image)


def get_scan_reconciliation_artifact_owner(
    session: Session,
    *,
    owner_user_id: int,
    artifact_id: int,
) -> ScanReconciliationArtifactRead:
    row = session.get(ScanReconciliationArtifact, artifact_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan reconciliation artifact not found")
    return _artifact_read(row)


def list_scan_reconciliation_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationRunListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = select(ScanReconciliationRun).where(ScanReconciliationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanReconciliationRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanReconciliationRun.created_at).desc(), col(ScanReconciliationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationRun).where(ScanReconciliationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(
        select(ScanReconciliationRun.reconciliation_status, func.count())
        .where(ScanReconciliationRun.owner_user_id == owner_user_id)
        .group_by(ScanReconciliationRun.reconciliation_status)
    ).all()
    return ScanReconciliationRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        ambiguous_match_count=sum(1 for row in rows if row.reconciliation_status in {"MATCH_AMBIGUOUS", "MULTIPLE_HIGH_CONFIDENCE_MATCHES"}),
        low_confidence_count=sum(
            1
            for row in rows
            if float((row.output_manifest_json.get("decision") or {}).get("final_confidence_score") or 0.0) < _PROBABLE_THRESHOLD
        ),
    )


def list_scan_reconciliation_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationRunListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = select(ScanReconciliationRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanReconciliationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanReconciliationRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanReconciliationRun.created_at).desc(), col(ScanReconciliationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationRun)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanReconciliationRun.reconciliation_status, func.count()).group_by(ScanReconciliationRun.reconciliation_status)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanReconciliationRun.owner_user_id == owner_user_id)
    counts = session.exec(counts_stmt).all()
    return ScanReconciliationRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        ambiguous_match_count=sum(1 for row in rows if row.reconciliation_status in {"MATCH_AMBIGUOUS", "MULTIPLE_HIGH_CONFIDENCE_MATCHES"}),
        low_confidence_count=sum(
            1
            for row in rows
            if float((row.output_manifest_json.get("decision") or {}).get("final_confidence_score") or 0.0) < _PROBABLE_THRESHOLD
        ),
    )


def list_scan_reconciliation_candidates_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    reconciliation_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationCandidateListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = (
        select(ScanReconciliationCandidate)
        .join(ScanReconciliationRun, ScanReconciliationRun.id == ScanReconciliationCandidate.reconciliation_run_id)
        .where(ScanReconciliationCandidate.owner_user_id == owner_user_id)
    )
    if scan_image_id is not None:
        stmt = stmt.where(ScanReconciliationRun.scan_image_id == scan_image_id)
    if reconciliation_run_id is not None:
        stmt = stmt.where(ScanReconciliationCandidate.reconciliation_run_id == reconciliation_run_id)
    stmt = stmt.order_by(col(ScanReconciliationCandidate.candidate_rank).asc(), col(ScanReconciliationCandidate.id).asc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationCandidate).where(ScanReconciliationCandidate.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanReconciliationCandidateListResponse(
        items=[_candidate_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        canonical_match_count=sum(1 for row in rows if row.canonical_comic_id is not None),
    )


def list_scan_reconciliation_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    reconciliation_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationIssueListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = select(ScanReconciliationIssue).where(ScanReconciliationIssue.owner_user_id == owner_user_id)
    if reconciliation_run_id is not None:
        stmt = stmt.where(ScanReconciliationIssue.reconciliation_run_id == reconciliation_run_id)
    stmt = stmt.order_by(col(ScanReconciliationIssue.created_at).desc(), col(ScanReconciliationIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationIssue).where(ScanReconciliationIssue.owner_user_id == owner_user_id)
    if reconciliation_run_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationIssue.reconciliation_run_id == reconciliation_run_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(
        select(ScanReconciliationIssue.issue_type, func.count())
        .where(ScanReconciliationIssue.owner_user_id == owner_user_id)
        .group_by(ScanReconciliationIssue.issue_type)
    ).all()
    return ScanReconciliationIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_reconciliation_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationIssueListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = select(ScanReconciliationIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanReconciliationIssue.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanReconciliationIssue.created_at).desc(), col(ScanReconciliationIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationIssue)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationIssue.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanReconciliationIssue.issue_type, func.count()).group_by(ScanReconciliationIssue.issue_type)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanReconciliationIssue.owner_user_id == owner_user_id)
    counts = session.exec(counts_stmt).all()
    return ScanReconciliationIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_reconciliation_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanReconciliationFailureListResponse:
    limit, offset = clamp_scan_reconciliation_pagination(limit=limit, offset=offset)
    stmt = select(ScanReconciliationRun).where(ScanReconciliationRun.reconciliation_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanReconciliationRun.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanReconciliationRun.created_at).desc(), col(ScanReconciliationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanReconciliationRun).where(ScanReconciliationRun.reconciliation_status == "FAILED")
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanReconciliationRun.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanReconciliationFailureListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
    )
