"""P40-01: Versioned envelope + pagination helpers for /api/v1/scan-ingestion endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SCAN_API_V1_ENGINE_VERSIONS: dict[str, str] = {
    "scan_ingestion": "P40-01",
    "scan_normalization": "P40-02",
}


class ScanApiV1Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    limit: int
    offset: int
    has_next: bool
    next_cursor: str | None = None


class ScanApiV1Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    snapshot_id: str | None = None
    checksum: str | None = None
    generated_at: str = Field(description="RFC3339 / ISO 8601 timestamp in UTC.")
    engine_versions: dict[str, str] = Field(default_factory=lambda: dict(SCAN_API_V1_ENGINE_VERSIONS))


class ScanApiV1Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: Any
    meta: ScanApiV1Meta


def utc_generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_meta(
    *,
    owner_user_id: int | str | None,
    snapshot_id: int | str | None = None,
    checksum: str | None = None,
) -> ScanApiV1Meta:
    oid = str(owner_user_id) if owner_user_id is not None else None
    sid = str(snapshot_id) if snapshot_id is not None else None
    return ScanApiV1Meta(
        owner_user_id=oid,
        snapshot_id=sid,
        checksum=checksum,
        generated_at=utc_generated_at(),
        engine_versions=dict(SCAN_API_V1_ENGINE_VERSIONS),
    )


def wrap_standard_list(payload: BaseModel, *, owner_user_id: int | str | None) -> ScanApiV1Envelope:
    dumped = payload.model_dump(mode="json")
    try:
        items = dumped.pop("items")
        total_items = int(dumped.pop("total_items"))
        limit = int(dumped.pop("limit"))
        offset = int(dumped.pop("offset"))
    except KeyError as exc:  # pragma: no cover - defensive
        raise TypeError(
            "wrap_standard_list expects items, total_items, limit, offset on the payload model.",
        ) from exc
    item_count = len(items)
    pagination = ScanApiV1Pagination(
        total_count=total_items,
        limit=limit,
        offset=offset,
        has_next=offset + item_count < total_items,
        next_cursor=None,
    )
    data: dict[str, Any] = {
        "items": items,
        "pagination": pagination.model_dump(mode="json"),
    }
    data.update(dumped)
    return ScanApiV1Envelope(data=data, meta=build_meta(owner_user_id=owner_user_id))


def wrap_object(
    payload: BaseModel,
    *,
    owner_user_id: int | str | None,
    snapshot_id: int | str | None = None,
    checksum: str | None = None,
) -> ScanApiV1Envelope:
    return ScanApiV1Envelope(
        data=payload.model_dump(mode="json"),
        meta=build_meta(owner_user_id=owner_user_id, snapshot_id=snapshot_id, checksum=checksum),
    )
