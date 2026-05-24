from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models import (
    CoverImage,
    CoverImageOcrCandidate,
    OcrReplayItem,
    OcrReplayRun,
    User,
)
from app.schemas.ocr_replays import (
    OcrReplayCreatePayload,
    OcrReplayItemRead,
    OcrReplayRunRead,
)
from app.services import cover_images as cover_images_service
from app.services.ocr_pipeline_runtime import PipelineStepTimeout, run_with_thread_deadline
from app.services.cover_images import (
    BARCODE_CANDIDATE_EXTRACTION_VERSION,
    FINGERPRINT_EXTRACTION_VERSION,
    OCR_CANDIDATE_EXTRACTION_VERSION,
    OCR_NORMALIZATION_VERSION,
    OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION,
    _barcode_candidate_signature,
    _build_ocr_candidate_rows,
    _build_ocr_quality_analysis_specs,
    _build_ocr_reconciliation_warning_specs,
    _cover_fingerprint_source,
    _current_metadata_for_cover,
    _derive_barcode_raw_values_from_text,
    _latest_barcode_candidate_rows_for_ocr_result,
    _selected_ocr_candidates_for_reconciliation,
    generate_average_hash,
    generate_difference_hash,
    generate_perceptual_hash,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
    get_latest_cover_image_ocr_result_for_cover,
    list_cover_barcode_candidate_reads_for_cover,
    list_cover_fingerprint_reads_for_cover,
    list_cover_image_ocr_reconciliation_warnings,
    list_cover_ocr_quality_analysis_reads_for_cover,
    normalize_barcode_candidate_value,
    normalize_ocr_text,
    resolve_filesystem_path,
    validate_cover_image_ready_for_ocr,
)
from app.services.metadata_audits import record_metadata_audit
from app.services.processing_errors import classify_exception, structured_error_to_persistent

