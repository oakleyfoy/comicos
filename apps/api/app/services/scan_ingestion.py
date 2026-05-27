from __future__ import annotations

import hashlib
import io
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import ScanImage, ScanImageVariant, ScanIngestionBatch, ScanIngestionEvent, ScanUploadSession
from app.schemas.scan_ingestion import (
    RegisteredScanFilePayload,
    ScanBatchCreatePayload,
    ScanBatchUploadPayload,
    ScanImageListResponse,
    ScanImageRead,
    ScanImageSummaryRead,
    ScanImageVariantRead,
    ScanIngestionBatchListResponse,
    ScanIngestionBatchRead,
    ScanIngestionBatchSummaryRead,
    ScanIngestionEventRead,
    ScanUploadSessionRead,
)

_THUMBNAIL_MAX = 320


@dataclass(frozen=True)
class _PreparedUpload:
    original_filename: str
    mime_type: str
    body: bytes
    input_order: int


@dataclass(frozen=True)
class _DecodedImage:
    width: int | None
    height: int | None
    dpi_x: int | None
    dpi_y: int | None
    mime_type: str
    color_mode: str | None


def utc_now():
    from app.models.scan_ingestion import utc_now as _utc_now

    return _utc_now()


def clamp_scan_ingestion_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _normalize_dpi_value(value: Any) -> int | None:
    if isinstance(value, (tuple, list)) and value:
        value = value[0]
    if value is None:
        return None
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _guess_mime_type(filename: str, hinted: str | None) -> str:
    if hinted and hinted != "application/octet-stream":
        return hinted
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _extension_for_mime_type(mime_type: str, fallback_filename: str) -> str:
    ext = mimetypes.guess_extension(mime_type, strict=False)
    if ext:
        return ext.lower()
    suffix = Path(fallback_filename).suffix.lower()
    if suffix:
        return suffix
    return ".bin"


