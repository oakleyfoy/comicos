from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryRun,
    ScanDefectRun,
    ScanGradingAssistanceRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanReconciliationRun,
    ScanReviewArtifact,
    ScanReviewDecision,
    ScanReviewEvidenceAction,
    ScanReviewHistory,
    ScanReviewIssue,
    ScanReviewNote,
    ScanReviewSession,
    ScanVisualEvidenceArtifact,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_review import (
    ScanReviewArtifactRead,
    ScanReviewDecisionCreate,
    ScanReviewDecisionRead,
    ScanReviewEvidenceActionCreate,
    ScanReviewEvidenceActionRead,
    ScanReviewHistoryRead,
    ScanReviewIssueListResponse,
    ScanReviewIssueRead,
    ScanReviewNoteCreate,
    ScanReviewNoteRead,
    ScanReviewSessionCreate,
    ScanReviewSessionDetail,
    ScanReviewSessionListResponse,
    ScanReviewSessionRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-14-v1"
_PREVIEW_MAX = 420


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
    from app.models.scan_review import utc_now as _utc_now

    return _utc_now()


def clamp_scan_review_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_review_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_review_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan review storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    review_session_id: int,
    artifact_type: str,
    artifact_checksum: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    short = artifact_checksum[:12]
    return f"scan-review/{owner_user_id}/{scan_image_id}/{review_session_id}/{safe_type}-{short}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_review_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanReviewArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_review_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _resolve_visual_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    visual_evidence_run_id: int | None,
) -> ScanVisualEvidenceRun | None:
    stmt = select(ScanVisualEvidenceRun).where(
        ScanVisualEvidenceRun.owner_user_id == owner_user_id,
        ScanVisualEvidenceRun.scan_image_id == scan_image_id,
        ScanVisualEvidenceRun.evidence_status == "COMPLETE",
    )
    if visual_evidence_run_id is not None:
        stmt = stmt.where(ScanVisualEvidenceRun.id == visual_evidence_run_id)
    return session.exec(stmt.order_by(col(ScanVisualEvidenceRun.id).desc())).first()


def _resolve_grading_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    grading_assistance_run_id: int | None,
) -> ScanGradingAssistanceRun | None:
    stmt = select(ScanGradingAssistanceRun).where(
        ScanGradingAssistanceRun.owner_user_id == owner_user_id,
        ScanGradingAssistanceRun.scan_image_id == scan_image_id,
        ScanGradingAssistanceRun.assistance_status == "COMPLETE",
    )
    if grading_assistance_run_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.id == grading_assistance_run_id)
    return session.exec(stmt.order_by(col(ScanGradingAssistanceRun.id).desc())).first()


def _resolve_reconciliation_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    reconciliation_run_id: int | None,
) -> ScanReconciliationRun | None:
    stmt = select(ScanReconciliationRun).where(
        ScanReconciliationRun.owner_user_id == owner_user_id,
        ScanReconciliationRun.scan_image_id == scan_image_id,
        ScanReconciliationRun.reconciliation_status != "FAILED",
    )
    if reconciliation_run_id is not None:
        stmt = stmt.where(ScanReconciliationRun.id == reconciliation_run_id)
    return session.exec(stmt.order_by(col(ScanReconciliationRun.id).desc())).first()


def _resolve_defect_context(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    visual_run: ScanVisualEvidenceRun | None,
) -> tuple[ScanDefectRun | None, ScanBoundaryRun | None, ScanNormalizationRun | None, ScanNormalizationArtifact | None]:
    defect_run_id = None
    if visual_run is not None:
        lineage = dict((visual_run.output_manifest_json or {}).get("upstream_lineage") or {})
        if lineage.get("defect_checksum"):
            defect = session.exec(
                select(ScanDefectRun)
                .where(
                    ScanDefectRun.owner_user_id == owner_user_id,
                    ScanDefectRun.scan_image_id == scan_image_id,
                    ScanDefectRun.defect_checksum == lineage["defect_checksum"],
                )
                .order_by(col(ScanDefectRun.id).desc())
            ).first()
            if defect is not None:
                defect_run_id = int(defect.id or 0)
    defect_run = (
        session.get(ScanDefectRun, defect_run_id)
        if defect_run_id is not None
        else session.exec(
            select(ScanDefectRun)
            .where(
                ScanDefectRun.owner_user_id == owner_user_id,
                ScanDefectRun.scan_image_id == scan_image_id,
                ScanDefectRun.defect_status == "COMPLETE",
            )
            .order_by(col(ScanDefectRun.id).desc())
        ).first()
    )
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    normalization_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    return defect_run, boundary_run, normalization_run, source_artifact


