"""P34 deterministic Fujitsu-style batch ingest (multipart → ScanSessionItem rows).

Scanner drivers + OCR enqueue are out-of-scope. Inventory linkage is manifest-only — never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import ScanSession, ScanSessionItem
from app.models.asset_ledger import utc_now
from app.schemas.scan_sessions import ScanSessionDetailRead, ScanSessionIngestManifestRow
from app.services.cover_images import (
    decode_cover_image_upload_bytes_optional,
    ensure_content_addressable_cover_blob,
    persist_cover_bytes_for_inventory_copy,
    sha256_raw_bytes,
)
from app.services import scan_sessions as scan_sess


_INGEST_READY = frozenset({"imported", "queued_for_ocr", "ocr_complete", "review_required"})
_TERMINAL_SESSION_STATUSES = frozenset({"completed", "completed_with_errors", "cancelled"})


def _norm_filename(value: str | None) -> str:
    return (value or "").strip()


def _stable_idempotency_key(sha_hex: str, filename: str | None) -> tuple[str, str]:
    return (sha_hex.lower(), _norm_filename(filename))


class _SeqAllocator:
    def __init__(self, existing_sequences: Iterable[int]) -> None:
        self.used: set[int] = set(existing_sequences)
        self.next_auto_cursor: int = max(self.used, default=-1) + 1

    def _consume(self, seq: int) -> None:
        self.used.add(seq)
        self.next_auto_cursor = max(self.next_auto_cursor, seq + 1)

    def allocate_automatic(self) -> int:
        seq = self.next_auto_cursor
        while seq in self.used:
            seq += 1
        self._consume(seq)
        return seq

    def allocate_explicit_or_fail_audit(self, requested: int) -> tuple[bool, int]:
        if requested not in self.used:
            self._consume(requested)
            return True, requested
        return False, self.allocate_automatic()


@dataclass
class ParsedScanUploadSlot:
    body: bytes
    declared_content_type: str | None
    upload_filename: str | None
    manifest_row: ScanSessionIngestManifestRow


def ingest_uploaded_images_into_scan_session(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    scan_session_id: int,
    slots: list[ParsedScanUploadSlot],
) -> ScanSessionDetailRead:
    sess_row = scan_sess._assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=scan_session_id)
    if sess_row.status in _TERMINAL_SESSION_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot ingest into a terminated scan session")

    persisted_sorted = scan_sess._sorted_items(
        session.exec(select(ScanSessionItem).where(ScanSessionItem.scan_session_id == scan_session_id)).all()
    )
    allocator = _SeqAllocator(r.sequence_index for r in persisted_sorted)

    dup_success_by_key: dict[tuple[str, str], ScanSessionItem] = {}
    for row in persisted_sorted:
        sha = row.image_sha256
        if sha and row.ingest_status in _INGEST_READY:
            k = _stable_idempotency_key(sha, row.source_filename or None)
            prev = dup_success_by_key.get(k)
            if prev is None or (row.id or 10**18) < (prev.id or 10**18):
                dup_success_by_key[k] = row

    now = utc_now()

    def persist_failure_audit(
        *,
        sequence_index: int,
        ingest_error: str,
        inventory_copy_id: int | None,
        source_filename: str | None,
        sha_hex: str | None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        item = ScanSessionItem(
            scan_session_id=scan_session_id,
            inventory_copy_id=inventory_copy_id,
            cover_image_id=None,
            source_filename=source_filename,
            sequence_index=int(sequence_index),
            ingest_status="failed",
            ingest_error=ingest_error[:7999],
            image_width=width,
            image_height=height,
            image_sha256=sha_hex,
            created_at=now,
            updated_at=now,
        )
        session.add(item)
        session.commit()
        session.refresh(item)

    def persist_import_success(
        *,
        sequence_index: int,
        inventory_copy_id: int | None,
        cover_image_id: int | None,
        source_filename: str | None,
        sha_hex: str,
        width_i: int,
        height_i: int,
    ) -> ScanSessionItem:
        row = ScanSessionItem(
            scan_session_id=scan_session_id,
            inventory_copy_id=inventory_copy_id,
            cover_image_id=cover_image_id,
            source_filename=source_filename,
            sequence_index=int(sequence_index),
            ingest_status="imported",
            ingest_error=None,
            image_width=int(width_i),
            image_height=int(height_i),
            image_sha256=sha_hex.lower(),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    for slot in slots:
        man = slot.manifest_row
        inv_optional = man.inventory_copy_id
        upload_name = slot.upload_filename

        if inv_optional is not None:
            scan_sess._assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=int(inv_optional))

        override_source = (
            (_norm_filename(man.source_filename) or None) if man.source_filename is not None else None
        )
        canon_fn = override_source if override_source is not None else (_norm_filename(upload_name) or None)
        raw_body = slot.body

        if raw_body == b"":
            seq = allocator.allocate_automatic()
            persist_failure_audit(
                sequence_index=int(seq),
                ingest_error="empty upload",
                inventory_copy_id=int(inv_optional) if inv_optional is not None else None,
                source_filename=canon_fn,
                sha_hex=None,
            )
            continue

        sha_hex = sha256_raw_bytes(raw_body)
        ik = _stable_idempotency_key(sha_hex, canon_fn)
        if ik in dup_success_by_key:
            continue

        if len(raw_body) > settings.cover_images_max_bytes:
            seq = allocator.allocate_automatic()
            persist_failure_audit(
                sequence_index=int(seq),
                ingest_error=f"image exceeds ingest cap ({settings.cover_images_max_bytes} bytes)",
                inventory_copy_id=int(inv_optional) if inv_optional is not None else None,
                source_filename=canon_fn,
                sha_hex=sha_hex,
            )
            continue

        decoded = decode_cover_image_upload_bytes_optional(raw_body, slot.declared_content_type)
        if decoded is None:
            seq = allocator.allocate_automatic()
            persist_failure_audit(
                sequence_index=int(seq),
                ingest_error="unsupported or unreadable comic scan payload",
                inventory_copy_id=int(inv_optional) if inv_optional is not None else None,
                source_filename=canon_fn,
                sha_hex=sha_hex,
            )
            continue

        width_i, height_i, mime_i = decoded
        requested_seq = man.sequence_index
        seq_error: str | None = None

        if requested_seq is None:
            seq_use = allocator.allocate_automatic()
        else:
            ok_slot, audit_seq = allocator.allocate_explicit_or_fail_audit(int(requested_seq))
            if ok_slot:
                seq_use = int(requested_seq)
            else:
                seq_use = int(audit_seq)
                seq_error = f"sequence_index {requested_seq} already occupied for this scan session"

        inventory_for_row = int(inv_optional) if inv_optional is not None else None

        cover_id_val: int | None = None
        if seq_error is None:
            try:
                if inventory_for_row is not None:
                    cover_ent = persist_cover_bytes_for_inventory_copy(
                        session,
                        settings,
                        owner_user_id=owner_user_id,
                        inventory_copy_id=inventory_for_row,
                        body=raw_body,
                        mime_type=mime_i,
                        sha256_hex=sha_hex,
                        image_width=int(width_i),
                        image_height=int(height_i),
                        original_filename=canon_fn,
                        source_type="upload",
                    )
                    cover_id_val = int(cover_ent.id or 0) or None
                else:
                    ensure_content_addressable_cover_blob(settings, mime_i, sha_hex, raw_body)
            except HTTPException as exc:
                detail_txt = (
                    exc.detail
                    if isinstance(exc.detail, str)
                    else (str(exc.detail) if exc.detail is not None else "cover ingest rejected")
                )
                persist_failure_audit(
                    sequence_index=int(seq_use),
                    ingest_error=detail_txt,
                    inventory_copy_id=inventory_for_row,
                    source_filename=canon_fn,
                    sha_hex=sha_hex,
                    width=int(width_i),
                    height=int(height_i),
                )
                continue

        if seq_error is not None:
            persist_failure_audit(
                sequence_index=int(seq_use),
                ingest_error=seq_error,
                inventory_copy_id=inventory_for_row,
                source_filename=canon_fn,
                sha_hex=sha_hex,
                width=int(width_i),
                height=int(height_i),
            )
            continue

        added = persist_import_success(
            sequence_index=int(seq_use),
            inventory_copy_id=inventory_for_row,
            cover_image_id=cover_id_val,
            source_filename=canon_fn,
            sha_hex=sha_hex,
            width_i=int(width_i),
            height_i=int(height_i),
        )
        dup_success_by_key[ik] = added

    scan_sess.recompute_scan_session_counters(session, scan_session_id)
    sess_reload = session.get(ScanSession, scan_session_id)
    if sess_reload is None:
        raise HTTPException(status_code=404, detail="Scan session not found")
    scan_sess._touch(sess_reload)
    session.add(sess_reload)
    session.commit()
    session.refresh(sess_reload)

    return scan_sess.get_scan_session_detail(session, owner_user_id=owner_user_id, session_id=scan_session_id)
