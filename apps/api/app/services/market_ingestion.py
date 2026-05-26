from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionBatch,
    MarketAcquisitionIngestionEvent,
    MarketAcquisitionRawSource,
)
from app.schemas.market_ingestion import (
    MarketAcquisitionCandidateRead,
    MarketAcquisitionIngestionBatchCreatePayload,
    MarketAcquisitionIngestionBatchListResponse,
    MarketAcquisitionIngestionBatchRead,
    MarketAcquisitionIngestionBatchSummaryRead,
    MarketAcquisitionIngestionEventRead,
    MarketAcquisitionRawProcessingStatus,
    MarketAcquisitionRawSourceListResponse,
    MarketAcquisitionRawSourceRead,
)

MONEY_QUANT = Decimal("0.01")
ALLOWED_EXTERNAL_SOURCE_TYPES: set[str] = {
    "manual_input",
    "csv_import",
    "api_feed",
    "auction_snapshot",
    "curated_feed",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_market_ingestion_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _trim(value: Any | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_money(value: Any | None, *, field_name: str) -> Decimal | None:
    trimmed = _trim(value)
    if trimmed is None:
        return None
    try:
        return Decimal(trimmed).quantize(MONEY_QUANT)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid decimal") from exc


def _batch_summary_read(row: MarketAcquisitionIngestionBatch) -> MarketAcquisitionIngestionBatchSummaryRead:
    return MarketAcquisitionIngestionBatchSummaryRead.model_validate(row, from_attributes=True)


def _event_read(row: MarketAcquisitionIngestionEvent) -> MarketAcquisitionIngestionEventRead:
    return MarketAcquisitionIngestionEventRead.model_validate(row, from_attributes=True)


def _raw_read(row: MarketAcquisitionRawSource) -> MarketAcquisitionRawSourceRead:
    return MarketAcquisitionRawSourceRead.model_validate(row, from_attributes=True)


def _candidate_read(row: MarketAcquisitionCandidate) -> MarketAcquisitionCandidateRead:
    return MarketAcquisitionCandidateRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, *, batch: MarketAcquisitionIngestionBatch) -> MarketAcquisitionIngestionBatchRead:
    if batch.id is None:
        raise ValueError("ingestion batch must be flushed before serialization")
    events = list(
        session.exec(
            select(MarketAcquisitionIngestionEvent)
            .where(MarketAcquisitionIngestionEvent.ingestion_batch_id == batch.id)
            .order_by(col(MarketAcquisitionIngestionEvent.created_at).asc(), col(MarketAcquisitionIngestionEvent.id).asc())
        ).all(),
    )
    return MarketAcquisitionIngestionBatchRead(
        **_batch_summary_read(batch).model_dump(),
        events=[_event_read(row) for row in events],
    )


def _get_owner_batch_or_404(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
) -> MarketAcquisitionIngestionBatch:
    row = session.get(MarketAcquisitionIngestionBatch, batch_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    return row


def _get_ops_batch_or_404(session: Session, *, batch_id: int) -> MarketAcquisitionIngestionBatch:
    row = session.get(MarketAcquisitionIngestionBatch, batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    return row


def _append_event(
    session: Session,
    *,
    ingestion_batch_id: int,
    event_type: str,
    metadata_json: dict[str, Any],
    created_at: datetime,
) -> None:
    session.add(
        MarketAcquisitionIngestionEvent(
            ingestion_batch_id=ingestion_batch_id,
            event_type=event_type,
            metadata_json=_json_safe(metadata_json),
            created_at=created_at,
        )
    )


def _validate_record(
    record: dict[str, Any],
    *,
    batch_source_type: str,
) -> tuple[dict[str, Any], str]:
    title = _trim(record.get("title"))
    if title is None:
        raise ValueError("title is required")
    external_source_type = _trim(record.get("external_source_type")) or batch_source_type
    if external_source_type not in ALLOWED_EXTERNAL_SOURCE_TYPES:
        raise ValueError("external_source_type is invalid")
    asking_price = _parse_money(record.get("asking_price"), field_name="asking_price")
    external_fmv_estimate = _parse_money(record.get("external_fmv_estimate"), field_name="external_fmv_estimate")
    mapped = {
        "external_source_type": external_source_type,
        "external_listing_id": _trim(record.get("external_listing_id")),
        "source_name": _trim(record.get("source_name")),
        "title": title,
        "publisher": _trim(record.get("publisher")),
        "issue_number": _trim(record.get("issue_number")),
        "variant": _trim(record.get("variant")),
        "condition_raw": _trim(record.get("condition_raw")),
        "asking_price": asking_price,
        "currency": _trim(record.get("currency")),
        "external_fmv_estimate": external_fmv_estimate,
    }
    return mapped, external_source_type


def ingest_market_acquisition_batch_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketAcquisitionIngestionBatchCreatePayload,
) -> tuple[MarketAcquisitionIngestionBatchRead, bool]:
    batch_checksum = _hash_payload(
        {
            "batch_source_type": payload.batch_source_type,
            "records": payload.records,
        }
    )
    existing = session.exec(
        select(MarketAcquisitionIngestionBatch)
        .where(
            MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id,
            MarketAcquisitionIngestionBatch.batch_checksum == batch_checksum,
        )
        .order_by(col(MarketAcquisitionIngestionBatch.created_at).desc(), col(MarketAcquisitionIngestionBatch.id).desc())
    ).first()
    if existing is not None:
        return _detail_read(session, batch=existing), False

    now = utc_now()
    batch = MarketAcquisitionIngestionBatch(
        owner_user_id=owner_user_id,
        batch_source_type=payload.batch_source_type,
        batch_file_name=payload.batch_file_name,
        batch_checksum=batch_checksum,
        total_records=len(payload.records),
        successful_records=0,
        failed_records=0,
        ingestion_status="PROCESSING",
        started_at=now,
        completed_at=None,
        created_at=now,
    )
    session.add(batch)
    session.flush()
    if batch.id is None:
        raise ValueError("market ingestion batch must be flushed before ingest")
    _append_event(
        session,
        ingestion_batch_id=batch.id,
        event_type="BATCH_CREATED",
        metadata_json={
            "batch_checksum": batch_checksum,
            "batch_source_type": payload.batch_source_type,
            "batch_file_name": payload.batch_file_name,
            "total_records": len(payload.records),
        },
        created_at=now,
    )

    for index, raw_record in enumerate(payload.records):
        raw_hash = _hash_payload(raw_record)
        raw_row = MarketAcquisitionRawSource(
            ingestion_batch_id=batch.id,
            raw_record_json=_json_safe(raw_record),
            raw_hash=raw_hash,
            processing_status="PENDING",
            error_message=None,
            created_at=utc_now(),
        )
        session.add(raw_row)
        session.flush()
        try:
            mapped, _ = _validate_record(raw_record, batch_source_type=payload.batch_source_type)
            candidate = MarketAcquisitionCandidate(
                owner_user_id=owner_user_id,
                external_source_type=mapped["external_source_type"],
                external_listing_id=mapped["external_listing_id"],
                source_name=mapped["source_name"],
                title=mapped["title"],
                publisher=mapped["publisher"],
                issue_number=mapped["issue_number"],
                variant=mapped["variant"],
                condition_raw=mapped["condition_raw"],
                asking_price=mapped["asking_price"],
                currency=mapped["currency"],
                external_fmv_estimate=mapped["external_fmv_estimate"],
                raw_payload_json=_json_safe(raw_record),
                ingestion_batch_id=batch.id,
                normalized_flag=False,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(candidate)
            session.flush()
            batch.successful_records += 1
            _append_event(
                session,
                ingestion_batch_id=batch.id,
                event_type="RECORD_PARSED",
                metadata_json={
                    "record_index": index,
                    "raw_hash": raw_hash,
                    "raw_source_id": int(raw_row.id or 0),
                    "candidate_id": int(candidate.id or 0),
                },
                created_at=utc_now(),
            )
        except ValueError as exc:
            raw_row.processing_status = "FAILED"
            raw_row.error_message = str(exc)
            session.add(raw_row)
            batch.failed_records += 1
            _append_event(
                session,
                ingestion_batch_id=batch.id,
                event_type="RECORD_REJECTED",
                metadata_json={
                    "record_index": index,
                    "raw_hash": raw_hash,
                    "raw_source_id": int(raw_row.id or 0),
                    "error_message": str(exc),
                },
                created_at=utc_now(),
            )

    batch.ingestion_status = "FAILED" if batch.successful_records == 0 else "COMPLETED"
    batch.completed_at = utc_now()
    session.add(batch)
    _append_event(
        session,
        ingestion_batch_id=batch.id,
        event_type="BATCH_COMPLETED",
        metadata_json={
            "ingestion_status": batch.ingestion_status,
            "successful_records": batch.successful_records,
            "failed_records": batch.failed_records,
        },
        created_at=batch.completed_at,
    )
    session.commit()
    session.refresh(batch)
    return _detail_read(session, batch=batch), True


def list_ingestion_batches_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionIngestionBatchListResponse:
    limit, offset = clamp_market_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionIngestionBatch).where(MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionIngestionBatch.created_at).desc(),
                col(MarketAcquisitionIngestionBatch.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    status_rows = list(
        session.exec(
            select(
                MarketAcquisitionIngestionBatch.ingestion_status,
                func.count(),
            )
            .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id)
            .group_by(MarketAcquisitionIngestionBatch.ingestion_status)
        ).all(),
    )
    last_ingestion_at = rows[0].completed_at or rows[0].started_at or rows[0].created_at if rows else None
    return MarketAcquisitionIngestionBatchListResponse(
        items=[_batch_summary_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
        status_counts={str(status): int(count) for status, count in status_rows},
        last_ingestion_at=last_ingestion_at,
    )


def list_ingestion_batches_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionIngestionBatchListResponse:
    limit, offset = clamp_market_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionIngestionBatch)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionIngestionBatch.created_at).desc(),
                col(MarketAcquisitionIngestionBatch.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    status_stmt = select(MarketAcquisitionIngestionBatch.ingestion_status, func.count()).group_by(
        MarketAcquisitionIngestionBatch.ingestion_status
    )
    if owner_user_id is not None:
        status_stmt = status_stmt.where(MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id)
    status_rows = list(session.exec(status_stmt).all())
    last_ingestion_at = rows[0].completed_at or rows[0].started_at or rows[0].created_at if rows else None
    return MarketAcquisitionIngestionBatchListResponse(
        items=[_batch_summary_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
        status_counts={str(status): int(count) for status, count in status_rows},
        last_ingestion_at=last_ingestion_at,
    )


def get_ingestion_batch_owner(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
) -> MarketAcquisitionIngestionBatchRead:
    return _detail_read(session, batch=_get_owner_batch_or_404(session, owner_user_id=owner_user_id, batch_id=batch_id))


def get_ingestion_batch_ops(session: Session, *, batch_id: int) -> MarketAcquisitionIngestionBatchRead:
    return _detail_read(session, batch=_get_ops_batch_or_404(session, batch_id=batch_id))


def list_ingestion_raw_owner(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    limit: int = 200,
    offset: int = 0,
) -> MarketAcquisitionRawSourceListResponse:
    batch = _get_owner_batch_or_404(session, owner_user_id=owner_user_id, batch_id=batch_id)
    if batch.id is None:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    limit, offset = clamp_market_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionRawSource).where(MarketAcquisitionRawSource.ingestion_batch_id == batch.id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionRawSource.created_at).asc(), col(MarketAcquisitionRawSource.id).asc())
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionRawSourceListResponse(
        items=[_raw_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_ingestion_raw_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    ingestion_batch_id: int | None = None,
    processing_status: MarketAcquisitionRawProcessingStatus | str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> MarketAcquisitionRawSourceListResponse:
    limit, offset = clamp_market_ingestion_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionRawSource).join(
        MarketAcquisitionIngestionBatch,
        MarketAcquisitionRawSource.ingestion_batch_id == MarketAcquisitionIngestionBatch.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionIngestionBatch.owner_user_id == owner_user_id)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionRawSource.ingestion_batch_id == ingestion_batch_id)
    if processing_status is not None:
        stmt = stmt.where(MarketAcquisitionRawSource.processing_status == processing_status)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(col(MarketAcquisitionRawSource.created_at).asc(), col(MarketAcquisitionRawSource.id).asc())
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionRawSourceListResponse(
        items=[_raw_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