def build_review_snapshot(
    *,
    scan_image: ScanImage | None,
    visual_run: ScanVisualEvidenceRun | None,
    grading_run: ScanGradingAssistanceRun | None,
    reconciliation_run: ScanReconciliationRun | None,
    lineage: dict[str, Any],
    open_review_flags: list[dict[str, Any]],
    open_issues: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    snapshot = {
        "scan_image": {
            "scan_image_id": int(scan_image.id or 0) if scan_image else None,
            "sha256_checksum": scan_image.sha256_checksum if scan_image else None,
        },
        "reconciliation_summary": {
            "reconciliation_run_id": int(reconciliation_run.id or 0) if reconciliation_run else None,
            "reconciliation_status": reconciliation_run.reconciliation_status if reconciliation_run else None,
            "final_confidence_score": float((reconciliation_run.output_manifest_json or {}).get("final_confidence_score") or 0.0)
            if reconciliation_run
            else None,
        },
        "visual_evidence_summary": {
            "visual_evidence_run_id": int(visual_run.id or 0) if visual_run else None,
            "evidence_status": visual_run.evidence_status if visual_run else None,
            "package_count": len((visual_run.output_manifest_json or {}).get("packages") or []) if visual_run else 0,
            "issue_count": len((visual_run.output_manifest_json or {}).get("issues") or []) if visual_run else 0,
        },
        "grading_assistance_summary": {
            "grading_assistance_run_id": int(grading_run.id or 0) if grading_run else None,
            "assistance_status": grading_run.assistance_status if grading_run else None,
            "overall_support": dict((grading_run.output_manifest_json or {}).get("overall_support") or {}) if grading_run else {},
            "review_flags": open_review_flags,
        },
        "issues_requiring_attention": open_issues,
        "upstream_checksum_lineage": lineage,
    }
    return snapshot, _hash_payload(snapshot)


def _load_session_children(
    session: Session,
    *,
    review_session_id: int,
) -> tuple[list[ScanReviewDecision], list[ScanReviewNote], list[ScanReviewEvidenceAction], list[ScanReviewArtifact], list[ScanReviewIssue], list[ScanReviewHistory]]:
    decisions = session.exec(
        select(ScanReviewDecision).where(ScanReviewDecision.review_session_id == review_session_id).order_by(col(ScanReviewDecision.id))
    ).all()
    notes = session.exec(
        select(ScanReviewNote).where(ScanReviewNote.review_session_id == review_session_id).order_by(col(ScanReviewNote.id))
    ).all()
    actions = session.exec(
        select(ScanReviewEvidenceAction).where(ScanReviewEvidenceAction.review_session_id == review_session_id).order_by(col(ScanReviewEvidenceAction.id))
    ).all()
    artifacts = session.exec(
        select(ScanReviewArtifact).where(ScanReviewArtifact.review_session_id == review_session_id).order_by(col(ScanReviewArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanReviewIssue).where(ScanReviewIssue.review_session_id == review_session_id).order_by(col(ScanReviewIssue.id))
    ).all()
    history = session.exec(
        select(ScanReviewHistory).where(ScanReviewHistory.review_session_id == review_session_id).order_by(col(ScanReviewHistory.id))
    ).all()
    return decisions, notes, actions, artifacts, issues, history


def _build_issues(
    *,
    snapshot: dict[str, Any],
    decisions: list[ScanReviewDecision],
    actions: list[ScanReviewEvidenceAction],
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    review_clearance = any(
        row.decision_type == "REVIEW_REQUIRED_CLEARANCE" and row.decision_status in {"ACCEPTED", "OVERRIDDEN", "NOT_APPLICABLE"}
        for row in decisions
    )
    if snapshot["visual_evidence_summary"]["visual_evidence_run_id"] is None:
        issues.append(_IssueDraft("VISUAL_EVIDENCE_MISSING", "WARNING", "Visual evidence package is not available for this review session.", {}))
    if snapshot["grading_assistance_summary"]["grading_assistance_run_id"] is None:
        issues.append(_IssueDraft("GRADING_ASSISTANCE_MISSING", "INFO", "Grading assistance is not available for this review session.", {}))
    if snapshot["reconciliation_summary"]["reconciliation_run_id"] is None:
        issues.append(_IssueDraft("RECONCILIATION_MISSING", "INFO", "Reconciliation context is not available for this review session.", {}))
    if snapshot["grading_assistance_summary"]["review_flags"] and not review_clearance:
        issues.append(
            _IssueDraft(
                "REVIEW_REQUIRED_FLAGS_OPEN",
                "WARNING",
                "One or more grading-support review-required flags remain open.",
                {"flag_count": len(snapshot["grading_assistance_summary"]["review_flags"])},
            )
        )
    if snapshot["visual_evidence_summary"]["issue_count"] and any(
        row.get("issue_type") == "LOW_EVIDENCE_CONFIDENCE" for row in snapshot["issues_requiring_attention"]
    ):
        issues.append(_IssueDraft("LOW_SCAN_CONFIDENCE", "WARNING", "Upstream evidence confidence is low for some review materials.", {}))
    if any(row.get("issue_type") == "EVIDENCE_CONFLICT" for row in snapshot["issues_requiring_attention"]):
        issues.append(_IssueDraft("EVIDENCE_CONFLICT_UNRESOLVED", "WARNING", "Evidence conflicts remain unresolved in the upstream review set.", {}))
    identity_decisions = [row for row in decisions if row.decision_type == "IDENTITY_CONFIRMATION"]
    if snapshot["reconciliation_summary"]["reconciliation_run_id"] is not None and not identity_decisions:
        issues.append(_IssueDraft("IDENTITY_UNCONFIRMED", "WARNING", "Identity has not yet been confirmed or rejected by the reviewer.", {}))
    if any(row.action_type == "REQUEST_RESCAN" and row.action_status == "ACTIVE" for row in actions):
        issues.append(_IssueDraft("RESCAN_REQUESTED", "INFO", "A rescan request is still active for this review session.", {}))
    if any(row.issue_type in {"REVIEW_REQUIRED_FLAGS_OPEN", "IDENTITY_UNCONFIRMED"} for row in issues):
        issues.append(_IssueDraft("REVIEW_BLOCKED", "ERROR", "Review completion is blocked until required review items are addressed.", {}))
    unique: dict[tuple[str, str], _IssueDraft] = {}
    for row in issues:
        unique[(row.issue_type, row.issue_message)] = row
    return list(unique.values())


def _derive_status(
    *,
    current_status: str,
    issues: list[_IssueDraft],
    actions: list[ScanReviewEvidenceAction],
    completing: bool = False,
) -> str:
    if completing:
        if any(row.issue_type == "REVIEW_BLOCKED" for row in issues):
            raise HTTPException(status_code=409, detail="Review is blocked and cannot be completed yet.")
        if any(row.action_type == "REQUEST_RESCAN" and row.action_status == "ACTIVE" for row in actions):
            raise HTTPException(status_code=409, detail="Active rescan requests must be cleared before completion.")
        return "REVIEW_COMPLETE"
    if any(row.issue_type == "REVIEW_BLOCKED" for row in issues):
        return "REVIEW_BLOCKED"
    if any(row.action_type == "REQUEST_RESCAN" and row.action_status == "ACTIVE" for row in actions):
        return "NEEDS_MORE_SCAN_DATA"
    if current_status == "NOT_STARTED":
        return "IN_REVIEW"
    return current_status


def build_review_manifest(
    *,
    lineage: dict[str, Any],
    review_snapshot: dict[str, Any],
    decisions: list[ScanReviewDecision],
    notes: list[ScanReviewNote],
    actions: list[ScanReviewEvidenceAction],
    issues: list[_IssueDraft],
    artifact_refs: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "upstream_lineage": lineage,
        "review_snapshot": review_snapshot,
        "decisions": [
            {
                "decision_type": row.decision_type,
                "decision_status": row.decision_status,
                "decision_value": row.decision_value,
                "confidence_score": row.confidence_score,
                "reason_text": row.reason_text,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat(),
            }
            for row in decisions
        ],
        "notes": [
            {
                "note_type": row.note_type,
                "note_text": row.note_text,
                "source_system": row.source_system,
                "source_record_id": row.source_record_id,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat(),
            }
            for row in notes
        ],
        "evidence_actions": [
            {
                "source_system": row.source_system,
                "source_record_id": row.source_record_id,
                "action_type": row.action_type,
                "action_status": row.action_status,
                "reason_text": row.reason_text,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at.isoformat(),
            }
            for row in actions
        ],
        "issues": [
            {
                "issue_type": row.issue_type,
                "severity": row.severity,
                "issue_message": row.issue_message,
                "metadata_json": row.metadata_json,
            }
            for row in issues
        ],
        "artifact_refs": artifact_refs,
    }
    return manifest, _hash_payload(manifest)


def _build_debug_preview(settings: Settings, source_artifact: ScanNormalizationArtifact | None) -> bytes:
    if source_artifact is None:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (18, 18, 22)).save(buf, format="PNG")
        return buf.getvalue()
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = image_fp.copy().convert("RGB")
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (18, 18, 22)).save(buf, format="PNG")
        return buf.getvalue()
    image.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _persist_artifacts(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    scan_image_id: int,
    review_session_id: int,
    drafts: list[_ArtifactDraft],
) -> None:
    for row in drafts:
        artifact_checksum = _sha256_bytes(row.body)
        exists = session.exec(
            select(ScanReviewArtifact).where(
                ScanReviewArtifact.review_session_id == review_session_id,
                ScanReviewArtifact.artifact_type == row.artifact_type,
                ScanReviewArtifact.artifact_checksum == artifact_checksum,
            )
        ).first()
        if exists is not None:
            continue
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=scan_image_id,
            review_session_id=review_session_id,
            artifact_type=row.artifact_type,
            artifact_checksum=artifact_checksum,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanReviewArtifact(
                owner_user_id=owner_user_id,
                review_session_id=review_session_id,
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=artifact_checksum,
                metadata_json=row.metadata_json,
            )
        )