REPLAY_TYPE_TO_CURRENT_VERSION = {
    "ocr_result": OCR_NORMALIZATION_VERSION,
    "candidate_extraction": OCR_CANDIDATE_EXTRACTION_VERSION,
    "barcode_extraction": BARCODE_CANDIDATE_EXTRACTION_VERSION,
    "fingerprint_generation": FINGERPRINT_EXTRACTION_VERSION,
    "reconciliation_warning": "cover-image-ocr-reconciliation-v1",
    "quality_analysis": OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION,
    "full_pipeline": "full-pipeline-current",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ocr_replay_item_entity_to_read(row: OcrReplayItem) -> OcrReplayItemRead:
    if row.id is None:
        raise ValueError("OCR replay item must be flushed before serialization")
    return OcrReplayItemRead(
        id=row.id,
        replay_run_id=row.replay_run_id,
        cover_image_id=row.cover_image_id,
        status=row.status,  # type: ignore[arg-type]
        previous_snapshot_json=row.previous_snapshot_json or {},
        replay_snapshot_json=row.replay_snapshot_json or {},
        diff_summary_json=row.diff_summary_json or {},
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def ocr_replay_run_entity_to_read(session: Session, row: OcrReplayRun) -> OcrReplayRunRead:
    if row.id is None:
        raise ValueError("OCR replay run must be flushed before serialization")
    items = session.exec(
        select(OcrReplayItem)
        .where(OcrReplayItem.replay_run_id == row.id)
        .order_by(OcrReplayItem.cover_image_id.asc(), OcrReplayItem.id.asc())
    ).all()
    return OcrReplayRunRead(
        id=row.id,
        replay_type=row.replay_type,  # type: ignore[arg-type]
        extraction_version_from=row.extraction_version_from,
        extraction_version_to=row.extraction_version_to,
        status=row.status,  # type: ignore[arg-type]
        total_items=row.total_items,
        changed_items=row.changed_items,
        unchanged_items=row.unchanged_items,
        failed_items=row.failed_items,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_by=row.created_by,
        items=[ocr_replay_item_entity_to_read(item) for item in items],
    )


def _replay_run_snapshot_public(row: OcrReplayRun) -> dict[str, object]:
    return {
        "replay_type": row.replay_type,
        "extraction_version_from": row.extraction_version_from,
        "extraction_version_to": row.extraction_version_to,
        "status": row.status,
        "total_items": row.total_items,
        "changed_items": row.changed_items,
        "unchanged_items": row.unchanged_items,
        "failed_items": row.failed_items,
    }


def _text_summary(value: str | None) -> dict[str, object]:
    text = value or ""
    return {
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "length": len(text),
        "preview": text[:120],
    }


def _list_diff(
    previous_items: list[dict[str, object]],
    replay_items: list[dict[str, object]],
) -> dict[str, object]:
    prev_by_key = {str(item["key"]): item for item in previous_items}
    next_by_key = {str(item["key"]): item for item in replay_items}
    added = sorted(key for key in next_by_key if key not in prev_by_key)
    removed = sorted(key for key in prev_by_key if key not in next_by_key)
    changed: list[dict[str, object]] = []
    unchanged = 0
    for key in sorted(set(prev_by_key) & set(next_by_key)):
        if prev_by_key[key] == next_by_key[key]:
            unchanged += 1
            continue
        changed_fields = sorted(
            field
            for field in set(prev_by_key[key]) | set(next_by_key[key])
            if prev_by_key[key].get(field) != next_by_key[key].get(field)
        )
        changed.append({"key": key, "fields": changed_fields[:10]})
    status = "unchanged" if not added and not removed and not changed else "changed"
    return {
        "status": status,
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "unchanged": unchanged,
        "added_keys": added[:20],
        "removed_keys": removed[:20],
        "changed_keys": changed[:20],
    }


def _flat_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    changed_fields = sorted(
        field
        for field in set(previous_snapshot) | set(replay_snapshot)
        if previous_snapshot.get(field) != replay_snapshot.get(field)
    )
    return {
        "status": "unchanged" if not changed_fields else "changed",
        "changed_fields": changed_fields[:20],
    }


def _pipeline_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    prev_components = dict(previous_snapshot.get("components") or {})
    next_components = dict(replay_snapshot.get("components") or {})
    changed_components: list[dict[str, object]] = []
    unchanged = 0
    for key in sorted(set(prev_components) | set(next_components)):
        prev_component = prev_components.get(key)
        next_component = next_components.get(key)
        if prev_component == next_component:
            unchanged += 1
            continue
        changed_components.append({"component": key})
    return {
        "status": "unchanged" if not changed_components else "changed",
        "changed": len(changed_components),
        "unchanged": unchanged,
        "components": changed_components[:20],
    }


def _summarize_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    shape = str(previous_snapshot.get("shape") or replay_snapshot.get("shape") or "flat")
    if shape == "list":
        return _list_diff(
            list(previous_snapshot.get("items") or []),
            list(replay_snapshot.get("items") or []),
        )
    if shape == "pipeline":
        return _pipeline_diff(previous_snapshot, replay_snapshot)
    return _flat_diff(previous_snapshot, replay_snapshot)


def _bounded_replay_diff_summary(diff_summary: dict[str, object], *, max_chars: int) -> dict[str, object]:
    try:
        dumped = json.dumps(diff_summary, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return {"status": "invalid_diff", "truncated": True, "truncation_reason": "json_error"}
    if len(dumped) <= max_chars:
        return diff_summary
    return {
        "status": str(diff_summary.get("status") or "changed"),
        "truncated": True,
        "max_chars": max_chars,
        "serialized_length": len(dumped),
        "truncation_reason": "replay_diff_size_cap",
    }


def _candidate_snapshot_key(payload: dict[str, object]) -> str:
    return "|".join(
        [
            str(payload.get("candidate_type") or ""),
            str(payload.get("raw_candidate_text") or ""),
            str(payload.get("normalized_candidate_text") or ""),
            str(payload.get("extraction_source") or ""),
        ]
    )


def _barcode_snapshot_key(payload: dict[str, object]) -> str:
    return "|".join(
        [
            str(payload.get("normalized_upc_value") or ""),
            str(payload.get("source_ocr_result_id") or ""),
            str(payload.get("source_ocr_candidate_id") or ""),
        ]
    )


def _fingerprint_snapshot_key(payload: dict[str, object]) -> str:
    return "|".join(
        [
            str(payload.get("fingerprint_type") or ""),
            str(payload.get("derivative_type") or ""),
        ]
    )


def _warning_snapshot_key(payload: dict[str, object]) -> str:
    return "|".join(
        [
            str(payload.get("warning_type") or ""),
            str(payload.get("current_metadata_value") or ""),
            str(payload.get("candidate_value") or ""),
        ]
    )


def _quality_snapshot_key(payload: dict[str, object]) -> str:
    return str(payload.get("quality_type") or "")


def _latest_ocr_result_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    row = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    if row is None:
        return {"shape": "flat", "exists": False}, "none"
    snapshot = {
        "shape": "flat",
        "exists": True,
        "ocr_engine": row.ocr_engine,
        "ocr_engine_version": row.ocr_engine_version,
        "processing_status": row.processing_status,
        "raw_text": _text_summary(row.raw_text),
        "normalized_text": _text_summary(row.normalized_text),
        "confidence_score": row.confidence_score,
        "normalization_version": row.normalization_version,
    }
    version = row.normalization_version or "unknown"
    return snapshot, version


def _replayed_ocr_result_snapshot(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> tuple[dict[str, object], str]:
    cover = validate_cover_image_ready_for_ocr(session, settings=settings, cover_image_id=cover_image_id)
    abs_path = resolve_filesystem_path(settings, cover.storage_path)
    raw_text = cover_images_service._run_tesseract_ocr_with_test_compat(
        abs_path,
        timeout_seconds=float(settings.cover_ocr_tesseract_timeout_seconds),
    )
    normalized_text = normalize_ocr_text(raw_text)
    snapshot = {
        "shape": "flat",
        "exists": True,
        "ocr_engine": "tesseract",
        "ocr_engine_version": cover_images_service.get_tesseract_engine_version(),
        "processing_status": "processed",
        "raw_text": _text_summary(raw_text),
        "normalized_text": _text_summary(normalized_text),
        "confidence_score": None,
        "normalization_version": OCR_NORMALIZATION_VERSION,
    }
    return snapshot, OCR_NORMALIZATION_VERSION


def _latest_candidate_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    latest = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    if latest is None:
        return {"shape": "list", "items": [], "item_count": 0}, "none"
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(
            CoverImageOcrCandidate.cover_image_id == cover_image_id,
            CoverImageOcrCandidate.ocr_result_id == latest.id,
        )
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    items_by_key: dict[str, dict[str, object]] = {}
    versions = {row.extraction_version for row in rows if row.extraction_version}
    for row in rows:
        payload = {
            "candidate_type": row.candidate_type,
            "raw_candidate_text": row.raw_candidate_text,
            "normalized_candidate_text": row.normalized_candidate_text,
            "extraction_source": row.extraction_source,
            "confidence_score": row.confidence_score,
        }
        items_by_key[_candidate_snapshot_key(payload)] = {"key": _candidate_snapshot_key(payload), **payload}
    items = sorted(items_by_key.values(), key=lambda item: str(item["key"]))
    return {
        "shape": "list",
        "item_count": len(items),
        "items": items,
    }, (next(iter(versions)) if len(versions) == 1 else ("mixed" if versions else "none"))


def _replayed_candidate_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    latest = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    if latest is None:
        raise HTTPException(status_code=409, detail="No prior OCR result exists to replay candidates.")
    rows = _build_ocr_candidate_rows(
        cover_image_id=cover_image_id,
        ocr_result_id=latest.id,
        extraction_source="full_cover",
        source_text=latest.raw_text,
        max_candidates=int(get_settings().cover_ocr_max_candidates_per_extract),
    )
    items = []
    for row in rows:
        payload = {
            "candidate_type": row.candidate_type,
            "raw_candidate_text": row.raw_candidate_text,
            "normalized_candidate_text": row.normalized_candidate_text,
            "extraction_source": row.extraction_source,
            "confidence_score": row.confidence_score,
        }
        items.append({"key": _candidate_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, OCR_CANDIDATE_EXTRACTION_VERSION


def _latest_barcode_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    rows = list_cover_barcode_candidate_reads_for_cover(session, cover_image_id)
    items = []
    versions = {row.extraction_version for row in rows if row.extraction_version}
    for row in rows:
        payload = {
            "normalized_upc_value": row.normalized_upc_value,
            "barcode_type": row.barcode_type,
            "source_ocr_result_id": row.source_ocr_result_id,
            "source_ocr_candidate_id": row.source_ocr_candidate_id,
            "confidence": row.confidence,
        }
        items.append({"key": _barcode_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, (next(iter(versions)) if len(versions) == 1 else ("mixed" if versions else "none"))


def _replayed_barcode_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    latest = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    if latest is None:
        raise HTTPException(status_code=409, detail="No prior OCR result exists to replay barcodes.")
    ocr_candidate_rows = _latest_barcode_candidate_rows_for_ocr_result(
        session,
        cover_image_id=cover_image_id,
        ocr_result_id=latest.id,
    )
    items: list[dict[str, object]] = []
    emitted_signatures: set[tuple[str, int | None, int | None, str]] = set()
    candidate_normalized_values: set[str] = set()
    for ocr_candidate in ocr_candidate_rows:
        normalized = normalize_barcode_candidate_value(ocr_candidate.raw_candidate_text)
        if normalized is None:
            continue
        normalized_upc_value, barcode_type = normalized
        candidate_normalized_values.add(normalized_upc_value)
        signature = _barcode_candidate_signature(
            normalized_upc_value=normalized_upc_value,
            source_ocr_result_id=ocr_candidate.ocr_result_id,
            source_ocr_candidate_id=ocr_candidate.id,
            extraction_version=BARCODE_CANDIDATE_EXTRACTION_VERSION,
        )
        if signature in emitted_signatures:
            continue
        emitted_signatures.add(signature)
        payload = {
            "normalized_upc_value": normalized_upc_value,
            "barcode_type": barcode_type,
            "source_ocr_result_id": ocr_candidate.ocr_result_id,
            "source_ocr_candidate_id": ocr_candidate.id,
            "confidence": ocr_candidate.confidence_score,
        }
        items.append({"key": _barcode_snapshot_key(payload), **payload})
    cfg = get_settings()
    for raw_value in _derive_barcode_raw_values_from_text(
        latest.raw_text or "",
        scan_max_chars=int(cfg.cover_barcode_raw_derive_scan_max_chars),
        max_values=max(1, int(cfg.cover_barcode_candidate_emit_max_per_extract)),
    ):
        normalized = normalize_barcode_candidate_value(raw_value)
        if normalized is None:
            continue
        normalized_upc_value, barcode_type = normalized
        if normalized_upc_value in candidate_normalized_values:
            continue
        payload = {
            "normalized_upc_value": normalized_upc_value,
            "barcode_type": barcode_type,
            "source_ocr_result_id": latest.id,
            "source_ocr_candidate_id": None,
            "confidence": latest.confidence_score,
        }
        items.append({"key": _barcode_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, BARCODE_CANDIDATE_EXTRACTION_VERSION


def _latest_fingerprint_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    rows = list_cover_fingerprint_reads_for_cover(session, cover_image_id)
    items = []
    versions = {row.extraction_version for row in rows if row.extraction_version}
    for row in rows:
        payload = {
            "fingerprint_type": row.fingerprint_type,
            "derivative_type": row.derivative_type,
            "fingerprint_value": row.fingerprint_value,
            "image_sha256": row.image_sha256,
            "image_width": row.image_width,
            "image_height": row.image_height,
        }
        items.append({"key": _fingerprint_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, (next(iter(versions)) if len(versions) == 1 else ("mixed" if versions else "none"))


def _replayed_fingerprint_snapshot(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> tuple[dict[str, object], str]:
    cover = session.get(CoverImage, cover_image_id)
    if cover is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    derivative_type, payload, image_width, image_height, image_sha256 = _cover_fingerprint_source(
        session,
        settings=settings,
        cover=cover,
    )
    items = []
    for fingerprint_type, generator in (
        ("ahash", generate_average_hash),
        ("dhash", generate_difference_hash),
        ("phash", generate_perceptual_hash),
    ):
        try:
            fingerprint_value = run_with_thread_deadline(
                float(settings.cover_fingerprint_generation_thread_timeout_seconds),
                lambda gen=generator: gen(payload),
                stage=f"replay_fingerprint_{fingerprint_type}",
            )
        except PipelineStepTimeout as exc:
            raise HTTPException(
                status_code=409,
                detail=f"Fingerprint replay exceeded deadline ({fingerprint_type}).",
            ) from exc
        item = {
            "fingerprint_type": fingerprint_type,
            "derivative_type": derivative_type,
            "fingerprint_value": fingerprint_value,
            "image_sha256": image_sha256,
            "image_width": image_width,
            "image_height": image_height,
        }
        items.append({"key": _fingerprint_snapshot_key(item), **item})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, FINGERPRINT_EXTRACTION_VERSION


def _latest_reconciliation_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    rows = list_cover_image_ocr_reconciliation_warnings(session, cover_image_id=cover_image_id)
    items = []
    for row in rows:
        payload = {
            "warning_type": row.warning_type,
            "severity": row.severity,
            "current_metadata_value": row.current_metadata_value,
            "candidate_value": row.candidate_value,
            "message": row.message,
        }
        items.append({"key": _warning_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, "cover-image-ocr-reconciliation-v1"


def _replayed_reconciliation_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    cover = session.get(CoverImage, cover_image_id)
    if cover is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    selected = _selected_ocr_candidates_for_reconciliation(rows)
    current_metadata = _current_metadata_for_cover(session, cover)
    specs = _build_ocr_reconciliation_warning_specs(
        cover=cover,
        selected_candidates=selected,
        current_metadata=current_metadata,
    )
    items = []
    for spec in specs:
        payload = {
            "warning_type": str(spec["warning_type"]),
            "severity": str(spec["severity"]),
            "current_metadata_value": spec["current_metadata_value"],
            "candidate_value": spec["candidate_value"],
            "message": str(spec["message"]),
        }
        items.append({"key": _warning_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, "cover-image-ocr-reconciliation-v1"


def _latest_quality_snapshot(session: Session, cover_image_id: int) -> tuple[dict[str, object], str]:
    rows = list_cover_ocr_quality_analysis_reads_for_cover(session, cover_image_id)
    items = []
    versions = {row.extraction_version for row in rows if row.extraction_version}
    for row in rows:
        payload = {
            "quality_type": row.quality_type,
            "deterministic_score": row.deterministic_score,
            "severity": row.severity,
            "detail_json": row.detail_json,
        }
        items.append({"key": _quality_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, (next(iter(versions)) if len(versions) == 1 else ("mixed" if versions else "none"))


def _replayed_quality_snapshot(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> tuple[dict[str, object], str]:
    cover = session.get(CoverImage, cover_image_id)
    if cover is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    derivative_type, image_bytes, _, _, _ = _cover_fingerprint_source(session, settings=settings, cover=cover)
    latest = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    try:
        specs = run_with_thread_deadline(
            float(settings.cover_quality_analysis_thread_timeout_seconds),
            lambda: _build_ocr_quality_analysis_specs(
                cover=cover,
                derivative_type=derivative_type,
                image_bytes=image_bytes,
                source_ocr_result=latest,
            ),
            stage="replay_ocr_quality_specs",
        )
    except PipelineStepTimeout as exc:
        raise HTTPException(
            status_code=409,
            detail="Quality replay exceeded the bounded deadline.",
        ) from exc
    items = []
    for spec in specs:
        payload = {
            "quality_type": str(spec["quality_type"]),
            "deterministic_score": float(spec["deterministic_score"]),
            "severity": str(spec["severity"]),
            "detail_json": dict(spec["detail_json"]),
        }
        items.append({"key": _quality_snapshot_key(payload), **payload})
    return {
        "shape": "list",
        "item_count": len(items),
        "items": sorted(items, key=lambda item: str(item["key"])),
    }, OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION


def _pipeline_snapshot(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    replay: bool,
) -> tuple[dict[str, object], str]:
    builders = {
        "ocr_result": (
            lambda: _replayed_ocr_result_snapshot(session, settings=settings, cover_image_id=cover_image_id)
            if replay
            else _latest_ocr_result_snapshot(session, cover_image_id)
        ),
        "candidate_extraction": (
            lambda: _replayed_candidate_snapshot(session, cover_image_id)
            if replay
            else _latest_candidate_snapshot(session, cover_image_id)
        ),
        "barcode_extraction": (
            lambda: _replayed_barcode_snapshot(session, cover_image_id)
            if replay
            else _latest_barcode_snapshot(session, cover_image_id)
        ),
        "fingerprint_generation": (
            lambda: _replayed_fingerprint_snapshot(session, settings=settings, cover_image_id=cover_image_id)
            if replay
            else _latest_fingerprint_snapshot(session, cover_image_id)
        ),
        "reconciliation_warning": (
            lambda: _replayed_reconciliation_snapshot(session, cover_image_id)
            if replay
            else _latest_reconciliation_snapshot(session, cover_image_id)
        ),
        "quality_analysis": (
            lambda: _replayed_quality_snapshot(session, settings=settings, cover_image_id=cover_image_id)
            if replay
            else _latest_quality_snapshot(session, cover_image_id)
        ),
    }
    components: dict[str, object] = {}
    versions: dict[str, str] = {}
    for key, builder in builders.items():
        snapshot, version = builder()
        components[key] = snapshot
        versions[key] = version
    return {
        "shape": "pipeline",
        "components": components,
        "versions": versions,
    }, "full-pipeline-current"


def _build_snapshots_for_type(
    session: Session,
    *,
    settings: Settings,
    replay_type: str,
    cover_image_id: int,
) -> tuple[dict[str, object], dict[str, object], str, str]:
    if replay_type == "ocr_result":
        previous, version_from = _latest_ocr_result_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_ocr_result_snapshot(session, settings=settings, cover_image_id=cover_image_id)
        return previous, replayed, version_from, version_to
    if replay_type == "candidate_extraction":
        previous, version_from = _latest_candidate_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_candidate_snapshot(session, cover_image_id)
        return previous, replayed, version_from, version_to
    if replay_type == "barcode_extraction":
        previous, version_from = _latest_barcode_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_barcode_snapshot(session, cover_image_id)
        return previous, replayed, version_from, version_to
    if replay_type == "fingerprint_generation":
        previous, version_from = _latest_fingerprint_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_fingerprint_snapshot(
            session,
            settings=settings,
            cover_image_id=cover_image_id,
        )
        return previous, replayed, version_from, version_to
    if replay_type == "reconciliation_warning":
        previous, version_from = _latest_reconciliation_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_reconciliation_snapshot(session, cover_image_id)
        return previous, replayed, version_from, version_to
    if replay_type == "quality_analysis":
        previous, version_from = _latest_quality_snapshot(session, cover_image_id)
        replayed, version_to = _replayed_quality_snapshot(
            session,
            settings=settings,
            cover_image_id=cover_image_id,
        )
        return previous, replayed, version_from, version_to
    if replay_type == "full_pipeline":
        previous, version_from = _pipeline_snapshot(
            session,
            settings=settings,
            cover_image_id=cover_image_id,
            replay=False,
        )
        replayed, version_to = _pipeline_snapshot(
            session,
            settings=settings,
            cover_image_id=cover_image_id,
            replay=True,
        )
        return previous, replayed, version_from, version_to
    raise HTTPException(status_code=422, detail="Unsupported OCR replay type")


def _validate_cover_ids_for_owner(session: Session, *, current_user: User, cover_ids: list[int]) -> list[int]:
    valid: list[int] = []
    for cover_id in cover_ids:
        try:
            get_cover_entity_for_processing_by_owner(session, current_user=current_user, cover_image_id=cover_id)
        except HTTPException:
            continue
        valid.append(cover_id)
    return valid


def _validate_cover_ids_for_ops(session: Session, *, cover_ids: list[int]) -> list[int]:
    valid: list[int] = []
    for cover_id in cover_ids:
        try:
            get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_id)
        except HTTPException:
            continue
        valid.append(cover_id)
    return valid


def _normalize_cover_ids(cover_image_ids: list[int]) -> list[int]:
    return sorted({int(value) for value in cover_image_ids if int(value) > 0})


def _derive_run_versions(
    session: Session,
    *,
    settings: Settings,
    replay_type: str,
    cover_ids: list[int],
) -> tuple[str, str]:
    if not cover_ids:
        return "none", REPLAY_TYPE_TO_CURRENT_VERSION[replay_type]
    from_versions: set[str] = set()
    for cover_id in cover_ids[:5]:
        try:
            if replay_type == "ocr_result":
                _, version_from = _latest_ocr_result_snapshot(session, cover_id)
            elif replay_type == "candidate_extraction":
                _, version_from = _latest_candidate_snapshot(session, cover_id)
            elif replay_type == "barcode_extraction":
                _, version_from = _latest_barcode_snapshot(session, cover_id)
            elif replay_type == "fingerprint_generation":
                _, version_from = _latest_fingerprint_snapshot(session, cover_id)
            elif replay_type == "reconciliation_warning":
                _, version_from = _latest_reconciliation_snapshot(session, cover_id)
            elif replay_type == "quality_analysis":
                _, version_from = _latest_quality_snapshot(session, cover_id)
            elif replay_type == "full_pipeline":
                _, version_from = _pipeline_snapshot(
                    session,
                    settings=settings,
                    cover_image_id=cover_id,
                    replay=False,
                )
            else:
                version_from = "none"
        except Exception:
            continue
        from_versions.add(version_from)
    version_from_value = next(iter(from_versions)) if len(from_versions) == 1 else ("mixed" if from_versions else "none")
    version_to_value = REPLAY_TYPE_TO_CURRENT_VERSION[replay_type]
    return version_from_value, version_to_value


def _recompute_run_summary(run: OcrReplayRun, items: list[OcrReplayItem]) -> None:
    counts = Counter(item.status for item in items)
    run.total_items = len(items)
    run.changed_items = counts.get("changed", 0)
    run.unchanged_items = counts.get("unchanged", 0)
    run.failed_items = counts.get("failed", 0)
    if run.status == "cancelled":
        run.completed_at = run.completed_at or _now()
        return
    if counts.get("failed", 0) == len(items) and len(items) > 0:
        run.status = "failed"
    elif counts.get("changed", 0) > 0 or counts.get("failed", 0) > 0:
        run.status = "completed_with_changes"
    else:
        run.status = "completed"
    run.completed_at = _now()


def _version_label(values: set[str], fallback: str) -> str:
    if not values:
        return fallback
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


def _create_replay_run(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
    replay_type: str,
    cover_ids: list[int],
) -> OcrReplayRunRead:
    now = _now()
    version_from, version_to = _derive_run_versions(
        session,
        settings=settings,
        replay_type=replay_type,
        cover_ids=cover_ids,
    )
    run = OcrReplayRun(
        replay_type=replay_type,
        extraction_version_from=version_from,
        extraction_version_to=version_to,
        status="pending",
        total_items=len(cover_ids),
        changed_items=0,
        unchanged_items=0,
        failed_items=0,
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
        created_by=actor_user_id,
    )
    session.add(run)
    session.flush()
    if run.id is None:
        raise ValueError("Failed to create OCR replay run")
    for cover_id in cover_ids:
        session.add(
            OcrReplayItem(
                replay_run_id=run.id,
                cover_image_id=cover_id,
                status="pending",
                previous_snapshot_json={},
                replay_snapshot_json={},
                diff_summary_json={},
                last_error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
        )
    session.flush()
    record_metadata_audit(
        session,
        entity_type="ocr_replay_run",
        entity_id=run.id,
        action="ocr_replay_run_created",
        before_snapshot=None,
        after_snapshot=_replay_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(run)
    return ocr_replay_run_entity_to_read(session, run)


def create_ocr_replay_run_for_owner(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    payload: OcrReplayCreatePayload,
) -> OcrReplayRunRead:
    cover_ids = _validate_cover_ids_for_owner(
        session,
        current_user=current_user,
        cover_ids=_normalize_cover_ids(payload.cover_image_ids),
    )
    return _create_replay_run(
        session,
        settings=settings,
        actor_user_id=current_user.id,
        replay_type=payload.replay_type,
        cover_ids=cover_ids,
    )


def create_ocr_replay_run_for_ops(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
    payload: OcrReplayCreatePayload,
) -> OcrReplayRunRead:
    cover_ids = _validate_cover_ids_for_ops(session, cover_ids=_normalize_cover_ids(payload.cover_image_ids))
    return _create_replay_run(
        session,
        settings=settings,
        actor_user_id=actor_user_id,
        replay_type=payload.replay_type,
        cover_ids=cover_ids,
    )


def get_ocr_replay_run_for_owner_or_404(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> OcrReplayRun:
    run = session.get(OcrReplayRun, replay_id)
    if run is None or run.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="OCR replay run not found")
    return run


def get_ocr_replay_run_for_ops_or_404(session: Session, *, replay_id: int) -> OcrReplayRun:
    run = session.get(OcrReplayRun, replay_id)
    if run is None:
        raise HTTPException(status_code=404, detail="OCR replay run not found")
    return run


def list_ocr_replay_runs_for_owner(
    session: Session,
    *,
    current_user: User,
    limit: int = 25,
) -> list[OcrReplayRunRead]:
    rows = session.exec(
        select(OcrReplayRun)
        .where(OcrReplayRun.created_by == current_user.id)
        .order_by(OcrReplayRun.created_at.desc(), OcrReplayRun.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [ocr_replay_run_entity_to_read(session, row) for row in rows]


def list_ocr_replay_runs_for_ops(session: Session, *, limit: int = 25) -> list[OcrReplayRunRead]:
    rows = session.exec(
        select(OcrReplayRun)
        .order_by(OcrReplayRun.created_at.desc(), OcrReplayRun.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [ocr_replay_run_entity_to_read(session, row) for row in rows]


def get_ocr_replay_run_detail_for_owner(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id)
    return ocr_replay_run_entity_to_read(session, run)


def get_ocr_replay_run_detail_for_ops(session: Session, *, replay_id: int) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_ops_or_404(session, replay_id=replay_id)
    return ocr_replay_run_entity_to_read(session, run)


def _start_replay_run(
    session: Session,
    *,
    settings: Settings,
    run: OcrReplayRun,
    actor_user_id: int | None,
) -> OcrReplayRunRead:
    if run.id is None:
        raise HTTPException(status_code=404, detail="OCR replay run not found")
    if run.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled OCR replay runs cannot be started")
    before = _replay_run_snapshot_public(run)
    run.status = "running"
    run.started_at = _now()
    run.completed_at = None
    run.updated_at = _now()
    session.add(run)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="ocr_replay_run",
        entity_id=run.id,
        action="ocr_replay_run_started",
        before_snapshot=before,
        after_snapshot=_replay_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )

    items = session.exec(
        select(OcrReplayItem)
        .where(OcrReplayItem.replay_run_id == run.id)
        .order_by(OcrReplayItem.cover_image_id.asc(), OcrReplayItem.id.asc())
    ).all()
    version_from_values: set[str] = set()
    version_to_values: set[str] = set()
    for item in items:
        item.status = "running"
        item.updated_at = _now()
        item.last_error = None
        session.add(item)
        session.flush()
        try:
            previous_snapshot, replay_snapshot, version_from, version_to = _build_snapshots_for_type(
                session,
                settings=settings,
                replay_type=run.replay_type,
                cover_image_id=item.cover_image_id,
            )
            diff_summary = _bounded_replay_diff_summary(
                _summarize_diff(previous_snapshot, replay_snapshot),
                max_chars=max(512, int(settings.cover_ocr_replay_diff_max_chars)),
            )
            item.previous_snapshot_json = previous_snapshot
            item.replay_snapshot_json = replay_snapshot
            item.diff_summary_json = diff_summary
            item.status = "changed" if diff_summary.get("status") == "changed" else "unchanged"
            item.completed_at = _now()
            item.updated_at = _now()
            version_from_values.add(version_from)
            version_to_values.add(version_to)
            session.add(item)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="ocr_replay_item",
                entity_id=item.id,
                action=f"ocr_replay_item_{item.status}",
                before_snapshot=None,
                after_snapshot=ocr_replay_item_entity_to_read(item).model_dump(),
                actor_user_id=actor_user_id,
            )
        except Exception as exc:
            item.previous_snapshot_json = item.previous_snapshot_json or {}
            item.replay_snapshot_json = {}
            item.diff_summary_json = {}
            item.status = "failed"
            item.last_error = structured_error_to_persistent(
                classify_exception(exc, stage="ocr_replay_item")
            )[:2000]
            item.completed_at = _now()
            item.updated_at = _now()
            session.add(item)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="ocr_replay_item",
                entity_id=item.id,
                action="ocr_replay_item_failed",
                before_snapshot=None,
                after_snapshot=ocr_replay_item_entity_to_read(item).model_dump(),
                actor_user_id=actor_user_id,
            )

    session.flush()
    refreshed_items = session.exec(
        select(OcrReplayItem).where(OcrReplayItem.replay_run_id == run.id).order_by(OcrReplayItem.id.asc())
    ).all()
    run.extraction_version_from = _version_label(
        version_from_values,
        run.extraction_version_from or REPLAY_TYPE_TO_CURRENT_VERSION.get(run.replay_type, "none"),
    )
    run.extraction_version_to = _version_label(
        version_to_values,
        REPLAY_TYPE_TO_CURRENT_VERSION.get(run.replay_type, run.extraction_version_to or "none"),
    )
    _recompute_run_summary(run, refreshed_items)
    run.updated_at = _now()
    session.add(run)
    session.flush()
    final_event = {
        "completed": "ocr_replay_run_completed",
        "completed_with_changes": "ocr_replay_run_completed_with_changes",
        "failed": "ocr_replay_run_failed",
    }.get(run.status)
    if final_event:
        record_metadata_audit(
            session,
            entity_type="ocr_replay_run",
            entity_id=run.id,
            action=final_event,
            before_snapshot=before,
            after_snapshot=_replay_run_snapshot_public(run),
            actor_user_id=actor_user_id,
        )
    session.commit()
    session.refresh(run)
    return ocr_replay_run_entity_to_read(session, run)


def start_ocr_replay_run_for_owner(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    replay_id: int,
) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id)
    return _start_replay_run(session, settings=settings, run=run, actor_user_id=current_user.id)


def start_ocr_replay_run_for_ops(
    session: Session,
    *,
    settings: Settings,
    replay_id: int,
    actor_user_id: int | None,
) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_ops_or_404(session, replay_id=replay_id)
    return _start_replay_run(session, settings=settings, run=run, actor_user_id=actor_user_id)


def _cancel_replay_run(
    session: Session,
    *,
    run: OcrReplayRun,
    actor_user_id: int | None,
) -> OcrReplayRunRead:
    if run.id is None:
        raise HTTPException(status_code=404, detail="OCR replay run not found")
    before = _replay_run_snapshot_public(run)
    items = session.exec(
        select(OcrReplayItem).where(OcrReplayItem.replay_run_id == run.id).order_by(OcrReplayItem.id.asc())
    ).all()
    for item in items:
        if item.status == "pending":
            item.status = "cancelled"
            item.updated_at = _now()
            item.completed_at = _now()
            session.add(item)
    run.status = "cancelled"
    run.completed_at = _now()
    run.updated_at = _now()
    session.add(run)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="ocr_replay_run",
        entity_id=run.id,
        action="ocr_replay_run_cancelled",
        before_snapshot=before,
        after_snapshot=_replay_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(run)
    return ocr_replay_run_entity_to_read(session, run)


def cancel_ocr_replay_run_for_owner(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id)
    return _cancel_replay_run(session, run=run, actor_user_id=current_user.id)


def cancel_ocr_replay_run_for_ops(
    session: Session,
    *,
    replay_id: int,
    actor_user_id: int | None,
) -> OcrReplayRunRead:
    run = get_ocr_replay_run_for_ops_or_404(session, replay_id=replay_id)
    return _cancel_replay_run(session, run=run, actor_user_id=actor_user_id)
