"""P40-01: Versioned envelope + pagination helpers for /api/v1/scan-ingestion endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SCAN_API_V1_ENGINE_VERSIONS: dict[str, str] = {
    "scan_ingestion": "P40-01",
    "scan_normalization": "P40-02",
    "scan_boundary": "P40-03",
    "scan_ocr": "P40-04",
    "scan_reconciliation": "P40-05",
    "scan_defects": "P40-06",
    "scan_spine_ticks": "P40-07",
    "scan_corner_edges": "P40-08",
    "scan_surface_defects": "P40-09",
    "scan_structural_damage": "P40-10",
    "scan_defect_aggregation": "P40-11",
    "scan_grading_assistance": "P40-12",
    "scan_visual_evidence": "P40-13",
    "scan_review": "P40-14",
    "scan_historical_comparison": "P40-15",
    "scan_authentication": "P40-16",
    "scan_intelligence_feed": "P41-17",
    "scan_replay": "P40-18",
    "automation_jobs": "P41-01",
    "automation_workers": "P41-02",
    "automation_scheduling": "P41-03",
    "automation_recovery": "P41-04",
    "automation_batch": "P41-05",
    "automation_notifications": "P41-06",
    "automation_ops": "P41-07",
    "automation_rules": "P41-08",
    "automation_analytics": "P41-09",
    "organization_foundation": "P42-01",
    "organization_authorization": "P42-02",
    "auth_security_context": "P42-03",
    "shared_inventory_workflow": "P42-04",
    "organization_review_workflow": "P42-05",
    "dealer_storefront": "P42-06",
    "organization_activity_feed": "P42-07",
    "organization_audit_ledger": "P42-08",
    "organization_dealer_dashboard": "P42-09",
    "marketplace_account_foundation": "P43-01",
    "marketplace_listing_engine": "P43-02",
    "marketplace_inventory_sync": "P43-03",
    "marketplace_order_ingestion": "P43-04",
    "marketplace_pricing_engine": "P43-05",
    "marketplace_event_processing": "P43-06",
    "live_sale_workflows": "P43-07",
    "shopify_sync_layer": "P43-08",
    "marketplace_ops_dashboard": "P43-09",
    "marketplace_analytics": "P43-10",
    "mobile_foundation": "P44-01",
    "offline_inventory_engine": "P44-02",
    "mobile_scanning": "P44-03",
    "convention_mode": "P44-04",
    "quick_sales": "P44-05",
    "mobile_ops_dashboard": "P44-06",
    "mobile_device_security": "P44-07",
    "mobile_analytics": "P44-08",
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