def _upsert_issues(
    session: Session,
    *,
    owner_user_id: int,
    review_session_id: int,
    issues: list[_IssueDraft],
) -> None:
    existing = session.exec(select(ScanReviewIssue).where(ScanReviewIssue.review_session_id == review_session_id)).all()
    for row in existing:
        session.delete(row)
    session.flush()
    for row in issues:
        session.add(
            ScanReviewIssue(
                owner_user_id=owner_user_id,
                review_session_id=review_session_id,
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )


def _append_history(
    session: Session,
    *,
    owner_user_id: int,
    review_session_id: int,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> None:
    session.add(
        ScanReviewHistory(
            owner_user_id=owner_user_id,
            review_session_id=review_session_id,
            event_type=event_type,
            event_message=event_message,
            event_checksum=_hash_payload(
                {
                    "review_session_id": review_session_id,
                    "event_type": event_type,
                    "event_message": event_message,
                    "metadata_json": metadata_json,
                }
            ),
            metadata_json=metadata_json,
        )
    )


def _refresh_session_state(
    session: Session,
    settings: Settings,
    *,
    session_row: ScanReviewSession,
    complete: bool = False,
) -> None:
    decisions, notes, actions, _, _, _ = _load_session_children(session, review_session_id=int(session_row.id or 0))
    scan_image = session.get(ScanImage, int(session_row.scan_image_id))
    visual_run = session.get(ScanVisualEvidenceRun, int(session_row.visual_evidence_run_id)) if session_row.visual_evidence_run_id else None
    grading_run = session.get(ScanGradingAssistanceRun, int(session_row.grading_assistance_run_id)) if session_row.grading_assistance_run_id else None
    reconciliation_run = session.get(ScanReconciliationRun, int(session_row.reconciliation_run_id)) if session_row.reconciliation_run_id else None
    defect_run, boundary_run, normalization_run, source_artifact = _resolve_defect_context(
        session,
        owner_user_id=int(session_row.owner_user_id),
        scan_image_id=int(session_row.scan_image_id),
        visual_run=visual_run,
    )
    lineage = {
        "original_scan_checksum": scan_image.sha256_checksum if scan_image else None,
        "normalization_checksum": normalization_run.normalization_checksum if normalization_run else None,
        "boundary_checksum": boundary_run.boundary_checksum if boundary_run else None,
        "ocr_checksum": (visual_run.output_manifest_json or {}).get("upstream_lineage", {}).get("ocr_checksum") if visual_run else None,
        "reconciliation_checksum": reconciliation_run.reconciliation_checksum if reconciliation_run else None,
        "defect_checksum": defect_run.defect_checksum if defect_run else None,
        "aggregation_checksum": (visual_run.output_manifest_json or {}).get("upstream_lineage", {}).get("aggregation_checksum") if visual_run else None,
        "grading_assistance_checksum": grading_run.grading_assistance_checksum if grading_run else None,
        "visual_evidence_checksum": visual_run.visual_evidence_checksum if visual_run else None,
    }
    visual_issues = list((visual_run.output_manifest_json or {}).get("issues") or []) if visual_run else []
    review_flags = list((grading_run.output_manifest_json or {}).get("review_flags") or []) if grading_run else []
    snapshot, snapshot_checksum = build_review_snapshot(
        scan_image=scan_image,
        visual_run=visual_run,
        grading_run=grading_run,
        reconciliation_run=reconciliation_run,
        lineage=lineage,
        open_review_flags=review_flags,
        open_issues=visual_issues,
    )
    issues = _build_issues(snapshot=snapshot, decisions=decisions, actions=actions)
    review_status = _derive_status(current_status=session_row.review_status, issues=issues, actions=actions, completing=complete)
    manifest, review_checksum = build_review_manifest(
        lineage=lineage,
        review_snapshot=snapshot,
        decisions=decisions,
        notes=notes,
        actions=actions,
        issues=issues,
        artifact_refs=[],
    )
    session_row.snapshot_checksum = snapshot_checksum
    session_row.review_checksum = review_checksum
    session_row.review_status = review_status
    session_row.output_manifest_json = manifest
    session_row.updated_at = utc_now()
    if complete:
        session_row.completed_at = utc_now()
    _upsert_issues(session, owner_user_id=int(session_row.owner_user_id), review_session_id=int(session_row.id or 0), issues=issues)
    artifact_drafts = [
        _ArtifactDraft("REVIEW_SNAPSHOT", _serialize_json_artifact(snapshot), {"format": "json"}, ".json"),
        _ArtifactDraft("REVIEW_MANIFEST", _serialize_json_artifact(manifest), {"format": "json"}, ".json"),
        _ArtifactDraft("REVIEW_DEBUG_PREVIEW", _build_debug_preview(settings, source_artifact), {"format": "png"}, ".png"),
    ]
    if decisions:
        artifact_drafts.append(
            _ArtifactDraft(
                "REVIEW_DECISION_EXPORT",
                _serialize_json_artifact([ScanReviewDecisionRead.model_validate(row).model_dump(mode="json") for row in decisions]),
                {"format": "json"},
                ".json",
            )
        )
    if notes:
        artifact_drafts.append(
            _ArtifactDraft(
                "REVIEW_NOTES_EXPORT",
                _serialize_json_artifact([ScanReviewNoteRead.model_validate(row).model_dump(mode="json") for row in notes]),
                {"format": "json"},
                ".json",
            )
        )
    _persist_artifacts(
        session,
        settings,
        owner_user_id=int(session_row.owner_user_id),
        scan_image_id=int(session_row.scan_image_id),
        review_session_id=int(session_row.id or 0),
        drafts=artifact_drafts,
    )
    session.flush()
    artifacts = session.exec(select(ScanReviewArtifact).where(ScanReviewArtifact.review_session_id == session_row.id).order_by(col(ScanReviewArtifact.id))).all()
    manifest["artifact_refs"] = [
        {"artifact_type": row.artifact_type, "artifact_checksum": row.artifact_checksum}
        for row in artifacts
    ]
    session_row.output_manifest_json = manifest
    session_row.review_checksum = _hash_payload(manifest)
    session_row.updated_at = utc_now()
    session.add(session_row)


def _detail_from_session(session: Session, settings: Settings, row: ScanReviewSession) -> ScanReviewSessionDetail:
    decisions, notes, actions, artifacts, issues, history = _load_session_children(session, review_session_id=int(row.id or 0))
    visual_run = session.get(ScanVisualEvidenceRun, int(row.visual_evidence_run_id)) if row.visual_evidence_run_id else None
    defect_run, boundary_run, normalization_run, source_artifact = _resolve_defect_context(
        session,
        owner_user_id=int(row.owner_user_id),
        scan_image_id=int(row.scan_image_id),
        visual_run=visual_run,
    )
    scan_image = session.get(ScanImage, int(row.scan_image_id))
    art_reads = [
        ScanReviewArtifactRead.model_validate(item).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, item)})
        for item in artifacts
    ]
    lineage = dict((row.output_manifest_json or {}).get("upstream_lineage") or {})
    return ScanReviewSessionDetail(
        **ScanReviewSessionRead.model_validate(row).model_dump(),
        decisions=[ScanReviewDecisionRead.model_validate(item) for item in decisions],
        notes=[ScanReviewNoteRead.model_validate(item) for item in notes],
        evidence_actions=[ScanReviewEvidenceActionRead.model_validate(item) for item in actions],
        artifacts=art_reads,
        issues=[ScanReviewIssueRead.model_validate(item) for item in issues],
        history=[ScanReviewHistoryRead.model_validate(item) for item in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=normalization_run.normalization_checksum if normalization_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        ocr_checksum=lineage.get("ocr_checksum"),
        reconciliation_checksum=lineage.get("reconciliation_checksum"),
        defect_checksum=lineage.get("defect_checksum"),
        aggregation_checksum=lineage.get("aggregation_checksum"),
        grading_assistance_checksum=lineage.get("grading_assistance_checksum"),
        visual_evidence_checksum=lineage.get("visual_evidence_checksum"),
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        review_snapshot=dict((row.output_manifest_json or {}).get("review_snapshot") or {}),
    )


def create_scan_review_session(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    reviewer_user_id: int | None,
    payload: ScanReviewSessionCreate,
) -> tuple[ScanReviewSessionDetail, bool]:
    visual_run = _resolve_visual_run(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        visual_evidence_run_id=payload.visual_evidence_run_id,
    )
    grading_run = _resolve_grading_run(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        grading_assistance_run_id=payload.grading_assistance_run_id,
    )
    reconciliation_run = _resolve_reconciliation_run(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        reconciliation_run_id=payload.reconciliation_run_id,
    )
    defect_run, boundary_run, normalization_run, source_artifact = _resolve_defect_context(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        visual_run=visual_run,
    )
    scan_image = session.get(ScanImage, payload.scan_image_id)
    lineage = {
        "original_scan_checksum": scan_image.sha256_checksum if scan_image else None,
        "normalization_checksum": normalization_run.normalization_checksum if normalization_run else None,
        "boundary_checksum": boundary_run.boundary_checksum if boundary_run else None,
        "ocr_checksum": (visual_run.output_manifest_json or {}).get("upstream_lineage", {}).get("ocr_checksum") if visual_run else None,
        "reconciliation_checksum": reconciliation_run.reconciliation_checksum if reconciliation_run else None,
        "defect_checksum": defect_run.defect_checksum if defect_run else None,
        "aggregation_checksum": (visual_run.output_manifest_json or {}).get("upstream_lineage", {}).get("aggregation_checksum") if visual_run else None,
        "grading_assistance_checksum": grading_run.grading_assistance_checksum if grading_run else None,
        "visual_evidence_checksum": visual_run.visual_evidence_checksum if visual_run else None,
    }
    visual_issues = list((visual_run.output_manifest_json or {}).get("issues") or []) if visual_run else []
    review_flags = list((grading_run.output_manifest_json or {}).get("review_flags") or []) if grading_run else []
    snapshot, snapshot_checksum = build_review_snapshot(
        scan_image=scan_image,
        visual_run=visual_run,
        grading_run=grading_run,
        reconciliation_run=reconciliation_run,
        lineage=lineage,
        open_review_flags=review_flags,
        open_issues=visual_issues,
    )
    existing = session.exec(
        select(ScanReviewSession)
        .where(
            ScanReviewSession.owner_user_id == owner_user_id,
            ScanReviewSession.scan_image_id == payload.scan_image_id,
            ScanReviewSession.snapshot_checksum == snapshot_checksum,
            ScanReviewSession.review_status != "ARCHIVED",
        )
        .order_by(col(ScanReviewSession.id).desc())
    ).first()
    if existing is not None:
        return _detail_from_session(session, settings, existing), False

    manifest, review_checksum = build_review_manifest(
        lineage=lineage,
        review_snapshot=snapshot,
        decisions=[],
        notes=[],
        actions=[],
        issues=[],
        artifact_refs=[],
    )
    row = ScanReviewSession(
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        visual_evidence_run_id=int(visual_run.id or 0) if visual_run else None,
        grading_assistance_run_id=int(grading_run.id or 0) if grading_run else None,
        reconciliation_run_id=int(reconciliation_run.id or 0) if reconciliation_run else None,
        review_status="NOT_STARTED",
        review_checksum=review_checksum,
        snapshot_checksum=snapshot_checksum,
        reviewer_user_id=reviewer_user_id,
        input_manifest_json={
            "scan_image_id": payload.scan_image_id,
            "visual_evidence_run_id": int(visual_run.id or 0) if visual_run else None,
            "grading_assistance_run_id": int(grading_run.id or 0) if grading_run else None,
            "reconciliation_run_id": int(reconciliation_run.id or 0) if reconciliation_run else None,
        },
        output_manifest_json=manifest,
    )
    session.add(row)
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=int(row.id or 0),
        event_type="REVIEW_SESSION_CREATED",
        event_message="Created deterministic scan review session.",
        metadata_json={"snapshot_checksum": snapshot_checksum},
    )
    _refresh_session_state(session, settings, session_row=row)
    session.commit()
    session.refresh(row)
    return _detail_from_session(session, settings, row), True


