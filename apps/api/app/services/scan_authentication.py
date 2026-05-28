from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanAuthenticationArtifact,
    ScanAuthenticationFinding,
    ScanAuthenticationHistory,
    ScanAuthenticationIssue,
    ScanAuthenticationRun,
    ScanAuthenticationSignal,
    ScanBoundaryRun,
    ScanGradingAssistanceRun,
    ScanHistoricalComparisonRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanOcrCandidate,
    ScanOcrRun,
    ScanReconciliationCandidate,
    ScanReconciliationDecision,
    ScanReconciliationRun,
    ScanReviewDecision,
    ScanReviewSession,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_authentication import (
    ScanAuthenticationArtifactRead,
    ScanAuthenticationFindingListResponse,
    ScanAuthenticationFindingRead,
    ScanAuthenticationHistoryRead,
    ScanAuthenticationIssueListResponse,
    ScanAuthenticationIssueRead,
    ScanAuthenticationRunCreate,
    ScanAuthenticationRunDetail,
    ScanAuthenticationRunListResponse,
    ScanAuthenticationRunRead,
    ScanAuthenticationSignalListResponse,
    ScanAuthenticationSignalRead,
)
from app.services.authentication_rubric import (
    CONFLICT_CONFIDENCE_THRESHOLD,
    HISTORICAL_CONFLICT_THRESHOLD,
    LINEAGE_MINIMUM_CHECKS,
    LOW_CONFIDENCE_THRESHOLD,
    RUBRIC_VERSION,
    review_priority_for_status,
    status_for_confidence,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-16-v1"
_PREVIEW_MAX = 420


@dataclass(frozen=True)
class _SignalDraft:
    signal_type: str
    signal_category: str
    signal_status: str
    confidence_score: float
    source_system: str
    source_record_id: int | None
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _FindingDraft:
    finding_type: str
    finding_status: str
    confidence_score: float
    review_priority: str
    finding_text: str
    source_signal_ids: list[int]
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


@dataclass
class _AuthContext:
    scan_image: ScanImage
    normalization_run: ScanNormalizationRun | None
    boundary_run: ScanBoundaryRun | None
    source_artifact: ScanNormalizationArtifact | None
    ocr_run: ScanOcrRun | None
    ocr_candidates: list[ScanOcrCandidate]
    reconciliation_run: ScanReconciliationRun | None
    reconciliation_decision: ScanReconciliationDecision | None
    reconciliation_candidate: ScanReconciliationCandidate | None
    visual_run: ScanVisualEvidenceRun | None
    historical_run: ScanHistoricalComparisonRun | None
    review_session: ScanReviewSession | None
    review_decisions: list[ScanReviewDecision]
    grading_run: ScanGradingAssistanceRun | None


def utc_now():
    from app.models.scan_authentication import utc_now as _utc_now

    return _utc_now()


def clamp_scan_authentication_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _resolve_auth_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_authentication_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan authentication storage path escapes configured root")
    return target


def _artifact_storage_path(*, owner_user_id: int, scan_image_id: int, authentication_run_id: int, artifact_type: str, ext: str) -> str:
    return f"scan-authentication/{owner_user_id}/{scan_image_id}/{authentication_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_auth_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanAuthenticationArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_auth_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _load_context(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanAuthenticationRunCreate,
) -> _AuthContext:
    scan_image = session.get(ScanImage, payload.scan_image_id)
    if scan_image is None or int(scan_image.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found.")

    normalization_run = session.exec(
        select(ScanNormalizationRun)
        .where(
            ScanNormalizationRun.owner_user_id == owner_user_id,
            ScanNormalizationRun.scan_image_id == payload.scan_image_id,
            ScanNormalizationRun.normalization_status == "COMPLETE",
        )
        .order_by(col(ScanNormalizationRun.id).desc())
    ).first()
    boundary_run = session.exec(
        select(ScanBoundaryRun)
        .where(
            ScanBoundaryRun.owner_user_id == owner_user_id,
            ScanBoundaryRun.scan_image_id == payload.scan_image_id,
            ScanBoundaryRun.boundary_status == "COMPLETE",
        )
        .order_by(col(ScanBoundaryRun.id).desc())
    ).first()
    source_artifact = session.get(ScanNormalizationArtifact, int(boundary_run.source_artifact_id)) if boundary_run else None
    ocr_run = session.exec(
        select(ScanOcrRun)
        .where(ScanOcrRun.owner_user_id == owner_user_id, ScanOcrRun.scan_image_id == payload.scan_image_id, ScanOcrRun.ocr_status == "COMPLETE")
        .order_by(col(ScanOcrRun.id).desc())
    ).first()
    ocr_candidates: list[ScanOcrCandidate] = []
    if ocr_run is not None:
        ocr_candidates = session.exec(
            select(ScanOcrCandidate)
            .where(ScanOcrCandidate.ocr_run_id == ocr_run.id)
            .order_by(col(ScanOcrCandidate.candidate_type).asc(), col(ScanOcrCandidate.confidence_score).desc(), col(ScanOcrCandidate.id).asc())
        ).all()

    reconciliation_run = session.get(ScanReconciliationRun, payload.reconciliation_run_id) if payload.reconciliation_run_id else session.exec(
        select(ScanReconciliationRun)
        .where(
            ScanReconciliationRun.owner_user_id == owner_user_id,
            ScanReconciliationRun.scan_image_id == payload.scan_image_id,
            ScanReconciliationRun.reconciliation_status != "FAILED",
        )
        .order_by(col(ScanReconciliationRun.id).desc())
    ).first()
    if reconciliation_run is not None and int(reconciliation_run.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Reconciliation run not found.")
    reconciliation_decision = None
    reconciliation_candidate = None
    if reconciliation_run is not None:
        reconciliation_decision = session.exec(
            select(ScanReconciliationDecision)
            .where(ScanReconciliationDecision.reconciliation_run_id == reconciliation_run.id)
            .order_by(col(ScanReconciliationDecision.created_at).desc(), col(ScanReconciliationDecision.id).desc())
        ).first()
        if reconciliation_decision is not None and reconciliation_decision.selected_candidate_id is not None:
            reconciliation_candidate = session.get(ScanReconciliationCandidate, int(reconciliation_decision.selected_candidate_id))

    visual_run = session.get(ScanVisualEvidenceRun, payload.visual_evidence_run_id) if payload.visual_evidence_run_id else session.exec(
        select(ScanVisualEvidenceRun)
        .where(
            ScanVisualEvidenceRun.owner_user_id == owner_user_id,
            ScanVisualEvidenceRun.scan_image_id == payload.scan_image_id,
            ScanVisualEvidenceRun.evidence_status == "COMPLETE",
        )
        .order_by(col(ScanVisualEvidenceRun.id).desc())
    ).first()
    if visual_run is not None and int(visual_run.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Visual evidence run not found.")

    historical_run = session.get(ScanHistoricalComparisonRun, payload.historical_comparison_run_id) if payload.historical_comparison_run_id else session.exec(
        select(ScanHistoricalComparisonRun)
        .where(
            ScanHistoricalComparisonRun.owner_user_id == owner_user_id,
            ScanHistoricalComparisonRun.scan_image_id == payload.scan_image_id,
        )
        .order_by(col(ScanHistoricalComparisonRun.id).desc())
    ).first()
    if historical_run is not None and int(historical_run.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Historical comparison run not found.")

    review_session = session.get(ScanReviewSession, payload.review_session_id) if payload.review_session_id else session.exec(
        select(ScanReviewSession)
        .where(ScanReviewSession.owner_user_id == owner_user_id, ScanReviewSession.scan_image_id == payload.scan_image_id)
        .order_by(col(ScanReviewSession.id).desc())
    ).first()
    if review_session is not None and int(review_session.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Review session not found.")
    review_decisions: list[ScanReviewDecision] = []
    if review_session is not None:
        review_decisions = session.exec(
            select(ScanReviewDecision)
            .where(ScanReviewDecision.review_session_id == review_session.id)
            .order_by(col(ScanReviewDecision.id).asc())
        ).all()

    grading_run = None
    if visual_run is not None and visual_run.grading_assistance_run_id is not None:
        grading_run = session.get(ScanGradingAssistanceRun, int(visual_run.grading_assistance_run_id))
    if grading_run is None:
        grading_run = session.exec(
            select(ScanGradingAssistanceRun)
            .where(
                ScanGradingAssistanceRun.owner_user_id == owner_user_id,
                ScanGradingAssistanceRun.scan_image_id == payload.scan_image_id,
                ScanGradingAssistanceRun.assistance_status == "COMPLETE",
            )
            .order_by(col(ScanGradingAssistanceRun.id).desc())
        ).first()

    return _AuthContext(
        scan_image=scan_image,
        normalization_run=normalization_run,
        boundary_run=boundary_run,
        source_artifact=source_artifact,
        ocr_run=ocr_run,
        ocr_candidates=ocr_candidates,
        reconciliation_run=reconciliation_run,
        reconciliation_decision=reconciliation_decision,
        reconciliation_candidate=reconciliation_candidate,
        visual_run=visual_run,
        historical_run=historical_run,
        review_session=review_session,
        review_decisions=review_decisions,
        grading_run=grading_run,
    )


def _best_ocr_candidate(candidates: list[ScanOcrCandidate], candidate_type: str) -> ScanOcrCandidate | None:
    return next((row for row in candidates if row.candidate_type == candidate_type), None)


def evaluate_identity_consistency(context: _AuthContext) -> list[_SignalDraft]:
    signals: list[_SignalDraft] = []
    recon_conf = float(context.reconciliation_decision.final_confidence_score) if context.reconciliation_decision else 0.0
    review_identity = next((row for row in context.review_decisions if row.decision_type == "IDENTITY_CONFIRMATION"), None)
    title = _best_ocr_candidate(context.ocr_candidates, "TITLE")
    issue = _best_ocr_candidate(context.ocr_candidates, "ISSUE_NUMBER")
    publisher = _best_ocr_candidate(context.ocr_candidates, "PUBLISHER")

    review_conflict = review_identity is not None and review_identity.decision_status in {"REJECTED"}
    status = status_for_confidence(confidence_score=recon_conf, has_conflict=review_conflict, has_gap=context.reconciliation_run is None)
    signals.append(
        _SignalDraft(
            "IDENTITY_CONSISTENCY",
            "IDENTITY",
            "NEEDS_REVIEW" if context.reconciliation_run is None and not review_conflict else status,
            round(recon_conf, 6),
            "P40_05_RECONCILIATION",
            int(context.reconciliation_run.id or 0) if context.reconciliation_run else None,
            {
                "selected_candidate_id": int(context.reconciliation_decision.selected_candidate_id) if context.reconciliation_decision and context.reconciliation_decision.selected_candidate_id else None,
                "canonical_comic_id": int(context.reconciliation_candidate.canonical_comic_id) if context.reconciliation_candidate and context.reconciliation_candidate.canonical_comic_id else None,
            },
            {
                "review_identity_decision_id": int(review_identity.id or 0) if review_identity else None,
                "review_identity_status": review_identity.decision_status if review_identity else None,
            },
        )
    )

    agreement_count = sum(1 for row in (title, issue, publisher) if row is not None)
    conflict = review_identity is not None and review_identity.decision_status in {"REJECTED"}
    signals.append(
        _SignalDraft(
            "OCR_METADATA_CONSISTENCY",
            "METADATA",
            status_for_confidence(confidence_score=min(1.0, agreement_count / 3.0), has_conflict=conflict, has_gap=agreement_count == 0),
            round(min(1.0, agreement_count / 3.0), 6),
            "P40_04_OCR",
            int(context.ocr_run.id or 0) if context.ocr_run else None,
            {
                "title": title.normalized_candidate_value if title else None,
                "issue_number": issue.normalized_candidate_value if issue else None,
                "publisher": publisher.normalized_candidate_value if publisher else None,
            },
            {},
        )
    )
    return signals


def evaluate_metadata_consistency(context: _AuthContext) -> list[_SignalDraft]:
    title = _best_ocr_candidate(context.ocr_candidates, "TITLE")
    issue = _best_ocr_candidate(context.ocr_candidates, "ISSUE_NUMBER")
    publisher = _best_ocr_candidate(context.ocr_candidates, "PUBLISHER")
    candidate = context.reconciliation_candidate
    rows: list[tuple[str, str, str | None, str | None, ScanOcrCandidate | None]] = [
        ("PUBLISHER_TITLE_CONSISTENCY", "METADATA", candidate.series_title if candidate else None, title.normalized_candidate_value if title else None, title),
        ("ISSUE_NUMBER_CONSISTENCY", "METADATA", candidate.issue_number if candidate else None, issue.normalized_candidate_value if issue else None, issue),
        ("OCR_METADATA_CONSISTENCY", "METADATA", candidate.publisher if candidate else None, publisher.normalized_candidate_value if publisher else None, publisher),
    ]
    signals: list[_SignalDraft] = []
    for signal_type, category, left, right, source in rows:
        has_gap = left is None or right is None
        has_conflict = not has_gap and str(left).strip().lower() != str(right).strip().lower()
        confidence = round(float(source.confidence_score if source else 0.0), 6)
        signals.append(
            _SignalDraft(
                signal_type,
                category,
                status_for_confidence(confidence_score=confidence, has_conflict=has_conflict, has_gap=has_gap),
                confidence,
                "P40_05_RECONCILIATION",
                int(context.reconciliation_run.id or 0) if context.reconciliation_run else None,
                {"expected": left, "observed": right},
                {},
            )
        )
    return signals


def evaluate_scan_lineage_integrity(context: _AuthContext) -> list[_SignalDraft]:
    lineage_checks = {
        "original_scan_checksum": bool(context.scan_image.sha256_checksum),
        "normalization_checksum": bool(context.normalization_run and context.normalization_run.normalization_checksum),
        "boundary_checksum": bool(context.boundary_run and context.boundary_run.boundary_checksum),
        "ocr_checksum": bool(context.ocr_run and context.ocr_run.ocr_checksum),
        "reconciliation_checksum": bool(context.reconciliation_run and context.reconciliation_run.reconciliation_checksum),
    }
    present = sum(1 for value in lineage_checks.values() if value)
    confidence = round(present / len(lineage_checks), 6)
    return [
        _SignalDraft(
            "SCAN_LINEAGE_INTEGRITY",
            "LINEAGE",
            status_for_confidence(confidence_score=confidence, has_gap=present < LINEAGE_MINIMUM_CHECKS),
            confidence,
            "P40_LINEAGE",
            None,
            lineage_checks,
            {"present_count": present},
        )
    ]


def evaluate_historical_consistency(context: _AuthContext) -> list[_SignalDraft]:
    if context.historical_run is None:
        return [
            _SignalDraft(
                "HISTORICAL_MATCH_CONSISTENCY",
                "HISTORICAL",
                "NOT_APPLICABLE",
                0.0,
                "P40_15_HISTORICAL",
                None,
                {"reason": "historical_comparison_missing"},
                {},
            )
        ]
    manifest = context.historical_run.output_manifest_json or {}
    pairs = list(manifest.get("comparison_pairs") or [])
    deltas = list(manifest.get("deltas") or [])
    issues = list(manifest.get("issues") or [])
    conflict_count = sum(1 for row in issues if row.get("issue_type") in {"HISTORICAL_CONFLICT", "LOW_MATCH_CONFIDENCE"})
    inconclusive = context.historical_run.comparison_status == "INCONCLUSIVE" or any(row.get("delta_direction") == "INCONCLUSIVE" for row in deltas)
    confidence = 0.0 if not pairs else round(max(0.2, 1.0 - (conflict_count * 0.2) - (0.2 if inconclusive else 0.0)), 6)
    return [
        _SignalDraft(
            "HISTORICAL_MATCH_CONSISTENCY",
            "HISTORICAL",
            "CONFLICT_DETECTED" if conflict_count >= HISTORICAL_CONFLICT_THRESHOLD else ("INCONCLUSIVE" if inconclusive else status_for_confidence(confidence_score=confidence)),
            confidence,
            "P40_15_HISTORICAL",
            int(context.historical_run.id or 0),
            {"pair_count": len(pairs), "delta_count": len(deltas), "historical_status": context.historical_run.comparison_status},
            {},
        )
    ]


def evaluate_visual_evidence_consistency(context: _AuthContext) -> list[_SignalDraft]:
    if context.visual_run is None:
        return [
            _SignalDraft(
                "VISUAL_EVIDENCE_CONSISTENCY",
                "VISUAL",
                "NOT_APPLICABLE",
                0.0,
                "P40_13_VISUAL_EVIDENCE",
                None,
                {"reason": "visual_evidence_missing"},
                {},
            )
        ]
    output = context.visual_run.output_manifest_json or {}
    packages = list(output.get("packages") or [])
    issues = list(output.get("issues") or [])
    confidence = round(min(1.0, (len(packages) / 4.0)), 6)
    return [
        _SignalDraft(
            "VISUAL_EVIDENCE_CONSISTENCY",
            "VISUAL",
            status_for_confidence(confidence_score=confidence, has_conflict=any(row.get("severity") == "ERROR" for row in issues), has_gap=len(packages) == 0),
            confidence,
            "P40_13_VISUAL_EVIDENCE",
            int(context.visual_run.id or 0),
            {"package_count": len(packages), "issue_count": len(issues)},
            {},
        )
    ]


def evaluate_review_consistency(context: _AuthContext) -> list[_SignalDraft]:
    if context.review_session is None:
        return [
            _SignalDraft(
                "REVIEW_DECISION_CONSISTENCY",
                "REVIEW",
                "NOT_APPLICABLE",
                0.0,
                "P40_14_REVIEW",
                None,
                {"reason": "review_session_missing"},
                {},
            )
        ]
    open_issues = len(context.review_session.output_manifest_json.get("issues") or [])
    confidence = round(max(0.0, 1.0 - (open_issues * 0.15)), 6)
    return [
        _SignalDraft(
            "REVIEW_DECISION_CONSISTENCY",
            "REVIEW",
            status_for_confidence(confidence_score=confidence, has_conflict=context.review_session.review_status == "REVIEW_BLOCKED", has_gap=open_issues > 0),
            confidence,
            "P40_14_REVIEW",
            int(context.review_session.id or 0),
            {"review_status": context.review_session.review_status, "issue_count": open_issues},
            {},
        )
    ]


def _signal_issue_mapping(signal: _SignalDraft) -> _IssueDraft | None:
    if signal.signal_type == "IDENTITY_CONSISTENCY" and signal.signal_status == "CONFLICT_DETECTED":
        return _IssueDraft("IDENTITY_CONFLICT", "ERROR", "Identity evidence contains a deterministic conflict requiring review.", {})
    if signal.signal_category == "METADATA" and signal.signal_status == "CONFLICT_DETECTED":
        return _IssueDraft("METADATA_CONFLICT", "WARNING", "Metadata consistency checks detected a conflict.", {})
    if signal.signal_type == "SCAN_LINEAGE_INTEGRITY" and signal.signal_status in {"NEEDS_REVIEW", "INCONCLUSIVE"}:
        return _IssueDraft("LINEAGE_GAP", "WARNING", "Lineage integrity is incomplete for authentication assistance.", {})
    if signal.signal_type == "HISTORICAL_MATCH_CONSISTENCY" and signal.signal_status == "NOT_APPLICABLE":
        return _IssueDraft("HISTORICAL_COMPARISON_MISSING", "INFO", "Historical comparison input is not available.", {})
    if signal.signal_type == "HISTORICAL_MATCH_CONSISTENCY" and signal.signal_status == "CONFLICT_DETECTED":
        return _IssueDraft("HISTORICAL_CONFLICT", "WARNING", "Historical comparison indicates a conflict requiring review.", {})
    if signal.signal_type == "VISUAL_EVIDENCE_CONSISTENCY" and signal.signal_status == "NOT_APPLICABLE":
        return _IssueDraft("VISUAL_EVIDENCE_MISSING", "INFO", "Visual evidence input is not available.", {})
    if signal.signal_type == "IDENTITY_CONSISTENCY" and signal.signal_status == "NEEDS_REVIEW" and signal.source_record_id is None:
        return _IssueDraft("RECONCILIATION_MISSING", "WARNING", "Reconciliation context is missing for authentication assistance.", {})
    if signal.signal_status in {"NEEDS_REVIEW", "CONFLICT_DETECTED"}:
        return _IssueDraft("REVIEW_REQUIRED", "WARNING", "One or more authentication-support signals require human review.", {})
    if signal.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        return _IssueDraft("LOW_AUTHENTICATION_CONFIDENCE", "INFO", "Authentication-support confidence is limited for one or more signals.", {})
    return None


def generate_authentication_findings(signals: list[_SignalDraft]) -> tuple[list[_FindingDraft], list[_IssueDraft]]:
    findings: list[_FindingDraft] = []
    issues: list[_IssueDraft] = []
    for idx, signal in enumerate(signals, start=1):
        issue = _signal_issue_mapping(signal)
        if issue is not None:
            issues.append(issue)
        if signal.signal_status == "SUPPORTS_AUTHENTICITY_REVIEW":
            finding_type = "AUTHENTICATION_SUPPORT" if signal.signal_category in {"IDENTITY", "METADATA"} else "VISUAL_CONSISTENCY_SUPPORT"
            finding_status = "SUPPORTIVE"
            finding_text = f"{signal.signal_type.replace('_', ' ').title()} supports authenticity review with deterministic evidence linkage."
        elif signal.signal_status == "CONFLICT_DETECTED":
            finding_type = "IDENTITY_CONFLICT" if signal.signal_category == "IDENTITY" else ("METADATA_CONFLICT" if signal.signal_category == "METADATA" else "REVIEW_REQUIRED_FLAG")
            finding_status = "CONFLICT"
            finding_text = f"{signal.signal_type.replace('_', ' ').title()} detected a conflict that requires human review."
        elif signal.signal_status == "NEEDS_REVIEW":
            finding_type = "REVIEW_REQUIRED_FLAG"
            finding_status = "REVIEW_REQUIRED"
            finding_text = f"{signal.signal_type.replace('_', ' ').title()} needs additional human review."
        elif signal.signal_status == "INCONCLUSIVE":
            finding_type = "INCONCLUSIVE_AUTH_SIGNAL"
            finding_status = "INCONCLUSIVE"
            finding_text = f"{signal.signal_type.replace('_', ' ').title()} is inconclusive with the current deterministic inputs."
        else:
            finding_type = "LINEAGE_WARNING" if signal.signal_category == "LINEAGE" else "AUTHENTICATION_SUPPORT"
            finding_status = "WARNING" if signal.signal_status == "NOT_APPLICABLE" else "SUPPORTIVE"
            finding_text = f"{signal.signal_type.replace('_', ' ').title()} is not applicable or requires acknowledgment."
        findings.append(
            _FindingDraft(
                finding_type=finding_type,
                finding_status=finding_status,
                confidence_score=signal.confidence_score,
                review_priority=review_priority_for_status(signal.signal_status),
                finding_text=finding_text,
                source_signal_ids=[idx],
                metadata_json={"signal_type": signal.signal_type},
            )
        )
    unique_issues = list({(row.issue_type, row.issue_message): row for row in issues}.values())
    return findings, unique_issues


def build_authentication_manifest(
    *,
    lineage: dict[str, Any],
    signals: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    review_flags: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    artifact_refs: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "upstream_lineage": lineage,
        "signals": signals,
        "findings": findings,
        "review_flags": review_flags,
        "issues": issues,
        "artifact_refs": artifact_refs,
    }
    return manifest, _hash_payload(manifest)


def _lineage(context: _AuthContext) -> dict[str, Any]:
    return {
        "original_scan_checksum": context.scan_image.sha256_checksum,
        "normalization_checksum": context.normalization_run.normalization_checksum if context.normalization_run else None,
        "boundary_checksum": context.boundary_run.boundary_checksum if context.boundary_run else None,
        "ocr_checksum": context.ocr_run.ocr_checksum if context.ocr_run else None,
        "reconciliation_checksum": context.reconciliation_run.reconciliation_checksum if context.reconciliation_run else None,
        "visual_evidence_checksum": context.visual_run.visual_evidence_checksum if context.visual_run else None,
        "historical_comparison_checksum": context.historical_run.historical_comparison_checksum if context.historical_run else None,
        "review_checksum": context.review_session.review_checksum if context.review_session else None,
    }


def _image_or_blank(settings: Settings, source_artifact: ScanNormalizationArtifact | None) -> Image.Image:
    if source_artifact is None:
        return Image.new("RGB", (240, 340), (18, 18, 24))
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = image_fp.copy().convert("RGB")
    except (OSError, ValueError, UnidentifiedImageError, FileNotFoundError):
        image = Image.new("RGB", (240, 340), (18, 18, 24))
    image.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    return image


def _build_debug_preview(settings: Settings, context: _AuthContext, signals: list[_SignalDraft]) -> bytes:
    image = _image_or_blank(settings, context.source_artifact)
    if context.boundary_run is not None:
        draw = ImageDraw.Draw(image)
        geom = dict((context.boundary_run.output_manifest_json or {}).get("geometry") or {})
        if geom:
            draw.rectangle((geom.get("x_min", 0), geom.get("y_min", 0), geom.get("x_max", image.width - 1), geom.get("y_max", image.height - 1)), outline=(80, 180, 255), width=3)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _persist_artifacts(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    scan_image_id: int,
    authentication_run_id: int,
    drafts: list[_ArtifactDraft],
) -> None:
    for draft in drafts:
        checksum = _sha256_bytes(draft.body)
        existing = session.exec(
            select(ScanAuthenticationArtifact).where(
                ScanAuthenticationArtifact.authentication_run_id == authentication_run_id,
                ScanAuthenticationArtifact.artifact_type == draft.artifact_type,
                ScanAuthenticationArtifact.artifact_checksum == checksum,
            )
        ).first()
        if existing is not None:
            continue
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=scan_image_id,
            authentication_run_id=authentication_run_id,
            artifact_type=draft.artifact_type,
            ext=draft.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=draft.body)
        session.add(
            ScanAuthenticationArtifact(
                owner_user_id=owner_user_id,
                authentication_run_id=authentication_run_id,
                artifact_type=draft.artifact_type,
                storage_path=relative_path,
                artifact_checksum=checksum,
                metadata_json=draft.metadata_json,
            )
        )


def _append_history(session: Session, *, owner_user_id: int, authentication_run_id: int, event_type: str, event_message: str, metadata_json: dict[str, Any]) -> None:
    session.add(
        ScanAuthenticationHistory(
            owner_user_id=owner_user_id,
            authentication_run_id=authentication_run_id,
            event_type=event_type,
            event_message=event_message,
            event_checksum=_hash_payload(
                {
                    "authentication_run_id": authentication_run_id,
                    "event_type": event_type,
                    "event_message": event_message,
                    "metadata_json": metadata_json,
                }
            ),
            metadata_json=metadata_json,
        )
    )


def _detail_from_run(session: Session, settings: Settings, run: ScanAuthenticationRun) -> ScanAuthenticationRunDetail:
    signals = session.exec(
        select(ScanAuthenticationSignal).where(ScanAuthenticationSignal.authentication_run_id == run.id).order_by(col(ScanAuthenticationSignal.signal_rank), col(ScanAuthenticationSignal.id))
    ).all()
    findings = session.exec(
        select(ScanAuthenticationFinding).where(ScanAuthenticationFinding.authentication_run_id == run.id).order_by(col(ScanAuthenticationFinding.finding_rank), col(ScanAuthenticationFinding.id))
    ).all()
    artifacts = session.exec(
        select(ScanAuthenticationArtifact).where(ScanAuthenticationArtifact.authentication_run_id == run.id).order_by(col(ScanAuthenticationArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanAuthenticationIssue).where(ScanAuthenticationIssue.authentication_run_id == run.id).order_by(col(ScanAuthenticationIssue.id))
    ).all()
    history = session.exec(
        select(ScanAuthenticationHistory).where(ScanAuthenticationHistory.authentication_run_id == run.id).order_by(col(ScanAuthenticationHistory.id))
    ).all()
    context = _load_context(
        session,
        owner_user_id=int(run.owner_user_id),
        payload=ScanAuthenticationRunCreate(
            scan_image_id=int(run.scan_image_id),
            reconciliation_run_id=run.reconciliation_run_id,
            visual_evidence_run_id=run.visual_evidence_run_id,
            historical_comparison_run_id=run.historical_comparison_run_id,
            review_session_id=run.review_session_id,
        ),
    )
    artifact_reads = [
        ScanAuthenticationArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})
        for row in artifacts
    ]
    output = run.output_manifest_json or {}
    lineage = dict(output.get("upstream_lineage") or {})
    return ScanAuthenticationRunDetail(
        **ScanAuthenticationRunRead.model_validate(run).model_dump(),
        signals=[ScanAuthenticationSignalRead.model_validate(row) for row in signals],
        findings=[ScanAuthenticationFindingRead.model_validate(row) for row in findings],
        artifacts=artifact_reads,
        issues=[ScanAuthenticationIssueRead.model_validate(row) for row in issues],
        history=[ScanAuthenticationHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=lineage.get("original_scan_checksum"),
        normalization_checksum=lineage.get("normalization_checksum"),
        boundary_checksum=lineage.get("boundary_checksum"),
        ocr_checksum=lineage.get("ocr_checksum"),
        reconciliation_checksum=lineage.get("reconciliation_checksum"),
        visual_evidence_checksum=lineage.get("visual_evidence_checksum"),
        historical_comparison_checksum=lineage.get("historical_comparison_checksum"),
        review_checksum=lineage.get("review_checksum"),
        source_preview_data_url=_load_source_preview(settings, context.source_artifact) if context.source_artifact else None,
        review_flag_count=len(output.get("review_flags") or []),
    )


def run_scan_authentication_assistance(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanAuthenticationRunCreate,
) -> tuple[ScanAuthenticationRunDetail, bool]:
    context = _load_context(session, owner_user_id=owner_user_id, payload=payload)
    signal_drafts = [
        *evaluate_identity_consistency(context),
        *evaluate_metadata_consistency(context),
        *evaluate_scan_lineage_integrity(context),
        *evaluate_historical_consistency(context),
        *evaluate_visual_evidence_consistency(context),
        *evaluate_review_consistency(context),
    ]
    signal_drafts = sorted(
        signal_drafts,
        key=lambda row: (
            row.signal_category,
            row.signal_type,
            row.signal_status,
            -row.confidence_score,
            row.source_system,
            row.source_record_id or 0,
        ),
    )
    finding_drafts, issue_drafts = generate_authentication_findings(signal_drafts)
    review_flags = [
        {
            "signal_type": row.signal_type,
            "signal_status": row.signal_status,
            "confidence_score": row.confidence_score,
        }
        for row in signal_drafts
        if row.signal_status in {"NEEDS_REVIEW", "CONFLICT_DETECTED", "INCONCLUSIVE"}
    ]
    signal_payloads = [
        {
            "signal_type": row.signal_type,
            "signal_category": row.signal_category,
            "signal_status": row.signal_status,
            "confidence_score": row.confidence_score,
            "source_system": row.source_system,
            "source_record_id": row.source_record_id,
            "measurement_json": row.measurement_json,
            "metadata_json": row.metadata_json,
        }
        for row in signal_drafts
    ]
    finding_payloads = [
        {
            "finding_type": row.finding_type,
            "finding_status": row.finding_status,
            "confidence_score": row.confidence_score,
            "review_priority": row.review_priority,
            "finding_text": row.finding_text,
            "source_signal_ids_json": row.source_signal_ids,
            "metadata_json": row.metadata_json,
        }
        for row in finding_drafts
    ]
    issue_payloads = [
        {
            "issue_type": row.issue_type,
            "severity": row.severity,
            "issue_message": row.issue_message,
            "metadata_json": row.metadata_json,
        }
        for row in sorted(issue_drafts, key=lambda row: (row.issue_type, row.severity, row.issue_message))
    ]
    lineage = _lineage(context)
    provisional_manifest, _ = build_authentication_manifest(
        lineage=lineage,
        signals=signal_payloads,
        findings=finding_payloads,
        review_flags=review_flags,
        issues=issue_payloads,
        artifact_refs=[],
    )
    artifact_drafts = [
        _ArtifactDraft("AUTHENTICATION_SUPPORT_REPORT", _serialize_json_artifact({"findings": finding_payloads, "review_flags": review_flags}), {"format": "json"}, ".json"),
        _ArtifactDraft("AUTHENTICATION_SIGNAL_EXPORT", _serialize_json_artifact(signal_payloads), {"format": "json"}, ".json"),
        _ArtifactDraft("AUTHENTICATION_REVIEW_FLAGS", _serialize_json_artifact(review_flags), {"format": "json"}, ".json"),
        _ArtifactDraft("AUTHENTICATION_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json"),
        _ArtifactDraft("AUTHENTICATION_DEBUG_PREVIEW", _build_debug_preview(settings, context, signal_drafts), {"format": "png"}, ".png"),
    ]
    artifact_refs = [{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in artifact_drafts]
    manifest, final_checksum = build_authentication_manifest(
        lineage=lineage,
        signals=signal_payloads,
        findings=finding_payloads,
        review_flags=review_flags,
        issues=issue_payloads,
        artifact_refs=artifact_refs,
    )
    existing = session.exec(
        select(ScanAuthenticationRun)
        .where(ScanAuthenticationRun.owner_user_id == owner_user_id, ScanAuthenticationRun.authentication_checksum == final_checksum)
        .order_by(col(ScanAuthenticationRun.id).desc())
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    status = "INCONCLUSIVE" if any(row["finding_status"] in {"CONFLICT", "INCONCLUSIVE", "REVIEW_REQUIRED"} for row in finding_payloads) else "COMPLETE"
    run = ScanAuthenticationRun(
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        reconciliation_run_id=int(context.reconciliation_run.id or 0) if context.reconciliation_run else None,
        visual_evidence_run_id=int(context.visual_run.id or 0) if context.visual_run else None,
        historical_comparison_run_id=int(context.historical_run.id or 0) if context.historical_run else None,
        review_session_id=int(context.review_session.id or 0) if context.review_session else None,
        source_checksum=context.visual_run.visual_evidence_checksum if context.visual_run else context.scan_image.sha256_checksum,
        authentication_checksum=final_checksum,
        authentication_status=status,
        engine_version=ENGINE_VERSION,
        rubric_version=RUBRIC_VERSION,
        input_manifest_json={
            "scan_image_id": payload.scan_image_id,
            "reconciliation_run_id": payload.reconciliation_run_id,
            "visual_evidence_run_id": payload.visual_evidence_run_id,
            "historical_comparison_run_id": payload.historical_comparison_run_id,
            "review_session_id": payload.review_session_id,
        },
        output_manifest_json=manifest,
    )
    session.add(run)
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        authentication_run_id=int(run.id or 0),
        event_type="AUTHENTICATION_ASSISTANCE_STARTED",
        event_message="Started deterministic authentication assistance run.",
        metadata_json={"signal_count": len(signal_payloads)},
    )
    signal_rows: list[ScanAuthenticationSignal] = []
    for rank, row in enumerate(signal_drafts, start=1):
        signal_row = ScanAuthenticationSignal(
            owner_user_id=owner_user_id,
            authentication_run_id=int(run.id or 0),
            signal_rank=rank,
            signal_type=row.signal_type,
            signal_category=row.signal_category,
            signal_status=row.signal_status,
            confidence_score=row.confidence_score,
            source_system=row.source_system,
            source_record_id=row.source_record_id,
            measurement_json=row.measurement_json,
            metadata_json=row.metadata_json,
        )
        session.add(signal_row)
        signal_rows.append(signal_row)
    session.flush()
    for rank, row in enumerate(finding_drafts, start=1):
        mapped_ids = [int(signal_rows[index - 1].id or 0) for index in row.source_signal_ids if 0 < index <= len(signal_rows)]
        session.add(
            ScanAuthenticationFinding(
                owner_user_id=owner_user_id,
                authentication_run_id=int(run.id or 0),
                finding_rank=rank,
                finding_type=row.finding_type,
                finding_status=row.finding_status,
                confidence_score=row.confidence_score,
                review_priority=row.review_priority,
                finding_text=row.finding_text,
                source_signal_ids_json=mapped_ids,
                metadata_json=row.metadata_json,
            )
        )
    for row in issue_drafts:
        session.add(
            ScanAuthenticationIssue(
                owner_user_id=owner_user_id,
                authentication_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )
    session.flush()
    _persist_artifacts(
        session,
        settings,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        authentication_run_id=int(run.id or 0),
        drafts=artifact_drafts,
    )
    session.flush()
    run.completed_at = utc_now()
    session.add(run)
    _append_history(
        session,
        owner_user_id=owner_user_id,
        authentication_run_id=int(run.id or 0),
        event_type="AUTHENTICATION_ASSISTANCE_COMPLETED",
        event_message="Completed deterministic authentication assistance run.",
        metadata_json={"authentication_checksum": final_checksum, "finding_count": len(finding_payloads)},
    )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_authentication_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanAuthenticationRunDetail:
    row = session.get(ScanAuthenticationRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Authentication assistance run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_authentication_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanAuthenticationArtifactRead:
    row = session.get(ScanAuthenticationArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Authentication assistance artifact not found.")
    return ScanAuthenticationArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _run_list_response(rows: list[ScanAuthenticationRun], *, limit: int, offset: int, total_items: int) -> ScanAuthenticationRunListResponse:
    return ScanAuthenticationRunListResponse(
        items=[ScanAuthenticationRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts={key: sum(1 for row in rows if row.authentication_status == key) for key in sorted({row.authentication_status for row in rows})},
        unresolved_conflict_count=sum(
            1
            for row in rows
            if any(finding.get("finding_status") == "CONFLICT" for finding in (row.output_manifest_json.get("findings") or []))
        ),
        review_required_count=sum(
            1
            for row in rows
            if any(finding.get("finding_status") == "REVIEW_REQUIRED" for finding in (row.output_manifest_json.get("findings") or []))
        ),
    )


def list_scan_authentication_runs_owner(session: Session, *, owner_user_id: int, scan_image_id: int | None, limit: int, offset: int) -> ScanAuthenticationRunListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationRun).where(ScanAuthenticationRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanAuthenticationRun).where(ScanAuthenticationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanAuthenticationRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanAuthenticationRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationRun.created_at).desc(), col(ScanAuthenticationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_authentication_runs_ops(session: Session, *, owner_user_id: int | None, scan_image_id: int | None, limit: int, offset: int) -> ScanAuthenticationRunListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationRun)
    count_stmt = select(func.count()).select_from(ScanAuthenticationRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanAuthenticationRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanAuthenticationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanAuthenticationRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanAuthenticationRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationRun.created_at).desc(), col(ScanAuthenticationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_authentication_signals_owner(session: Session, *, owner_user_id: int, run_id: int | None, limit: int, offset: int) -> ScanAuthenticationSignalListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationSignal).where(ScanAuthenticationSignal.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanAuthenticationSignal).where(ScanAuthenticationSignal.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanAuthenticationSignal.authentication_run_id == run_id)
        count_stmt = count_stmt.where(ScanAuthenticationSignal.authentication_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationSignal.signal_rank), col(ScanAuthenticationSignal.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanAuthenticationSignalListResponse(
        items=[ScanAuthenticationSignalRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        signal_status_counts={key: sum(1 for row in rows if row.signal_status == key) for key in sorted({row.signal_status for row in rows})},
    )


def list_scan_authentication_findings_owner(session: Session, *, owner_user_id: int, run_id: int | None, limit: int, offset: int) -> ScanAuthenticationFindingListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationFinding).where(ScanAuthenticationFinding.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanAuthenticationFinding).where(ScanAuthenticationFinding.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanAuthenticationFinding.authentication_run_id == run_id)
        count_stmt = count_stmt.where(ScanAuthenticationFinding.authentication_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationFinding.finding_rank), col(ScanAuthenticationFinding.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanAuthenticationFindingListResponse(
        items=[ScanAuthenticationFindingRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        finding_status_counts={key: sum(1 for row in rows if row.finding_status == key) for key in sorted({row.finding_status for row in rows})},
        review_priority_counts={key: sum(1 for row in rows if row.review_priority == key) for key in sorted({row.review_priority for row in rows})},
    )


def list_scan_authentication_issues_owner(session: Session, *, owner_user_id: int, run_id: int | None, limit: int, offset: int) -> ScanAuthenticationIssueListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationIssue).where(ScanAuthenticationIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanAuthenticationIssue).where(ScanAuthenticationIssue.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanAuthenticationIssue.authentication_run_id == run_id)
        count_stmt = count_stmt.where(ScanAuthenticationIssue.authentication_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanAuthenticationIssueListResponse(
        items=[ScanAuthenticationIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_authentication_issues_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanAuthenticationIssueListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationIssue)
    count_stmt = select(func.count()).select_from(ScanAuthenticationIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanAuthenticationIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanAuthenticationIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanAuthenticationIssueListResponse(
        items=[ScanAuthenticationIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_authentication_failures_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanAuthenticationRunListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    stmt = select(ScanAuthenticationRun).where(ScanAuthenticationRun.authentication_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanAuthenticationRun).where(ScanAuthenticationRun.authentication_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanAuthenticationRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanAuthenticationRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanAuthenticationRun.created_at).desc(), col(ScanAuthenticationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_authentication_conflicts_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanAuthenticationRunListResponse:
    limit, offset = clamp_scan_authentication_pagination(limit=limit, offset=offset)
    candidate_rows = session.exec(
        select(ScanAuthenticationRun).order_by(col(ScanAuthenticationRun.created_at).desc(), col(ScanAuthenticationRun.id).desc())
    ).all()
    if owner_user_id is not None:
        candidate_rows = [row for row in candidate_rows if int(row.owner_user_id) == owner_user_id]
    rows = [row for row in candidate_rows if any(finding.get("finding_status") == "CONFLICT" for finding in (row.output_manifest_json.get("findings") or []))]
    rows = rows[offset : offset + limit]
    total_items = len([row for row in candidate_rows if any(finding.get("finding_status") == "CONFLICT" for finding in (row.output_manifest_json.get("findings") or []))])
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)