def _resolve_storage_root(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_ingestion_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan ingestion storage path escapes the configured root")
    return target


def _deterministic_original_storage_path(sha256_hex: str, filename: str, mime_type: str) -> str:
    ext = _extension_for_mime_type(mime_type, filename)
    return f"originals/{sha256_hex[:2]}/{sha256_hex[2:4]}/{sha256_hex}{ext}".replace("\\", "/")


def _deterministic_variant_storage_path(scan_image_id: int, variant_type: str, checksum: str, ext: str) -> str:
    safe_type = variant_type.lower().replace(" ", "_")
    return f"variants/{scan_image_id}/{safe_type}/{checksum}{ext}".replace("\\", "/")


def _ensure_bytes_written(settings: Settings, relative_path: str, body: bytes) -> None:
    abs_path = _resolve_storage_root(settings, relative_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    if abs_path.exists():
        return
    abs_path.write_bytes(body)


def _decode_image(body: bytes, filename: str, hinted_mime_type: str | None) -> _DecodedImage:
    try:
        with Image.open(io.BytesIO(body)) as image:
            width, height = image.size
            dpi = image.info.get("dpi")
            dpi_x = _normalize_dpi_value(dpi[0] if isinstance(dpi, tuple) and dpi else dpi)
            dpi_y = _normalize_dpi_value(dpi[1] if isinstance(dpi, tuple) and len(dpi) > 1 else dpi)
            mime = Image.MIME.get(image.format or "", _guess_mime_type(filename, hinted_mime_type))
            return _DecodedImage(
                width=int(width),
                height=int(height),
                dpi_x=dpi_x,
                dpi_y=dpi_y,
                mime_type=mime,
                color_mode=_trim(image.mode),
            )
    except UnidentifiedImageError as exc:
        raise ValueError("unsupported or unreadable scan payload") from exc
    except OSError as exc:
        raise ValueError("unsupported or unreadable scan payload") from exc


def detect_duplicate_scan(session: Session, *, owner_user_id: int, sha256_checksum: str) -> ScanImage | None:
    return session.exec(
        select(ScanImage)
        .where(ScanImage.owner_user_id == owner_user_id, ScanImage.sha256_checksum == sha256_checksum)
        .order_by(col(ScanImage.created_at).asc(), col(ScanImage.id).asc())
    ).first()


def _variant_read(row: ScanImageVariant) -> ScanImageVariantRead:
    return ScanImageVariantRead.model_validate(row, from_attributes=True)


def _image_summary_read(row: ScanImage) -> ScanImageSummaryRead:
    return ScanImageSummaryRead.model_validate(row, from_attributes=True)


def _event_read(row: ScanIngestionEvent) -> ScanIngestionEventRead:
    return ScanIngestionEventRead.model_validate(row, from_attributes=True)


def _upload_session_read(row: ScanUploadSession) -> ScanUploadSessionRead:
    return ScanUploadSessionRead.model_validate(row, from_attributes=True)


def _batch_summary_read(row: ScanIngestionBatch) -> ScanIngestionBatchSummaryRead:
    return ScanIngestionBatchSummaryRead.model_validate(row, from_attributes=True)


def _append_event(
    session: Session,
    *,
    ingestion_batch_id: int,
    event_type: str,
    scan_image_id: int | None = None,
    metadata_json: dict[str, Any],
) -> None:
    session.add(
        ScanIngestionEvent(
            ingestion_batch_id=ingestion_batch_id,
            scan_image_id=scan_image_id,
            event_type=event_type,
            metadata_json=_json_safe(metadata_json),
            created_at=utc_now(),
        )
    )


def _load_batch_detail(session: Session, *, batch: ScanIngestionBatch) -> ScanIngestionBatchRead:
    upload_session = session.get(ScanUploadSession, batch.upload_session_id)
    if upload_session is None:
        raise HTTPException(status_code=500, detail="Upload session not found for scan ingestion batch")
    images = list(
        session.exec(
            select(ScanImage)
            .where(ScanImage.ingestion_batch_id == batch.id)
            .order_by(col(ScanImage.sequence_index).asc(), col(ScanImage.id).asc())
        ).all()
    )
    events = list(
        session.exec(
            select(ScanIngestionEvent)
            .where(ScanIngestionEvent.ingestion_batch_id == batch.id)
            .order_by(col(ScanIngestionEvent.created_at).asc(), col(ScanIngestionEvent.id).asc())
        ).all()
    )
    return ScanIngestionBatchRead(
        **_batch_summary_read(batch).model_dump(),
        upload_session=_upload_session_read(upload_session),
        images=[_image_summary_read(row) for row in images],
        events=[_event_read(row) for row in events],
    )


def _load_scan_image_detail(session: Session, *, scan_image: ScanImage) -> ScanImageRead:
    variants = list(
        session.exec(
            select(ScanImageVariant)
            .where(ScanImageVariant.parent_scan_image_id == scan_image.id)
            .order_by(col(ScanImageVariant.created_at).asc(), col(ScanImageVariant.id).asc())
        ).all()
    )
    return ScanImageRead(
        **_image_summary_read(scan_image).model_dump(),
        variants=[_variant_read(row) for row in variants],
    )


def _session_checksum_for_entries(payload: ScanBatchUploadPayload | ScanBatchCreatePayload, entries: list[dict[str, Any]]) -> str:
    return _hash_payload(
        {
            "upload_source": payload.upload_source,
            "source_type": payload.source_type,
            "entries": entries,
        }
    )


def _batch_checksum_for_entries(payload: ScanBatchUploadPayload | ScanBatchCreatePayload, entries: list[dict[str, Any]]) -> str:
    return _hash_payload(
        {
            "source_type": payload.source_type,
            "normalized_dpi": payload.normalized_dpi,
            "entries": entries,
        }
    )


def _prepared_entries_for_upload(payload: ScanBatchUploadPayload, uploads: list[_PreparedUpload]) -> list[dict[str, Any]]:
    seeded: list[dict[str, Any]] = []
    for row in uploads:
        sha256_checksum = _sha256_bytes(row.body)
        seeded.append(
            {
                "original_filename": row.original_filename,
                "mime_type": row.mime_type,
                "file_size_bytes": len(row.body),
                "sha256_checksum": sha256_checksum,
            }
        )
    return sorted(
        seeded,
        key=lambda row: (
            str(row["original_filename"]).casefold(),
            str(row["sha256_checksum"]),
            int(row["file_size_bytes"]),
        ),
    )


def _prepared_entries_for_registered(payload: ScanBatchCreatePayload) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "original_filename": row.original_filename,
                "storage_path": row.storage_path,
                "mime_type": row.mime_type,
                "file_size_bytes": row.file_size_bytes,
                "sha256_checksum": row.sha256_checksum,
            }
            for row in payload.files
        ],
        key=lambda row: (
            str(row["original_filename"]).casefold(),
            str(row["sha256_checksum"]),
            int(row["file_size_bytes"]),
        ),
    )