def _session_for_owner(session: Session, *, owner_user_id: int, review_session_id: int) -> ScanReviewSession:
    row = session.get(ScanReviewSession, review_session_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan review session not found.")
    return row


def record_review_decision(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    review_session_id: int,
    payload: ScanReviewDecisionCreate,
) -> ScanReviewSessionDetail:
    row = _session_for_owner(session, owner_user_id=owner_user_id, review_session_id=review_session_id)
    session.add(
        ScanReviewDecision(
            owner_user_id=owner_user_id,
            review_session_id=review_session_id,
            decision_type=payload.decision_type,
            decision_status=payload.decision_status,
            decision_value=payload.decision_value,
            confidence_score=payload.confidence_score,
            reason_text=payload.reason_text,
            metadata_json=payload.metadata_json,
        )
    )
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=review_session_id,
        event_type="REVIEW_DECISION_RECORDED",
        event_message=f"Recorded {payload.decision_type} decision.",
        metadata_json={"decision_type": payload.decision_type, "decision_status": payload.decision_status},
    )
    _refresh_session_state(session, settings, session_row=row)
    session.commit()
    session.refresh(row)
    return _detail_from_session(session, settings, row)


def record_review_note(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    review_session_id: int,
    payload: ScanReviewNoteCreate,
) -> ScanReviewSessionDetail:
    row = _session_for_owner(session, owner_user_id=owner_user_id, review_session_id=review_session_id)
    session.add(
        ScanReviewNote(
            owner_user_id=owner_user_id,
            review_session_id=review_session_id,
            note_type=payload.note_type,
            note_text=payload.note_text,
            source_system=payload.source_system,
            source_record_id=payload.source_record_id,
            metadata_json=payload.metadata_json,
        )
    )
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=review_session_id,
        event_type="REVIEW_NOTE_RECORDED",
        event_message=f"Recorded {payload.note_type} note.",
        metadata_json={"note_type": payload.note_type},
    )
    _refresh_session_state(session, settings, session_row=row)
    session.commit()
    session.refresh(row)
    return _detail_from_session(session, settings, row)


def record_evidence_action(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    review_session_id: int,
    payload: ScanReviewEvidenceActionCreate,
) -> ScanReviewSessionDetail:
    row = _session_for_owner(session, owner_user_id=owner_user_id, review_session_id=review_session_id)
    session.add(
        ScanReviewEvidenceAction(
            owner_user_id=owner_user_id,
            review_session_id=review_session_id,
            source_system=payload.source_system,
            source_record_id=payload.source_record_id,
            action_type=payload.action_type,
            action_status=payload.action_status,
            reason_text=payload.reason_text,
            metadata_json=payload.metadata_json,
        )
    )
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=review_session_id,
        event_type="REVIEW_EVIDENCE_ACTION_RECORDED",
        event_message=f"Recorded {payload.action_type} evidence action.",
        metadata_json={"action_type": payload.action_type, "source_system": payload.source_system, "source_record_id": payload.source_record_id},
    )
    _refresh_session_state(session, settings, session_row=row)
    session.commit()
    session.refresh(row)
    return _detail_from_session(session, settings, row)


def complete_review_session(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    review_session_id: int,
) -> ScanReviewSessionDetail:
    row = _session_for_owner(session, owner_user_id=owner_user_id, review_session_id=review_session_id)
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=review_session_id,
        event_type="REVIEW_COMPLETION_REQUESTED",
        event_message="Attempted review session completion.",
        metadata_json={},
    )
    _refresh_session_state(session, settings, session_row=row, complete=True)
    _append_history(
        session,
        owner_user_id=owner_user_id,
        review_session_id=review_session_id,
        event_type="REVIEW_SESSION_COMPLETED",
        event_message="Marked review session as complete.",
        metadata_json={"review_status": "REVIEW_COMPLETE"},
    )
    session.commit()
    session.refresh(row)
    return _detail_from_session(session, settings, row)