def _coerce_upload_session(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanBatchUploadPayload | ScanBatchCreatePayload,
    entries: list[dict[str, Any]],
) -> ScanUploadSession:
    checksum = _session_checksum_for_entries(payload, entries)
    existing = session.exec(
        select(ScanUploadSession)
        .where(ScanUploadSession.owner_user_id == owner_user_id, ScanUploadSession.session_checksum == checksum)
        .order_by(col(ScanUploadSession.created_at).desc(), col(ScanUploadSession.id).desc())
    ).first()
    if existing is not None:
        return existing
    now = utc_now()
    row = ScanUploadSession(
        owner_user_id=owner_user_id,
        upload_source=payload.upload_source,
        session_checksum=checksum,
        total_files=len(entries),
        successful_files=0,
        failed_files=0,
        duplicate_files=0,
        started_at=now,
        completed_at=None,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return row


def create_scan_variant(
    session: Session,
    settings: Settings,
    *,
    scan_image: ScanImage,
    variant_type: str,
    image: Image.Image,
    ext: str,
    save_kwargs: dict[str, Any] | None = None,
) -> ScanImageVariantRead:
    rendered = io.BytesIO()
    normalized = ImageOps.exif_transpose(image)
    save_kwargs = save_kwargs or {}
    fmt = "PNG" if ext.lower() == ".png" else "JPEG"
    normalized.save(rendered, format=fmt, **save_kwargs)
    body = rendered.getvalue()
    checksum = _sha256_bytes(body)
    existing = session.exec(
        select(ScanImageVariant)
        .where(
            ScanImageVariant.parent_scan_image_id == scan_image.id,
            ScanImageVariant.variant_type == variant_type,
            ScanImageVariant.checksum == checksum,
        )
        .order_by(col(ScanImageVariant.created_at).asc(), col(ScanImageVariant.id).asc())
    ).first()
    if existing is not None:
        return _variant_read(existing)

    storage_path = _deterministic_variant_storage_path(int(scan_image.id or 0), variant_type, checksum, ext)
    _ensure_bytes_written(settings, storage_path, body)
    row = ScanImageVariant(
        parent_scan_image_id=int(scan_image.id or 0),
        variant_type=variant_type,
        storage_backend="filesystem",
        storage_path=storage_path,
        width=int(normalized.width),
        height=int(normalized.height),
        checksum=checksum,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    _append_event(
        session,
        ingestion_batch_id=scan_image.ingestion_batch_id,
        scan_image_id=scan_image.id,
        event_type="VARIANT_CREATED",
        metadata_json={"variant_type": variant_type, "checksum": checksum, "storage_path": storage_path},
    )
    return _variant_read(row)


def ingest_scan_image(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    batch: ScanIngestionBatch,
    sequence_index: int,
    payload: ScanBatchUploadPayload,
    prepared_upload: _PreparedUpload,
) -> ScanImage:
    sha256_checksum = _sha256_bytes(prepared_upload.body)
    duplicate_of = detect_duplicate_scan(session, owner_user_id=owner_user_id, sha256_checksum=sha256_checksum)
    storage_path = _deterministic_original_storage_path(
        sha256_checksum,
        prepared_upload.original_filename,
        prepared_upload.mime_type,
    )
    _ensure_bytes_written(settings, storage_path, prepared_upload.body)

    try:
        decoded = _decode_image(prepared_upload.body, prepared_upload.original_filename, prepared_upload.mime_type)
        processing_status = "NORMALIZED" if payload.create_normalized_variant else "INGESTED"
        failure_reason = None
    except ValueError as exc:
        decoded = _DecodedImage(
            width=None,
            height=None,
            dpi_x=None,
            dpi_y=None,
            mime_type=_guess_mime_type(prepared_upload.original_filename, prepared_upload.mime_type),
            color_mode=_trim(payload.color_mode),
        )
        processing_status = "FAILED"
        failure_reason = str(exc)

    row = ScanImage(
        owner_user_id=owner_user_id,
        ingestion_batch_id=int(batch.id or 0),
        sequence_index=sequence_index,
        original_filename=prepared_upload.original_filename,
        storage_backend="filesystem",
        storage_path=storage_path,
        mime_type=decoded.mime_type,
        width=decoded.width,
        height=decoded.height,
        dpi_x=decoded.dpi_x,
        dpi_y=decoded.dpi_y,
        normalized_dpi_x=payload.normalized_dpi if processing_status != "FAILED" else None,
        normalized_dpi_y=payload.normalized_dpi if processing_status != "FAILED" else None,
        file_size_bytes=len(prepared_upload.body),
        sha256_checksum=sha256_checksum,
        scanner_make=_trim(payload.scanner_make),
        scanner_model=_trim(payload.scanner_model),
        scanner_profile=_trim(payload.scanner_profile),
        color_mode=_trim(payload.color_mode) or decoded.color_mode,
        processing_status=processing_status,
        is_duplicate=duplicate_of is not None,
        duplicate_of_scan_image_id=int(duplicate_of.id) if duplicate_of and duplicate_of.id is not None else None,
        failure_reason=failure_reason,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()

    _append_event(
        session,
        ingestion_batch_id=int(batch.id or 0),
        scan_image_id=row.id,
        event_type="IMAGE_REGISTERED" if failure_reason is None else "IMAGE_FAILED",
        metadata_json={
            "sequence_index": sequence_index,
            "sha256_checksum": sha256_checksum,
            "original_filename": prepared_upload.original_filename,
            "storage_path": storage_path,
            "failure_reason": failure_reason,
        },
    )
    if duplicate_of is not None:
        _append_event(
            session,
            ingestion_batch_id=int(batch.id or 0),
            scan_image_id=row.id,
            event_type="DUPLICATE_DETECTED",
            metadata_json={
                "duplicate_of_scan_image_id": int(duplicate_of.id or 0),
                "sha256_checksum": sha256_checksum,
            },
        )

    if failure_reason is not None:
        return row

    with Image.open(io.BytesIO(prepared_upload.body)) as opened:
        oriented = ImageOps.exif_transpose(opened)
        if payload.create_normalized_variant:
            create_scan_variant(
                session,
                settings,
                scan_image=row,
                variant_type="normalized_image",
                image=oriented,
                ext=".png",
                save_kwargs={"dpi": (payload.normalized_dpi, payload.normalized_dpi)},
            )
        if payload.create_thumbnail:
            thumb = oriented.copy()
            thumb.thumbnail((_THUMBNAIL_MAX, _THUMBNAIL_MAX))
            create_scan_variant(
                session,
                settings,
                scan_image=row,
                variant_type="thumbnail",
                image=thumb,
                ext=".png",
            )
    return row


async def _prepare_upload_entries(files: list[UploadFile]) -> list[_PreparedUpload]:
    prepared: list[_PreparedUpload] = []
    for index, upload in enumerate(files):
        filename = _trim(upload.filename) or f"upload-{index + 1}"
        body = await upload.read()
        mime_type = _guess_mime_type(filename, upload.content_type)
        is_zip = mime_type == "application/zip" or filename.lower().endswith(".zip")
        if is_zip:
            try:
                with ZipFile(io.BytesIO(body)) as archive:
                    names = sorted(
                        [name for name in archive.namelist() if not name.endswith("/")],
                        key=lambda value: value.casefold(),
                    )
                    for inner_index, member in enumerate(names):
                        prepared.append(
                            _PreparedUpload(
                                original_filename=Path(member).name or f"zip-entry-{inner_index + 1}",
                                mime_type=_guess_mime_type(member, None),
                                body=archive.read(member),
                                input_order=index * 10000 + inner_index,
                            )
                        )
            except Exception as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=422, detail="Uploaded ZIP could not be read") from exc
            continue
        prepared.append(
            _PreparedUpload(
                original_filename=filename,
                mime_type=mime_type,
                body=body,
                input_order=index,
            )
        )
    if not prepared:
        raise HTTPException(status_code=422, detail="At least one scan file is required")
    return sorted(
        prepared,
        key=lambda row: (
            row.original_filename.casefold(),
            _sha256_bytes(row.body),
            row.input_order,
        ),
    )


async def register_uploaded_scan_batch(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanBatchUploadPayload,
    files: list[UploadFile],
) -> tuple[ScanIngestionBatchRead, bool]:
    prepared_uploads = await _prepare_upload_entries(files)
    entries = _prepared_entries_for_upload(payload, prepared_uploads)
    upload_session = _coerce_upload_session(session, owner_user_id=owner_user_id, payload=payload, entries=entries)
    batch_checksum = _batch_checksum_for_entries(payload, entries)
    existing = session.exec(
        select(ScanIngestionBatch)
        .where(ScanIngestionBatch.owner_user_id == owner_user_id, ScanIngestionBatch.ingestion_checksum == batch_checksum)
        .order_by(col(ScanIngestionBatch.created_at).desc(), col(ScanIngestionBatch.id).desc())
    ).first()
    if existing is not None:
        return _load_batch_detail(session, batch=existing), False

    now = utc_now()
    batch = ScanIngestionBatch(
        owner_user_id=owner_user_id,
        upload_session_id=int(upload_session.id or 0),
        source_type=payload.source_type,
        batch_status="PROCESSING",
        image_count=0,
        failed_count=0,
        duplicate_count=0,
        ingestion_checksum=batch_checksum,
        created_at=now,
        completed_at=None,
    )
    session.add(batch)
    session.flush()
    _append_event(
        session,
        ingestion_batch_id=int(batch.id or 0),
        event_type="UPLOAD_SESSION_STARTED",
        metadata_json={
            "upload_session_id": int(upload_session.id or 0),
            "session_checksum": upload_session.session_checksum,
            "total_files": len(entries),
        },
    )
    _append_event(
        session,
        ingestion_batch_id=int(batch.id or 0),
        event_type="BATCH_CREATED",
        metadata_json={
            "source_type": payload.source_type,
            "ingestion_checksum": batch_checksum,
            "normalized_dpi": payload.normalized_dpi,
        },
    )

    images: list[ScanImage] = []
    for idx, prepared in enumerate(prepared_uploads):
        row = ingest_scan_image(
            session,
            settings,
            owner_user_id=owner_user_id,
            batch=batch,
            sequence_index=idx,
            payload=payload,
            prepared_upload=prepared,
        )
        images.append(row)

    batch.image_count = len(images)
    batch.failed_count = sum(1 for row in images if row.processing_status == "FAILED")
    batch.duplicate_count = sum(1 for row in images if row.is_duplicate)
    batch.batch_status = "FAILED" if batch.failed_count == batch.image_count else "COMPLETE"
    batch.completed_at = utc_now()
    upload_session.successful_files = batch.image_count - batch.failed_count
    upload_session.failed_files = batch.failed_count
    upload_session.duplicate_files = batch.duplicate_count
    upload_session.completed_at = batch.completed_at
    session.add(upload_session)
    session.add(batch)
    _append_event(
        session,
        ingestion_batch_id=int(batch.id or 0),
        event_type="BATCH_COMPLETED",
        metadata_json={
            "batch_status": batch.batch_status,
            "image_count": batch.image_count,
            "failed_count": batch.failed_count,
            "duplicate_count": batch.duplicate_count,
        },
    )
    session.commit()
    session.refresh(batch)
    return _load_batch_detail(session, batch=batch), True


def register_scan_batch(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanBatchCreatePayload,
) -> tuple[ScanIngestionBatchRead, bool]:
    entries = _prepared_entries_for_registered(payload)
    upload_session = _coerce_upload_session(session, owner_user_id=owner_user_id, payload=payload, entries=entries)
    batch_checksum = _batch_checksum_for_entries(payload, entries)
    existing = session.exec(
        select(ScanIngestionBatch)
        .where(ScanIngestionBatch.owner_user_id == owner_user_id, ScanIngestionBatch.ingestion_checksum == batch_checksum)
        .order_by(col(ScanIngestionBatch.created_at).desc(), col(ScanIngestionBatch.id).desc())
    ).first()
    if existing is not None:
        return _load_batch_detail(session, batch=existing), False

    now = utc_now()
    batch = ScanIngestionBatch(
        owner_user_id=owner_user_id,
        upload_session_id=int(upload_session.id or 0),
        source_type=payload.source_type,
        batch_status="COMPLETE",
        image_count=len(payload.files),
        failed_count=0,
        duplicate_count=0,
        ingestion_checksum=batch_checksum,
        created_at=now,
        completed_at=now,
    )
    session.add(batch)
    session.flush()

    duplicate_count = 0
    for idx, item in enumerate(
        sorted(payload.files, key=lambda row: (row.original_filename.casefold(), row.sha256_checksum, row.storage_path))
    ):
        duplicate_of = detect_duplicate_scan(session, owner_user_id=owner_user_id, sha256_checksum=item.sha256_checksum)
        if duplicate_of is not None:
            duplicate_count += 1
        row = ScanImage(
            owner_user_id=owner_user_id,
            ingestion_batch_id=int(batch.id or 0),
            sequence_index=idx,
            original_filename=item.original_filename,
            storage_backend="external",
            storage_path=item.storage_path,
            mime_type=item.mime_type,
            width=item.width,
            height=item.height,
            dpi_x=item.dpi_x,
            dpi_y=item.dpi_y,
            normalized_dpi_x=payload.normalized_dpi,
            normalized_dpi_y=payload.normalized_dpi,
            file_size_bytes=item.file_size_bytes,
            sha256_checksum=item.sha256_checksum,
            scanner_make=item.scanner_make,
            scanner_model=item.scanner_model,
            scanner_profile=item.scanner_profile,
            color_mode=item.color_mode,
            processing_status="INGESTED",
            is_duplicate=duplicate_of is not None,
            duplicate_of_scan_image_id=int(duplicate_of.id) if duplicate_of and duplicate_of.id is not None else None,
            failure_reason=None,
            created_at=now,
        )
        session.add(row)
        session.flush()
        _append_event(
            session,
            ingestion_batch_id=int(batch.id or 0),
            scan_image_id=row.id,
            event_type="IMAGE_REGISTERED",
            metadata_json={"sequence_index": idx, "storage_path": row.storage_path, "sha256_checksum": row.sha256_checksum},
        )
        if duplicate_of is not None:
            _append_event(
                session,
                ingestion_batch_id=int(batch.id or 0),
                scan_image_id=row.id,
                event_type="DUPLICATE_DETECTED",
                metadata_json={"duplicate_of_scan_image_id": int(duplicate_of.id or 0)},
            )
    batch.duplicate_count = duplicate_count
    upload_session.successful_files = len(payload.files)
    upload_session.duplicate_files = duplicate_count
    upload_session.completed_at = now
    session.add(upload_session)
    session.add(batch)
    _append_event(
        session,
        ingestion_batch_id=int(batch.id or 0),
        event_type="BATCH_COMPLETED",
        metadata_json={"batch_status": batch.batch_status, "image_count": batch.image_count, "duplicate_count": duplicate_count},
    )
    session.commit()
    session.refresh(batch)
    return _load_batch_detail(session, batch=batch), True


def _get_owner_batch_or_404(session: Session, *, owner_user_id: int, batch_id: int) -> ScanIngestionBatch:
    row = session.get(ScanIngestionBatch, batch_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan ingestion batch not found")
    return row


def _get_owner_scan_image_or_404(session: Session, *, owner_user_id: int, scan_image_id: int) -> ScanImage:
    row = session.get(ScanImage, scan_image_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found")
    return row


def _get_owner_upload_session_or_404(session: Session, *, owner_user_id: int, upload_session_id: int) -> ScanUploadSession:
    row = session.get(ScanUploadSession, upload_session_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan upload session not found")
    return row


def get_scan_ingestion_batch_owner(session: Session, *, owner_user_id: int, batch_id: int) -> ScanIngestionBatchRead:
    return _load_batch_detail(session, batch=_get_owner_batch_or_404(session, owner_user_id=owner_user_id, batch_id=batch_id))


def get_scan_image_owner(session: Session, *, owner_user_id: int, scan_image_id: int) -> ScanImageRead:
    return _load_scan_image_detail(
        session,
        scan_image=_get_owner_scan_image_or_404(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id),
    )


def get_scan_upload_session_owner(session: Session, *, owner_user_id: int, upload_session_id: int) -> ScanUploadSessionRead:
    return _upload_session_read(
        _get_owner_upload_session_or_404(session, owner_user_id=owner_user_id, upload_session_id=upload_session_id)
    )


def list_scan_ingestion_batches_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> ScanIngestionBatchListResponse:
    limit, offset = clamp_scan_ingestion_pagination(limit=limit, offset=offset)
    stmt = (
        select(ScanIngestionBatch)
        .where(ScanIngestionBatch.owner_user_id == owner_user_id)
        .order_by(col(ScanIngestionBatch.created_at).desc(), col(ScanIngestionBatch.id).desc())
    )
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total = session.exec(
        select(func.count()).select_from(ScanIngestionBatch).where(ScanIngestionBatch.owner_user_id == owner_user_id)
    ).one()
    source_counts_rows = session.exec(
        select(ScanIngestionBatch.source_type, func.count())
        .where(ScanIngestionBatch.owner_user_id == owner_user_id)
        .group_by(ScanIngestionBatch.source_type)
    ).all()
    duplicate_image_count = session.exec(
        select(func.count()).select_from(ScanImage).where(ScanImage.owner_user_id == owner_user_id, ScanImage.is_duplicate.is_(True))
    ).one()
    failed_image_count = session.exec(
        select(func.count())
        .select_from(ScanImage)
        .where(ScanImage.owner_user_id == owner_user_id, ScanImage.processing_status == "FAILED")
    ).one()
    return ScanIngestionBatchListResponse(
        items=[_batch_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        source_type_counts={str(key): int(value) for key, value in source_counts_rows},
        duplicate_image_count=int(duplicate_image_count or 0),
        failed_image_count=int(failed_image_count or 0),
    )


def list_scan_ingestion_batches_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanIngestionBatchListResponse:
    limit, offset = clamp_scan_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(ScanIngestionBatch)
    if owner_user_id is not None:
        stmt = stmt.where(ScanIngestionBatch.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanIngestionBatch.created_at).desc(), col(ScanIngestionBatch.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanIngestionBatch)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanIngestionBatch.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()

    source_counts_stmt = select(ScanIngestionBatch.source_type, func.count()).group_by(ScanIngestionBatch.source_type)
    if owner_user_id is not None:
        source_counts_stmt = source_counts_stmt.where(ScanIngestionBatch.owner_user_id == owner_user_id)
    source_counts_rows = session.exec(source_counts_stmt).all()

    duplicate_stmt = select(func.count()).select_from(ScanImage).where(ScanImage.is_duplicate.is_(True))
    failed_stmt = select(func.count()).select_from(ScanImage).where(ScanImage.processing_status == "FAILED")
    if owner_user_id is not None:
        duplicate_stmt = duplicate_stmt.where(ScanImage.owner_user_id == owner_user_id)
        failed_stmt = failed_stmt.where(ScanImage.owner_user_id == owner_user_id)

    return ScanIngestionBatchListResponse(
        items=[_batch_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        source_type_counts={str(key): int(value) for key, value in source_counts_rows},
        duplicate_image_count=int(session.exec(duplicate_stmt).one() or 0),
        failed_image_count=int(session.exec(failed_stmt).one() or 0),
    )


def list_scan_ingestion_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanImageListResponse:
    limit, offset = clamp_scan_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(ScanImage).where(ScanImage.processing_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanImage.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanImage.created_at).desc(), col(ScanImage.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanImage).where(ScanImage.processing_status == "FAILED")
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanImage.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanImageListResponse(
        items=[_image_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
    )