def get_scan_review_session_owner(session: Session, settings: Settings, *, owner_user_id: int, review_session_id: int) -> ScanReviewSessionDetail:
    row = _session_for_owner(session, owner_user_id=owner_user_id, review_session_id=review_session_id)
    return _detail_from_session(session, settings, row)


def get_scan_review_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanReviewArtifactRead:
    row = session.get(ScanReviewArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan review artifact not found.")
    return ScanReviewArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _session_list_response(rows: list[ScanReviewSession], *, limit: int, offset: int, total_items: int) -> ScanReviewSessionListResponse:
    status_counts = {status: sum(1 for row in rows if row.review_status == status) for status in sorted({row.review_status for row in rows})}
    blocked = sum(1 for row in rows if row.review_status == "REVIEW_BLOCKED")
    rescans = sum(
        1
        for row in rows
        if any(action.get("action_type") == "REQUEST_RESCAN" for action in (row.output_manifest_json.get("evidence_actions") or []))
    )
    completed = sum(1 for row in rows if row.review_status == "REVIEW_COMPLETE")
    return ScanReviewSessionListResponse(
        items=[ScanReviewSessionRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        blocked_review_count=blocked,
        rescan_request_count=rescans,
        completed_review_count=completed,
    )


def list_scan_review_sessions_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewSessionListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    stmt = select(ScanReviewSession).where(ScanReviewSession.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanReviewSession).where(ScanReviewSession.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanReviewSession.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanReviewSession.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanReviewSession.updated_at).desc(), col(ScanReviewSession.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _session_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_review_sessions_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewSessionListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    stmt = select(ScanReviewSession)
    count_stmt = select(func.count()).select_from(ScanReviewSession)
    if owner_user_id is not None:
        stmt = stmt.where(ScanReviewSession.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanReviewSession.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanReviewSession.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanReviewSession.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanReviewSession.updated_at).desc(), col(ScanReviewSession.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _session_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_review_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    review_session_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewIssueListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    stmt = select(ScanReviewIssue).where(ScanReviewIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanReviewIssue).where(ScanReviewIssue.owner_user_id == owner_user_id)
    if review_session_id is not None:
        stmt = stmt.where(ScanReviewIssue.review_session_id == review_session_id)
        count_stmt = count_stmt.where(ScanReviewIssue.review_session_id == review_session_id)
    rows = session.exec(stmt.order_by(col(ScanReviewIssue.created_at), col(ScanReviewIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanReviewIssueListResponse(
        items=[ScanReviewIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_review_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewIssueListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    stmt = select(ScanReviewIssue)
    count_stmt = select(func.count()).select_from(ScanReviewIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanReviewIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanReviewIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanReviewIssue.created_at), col(ScanReviewIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanReviewIssueListResponse(
        items=[ScanReviewIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_review_blocked_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewSessionListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    stmt = select(ScanReviewSession).where(ScanReviewSession.review_status == "REVIEW_BLOCKED")
    count_stmt = select(func.count()).select_from(ScanReviewSession).where(ScanReviewSession.review_status == "REVIEW_BLOCKED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanReviewSession.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanReviewSession.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanReviewSession.updated_at).desc(), col(ScanReviewSession.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _session_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_review_rescans_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanReviewSessionListResponse:
    limit, offset = clamp_scan_review_pagination(limit=limit, offset=offset)
    session_ids = session.exec(
        select(ScanReviewEvidenceAction.review_session_id)
        .where(
            ScanReviewEvidenceAction.action_type == "REQUEST_RESCAN",
            ScanReviewEvidenceAction.action_status == "ACTIVE",
        )
        .order_by(col(ScanReviewEvidenceAction.review_session_id))
    ).all()
    session_ids = sorted({int(item) for item in session_ids})
    if not session_ids:
        return _session_list_response([], limit=limit, offset=offset, total_items=0)
    stmt = select(ScanReviewSession).where(col(ScanReviewSession.id).in_(session_ids))
    if owner_user_id is not None:
        stmt = stmt.where(ScanReviewSession.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanReviewSession.updated_at).desc(), col(ScanReviewSession.id).desc()).offset(offset).limit(limit)).all()
    total_items = len(rows) if owner_user_id is not None else len(session_ids)
    return _session_list_response(rows, limit=limit, offset=offset, total_items=total_items)

