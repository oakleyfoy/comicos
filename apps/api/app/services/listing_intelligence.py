"""P36-06 deterministic listing intelligence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    ConventionEvent,
    ConventionInventoryAssignment,
    ConventionPriceSnapshot,
    InventoryCopy,
    InventoryLiquiditySnapshot,
    Listing,
    ListingChannelPerformanceSnapshot,
    ListingCompletenessCheck,
    ListingExportRun,
    ListingExportRunItem,
    ListingImage,
    ListingIntelligenceEvidence,
    ListingIntelligenceSnapshot,
    ListingInventoryLink,
    ListingStalenessEvent,
    ListingVelocitySnapshot,
    SaleRecord,
)
from app.models.listing_registry import utc_now as listing_utc_now
from app.schemas.listing_intelligence import (
    ListingChannelPerformanceListResponse,
    ListingChannelPerformanceSnapshotRead,
    ListingCompletenessCheckListResponse,
    ListingCompletenessCheckRead,
    ListingIntelligenceDashboardSummary,
    ListingIntelligenceEvidenceListResponse,
    ListingIntelligenceEvidenceRead,
    ListingIntelligenceGeneratePayload,
    ListingIntelligenceGenerateResponse,
    ListingIntelligenceSnapshotListResponse,
    ListingIntelligenceSnapshotRead,
    ListingIntelligenceStatus,
)
from app.services.listing_registry import list_listing_images

MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
ALLOWED_CHANNELS = frozenset({"ebay", "whatnot", "shopify", "hipcomic", "shortboxed", "convention", "private_sale"})
CHANNEL_ALIASES = {
    "ebay": "ebay",
    "ebay_export": "ebay",
    "whatnot": "whatnot",
    "shopify": "shopify",
    "hipcomic": "hipcomic",
    "shortboxed": "shortboxed",
    "convention": "convention",
    "manual": "private_sale",
    "private_sale": "private_sale",
}


def clamp_listing_intelligence_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_channel(source_type: str | None) -> str | None:
    if source_type is None:
        return None
    normalized = str(source_type).strip().lower()
    return CHANNEL_ALIASES.get(normalized, normalized)


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized not in {"STRONG", "ADEQUATE", "WEAK", "INCOMPLETE", "INSUFFICIENT_DATA"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid intelligence status filter")
    return normalized


def _normalize_check_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized not in {"PASS", "WARNING", "FAIL"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid completeness status filter")
    return normalized


def _normalize_check_severity(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in {"info", "warning", "critical"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid completeness severity filter")
    return normalized


def _owner_listing(session: Session, *, owner_user_id: int, listing_id: int) -> Listing:
    row = session.exec(
        select(Listing).where(Listing.id == listing_id, Listing.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return row


def _inventory_copy(session: Session, *, owner_user_id: int, inventory_item_id: int) -> InventoryCopy:
    row = session.get(InventoryCopy, inventory_item_id)
    if row is None or int(row.user_id or 0) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory copy not found")
    return row


def _listing_images_sorted(session: Session, listing_id: int) -> list[ListingImage]:
    imgs = list_listing_images(session, listing_id)
    primary_index: int | None = None
    for idx, img in enumerate(imgs):
        if str(img.role).lower() == "primary":
            primary_index = idx
            break
    if primary_index is not None and primary_index > 0:
        return [imgs[primary_index], *[img for idx, img in enumerate(imgs) if idx != primary_index]]
    return imgs


def _score_title(title: str | None) -> tuple[Decimal, bool, str]:
    if title is None or not title.strip():
        return ZERO, False, "title missing"
    if len(title.strip()) >= 8:
        return _money(20), True, ""
    return _money(10), True, "title short"


def _score_description(description: str | None) -> tuple[Decimal, bool, str]:
    if description is None or not description.strip():
        return ZERO, False, "description missing"
    if len(description.strip()) >= 40:
        return _money(20), True, ""
    return _money(10), True, "description short"


def _score_condition(condition_summary: str | None) -> tuple[Decimal, bool, str]:
    if condition_summary is None or not condition_summary.strip():
        return ZERO, False, "condition missing"
    return _money(15), True, ""


def _score_price(amount: Decimal | None, currency: str | None) -> tuple[Decimal, bool, str]:
    if amount is None or currency is None:
        return ZERO, False, "price missing"
    return _money(15), True, ""


def _score_images(images: list[ListingImage]) -> tuple[Decimal, bool, bool, str]:
    if not images:
        return ZERO, False, False, "image missing"
    primary_exists = any(str(img.role).lower() == "primary" for img in images)
    if primary_exists:
        return _money(20), True, True, ""
    return _money(10), True, False, "primary image missing"


def _score_inventory_link(link_exists: bool) -> tuple[Decimal, bool, str]:
    if link_exists:
        return _money(10), True, ""
    return ZERO, False, "inventory link missing"


def _classify_status(*, evidence_count: int, completeness_score: Decimal) -> ListingIntelligenceStatus:
    if evidence_count == 0:
        return "INSUFFICIENT_DATA"
    score = int(completeness_score)
    if score >= 85:
        return "STRONG"
    if score >= 65:
        return "ADEQUATE"
    if score >= 40:
        return "WEAK"
    return "INCOMPLETE"


def _export_ready(*, title_ok: bool, condition_ok: bool, price_ok: bool, currency_ok: bool, inventory_ok: bool, status: str) -> bool:
    return bool(
        title_ok
        and condition_ok
        and price_ok
        and currency_ok
        and inventory_ok
        and status in {"READY", "ACTIVE"}
    )


def _check_status_for(required: bool) -> str:
    return "PASS" if required else "FAIL"


def _check_severity_for(required: bool, warning: bool = False) -> str:
    if required:
        return "info"
    if warning:
        return "warning"
    return "critical"


def _snapshot_read(row: ListingIntelligenceSnapshot) -> ListingIntelligenceSnapshotRead:
    return ListingIntelligenceSnapshotRead.model_validate(row, from_attributes=True)


def _evidence_read(row: ListingIntelligenceEvidence) -> ListingIntelligenceEvidenceRead:
    return ListingIntelligenceEvidenceRead.model_validate(row, from_attributes=True)


def _check_read(row: ListingCompletenessCheck) -> ListingCompletenessCheckRead:
    return ListingCompletenessCheckRead.model_validate(row, from_attributes=True)


def _channel_perf_read(row: ListingChannelPerformanceSnapshot) -> ListingChannelPerformanceSnapshotRead:
    return ListingChannelPerformanceSnapshotRead.model_validate(row, from_attributes=True)


def _listing_intelligence_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    stale_risk_flag: bool | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
):
    intelligence_status = _normalize_status(intelligence_status)
    channel = _normalize_channel(channel) if channel is not None else None
    query = select(ListingIntelligenceSnapshot)
    if owner_user_id is not None:
        query = query.where(ListingIntelligenceSnapshot.owner_user_id == owner_user_id)
    if listing_id is not None:
        query = query.where(ListingIntelligenceSnapshot.listing_id == listing_id)
    if inventory_item_id is not None:
        query = query.where(ListingIntelligenceSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        query = query.where(ListingIntelligenceSnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    if channel is not None:
        query = query.where(ListingIntelligenceSnapshot.channel == channel)
    if intelligence_status is not None:
        query = query.where(ListingIntelligenceSnapshot.intelligence_status == intelligence_status)
    if stale_risk_flag is not None:
        query = query.where(ListingIntelligenceSnapshot.stale_risk_flag == stale_risk_flag)
    if snapshot_date_from is not None:
        query = query.where(ListingIntelligenceSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        query = query.where(ListingIntelligenceSnapshot.snapshot_date <= snapshot_date_to)
    return query.order_by(
        col(ListingIntelligenceSnapshot.snapshot_date).desc(),
        col(ListingIntelligenceSnapshot.created_at).desc(),
        col(ListingIntelligenceSnapshot.id).desc(),
    )


def _check_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    check_status: str | None = None,
    severity: str | None = None,
):
    channel = _normalize_channel(channel) if channel is not None else None
    check_status = _normalize_check_status(check_status)
    severity = _normalize_check_severity(severity)
    query = select(ListingCompletenessCheck)
    if owner_user_id is not None:
        query = query.where(ListingCompletenessCheck.owner_user_id == owner_user_id)
    if listing_id is not None:
        query = query.where(ListingCompletenessCheck.listing_id == listing_id)
    if check_status is not None:
        query = query.where(ListingCompletenessCheck.status == check_status)
    if severity is not None:
        query = query.where(ListingCompletenessCheck.severity == severity)
    if snapshot_date_from is not None:
        query = query.where(ListingCompletenessCheck.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        query = query.where(ListingCompletenessCheck.snapshot_date <= snapshot_date_to)
    if channel is not None:
        query = query.join(
            ListingIntelligenceSnapshot,
            ListingCompletenessCheck.intelligence_snapshot_id == ListingIntelligenceSnapshot.id,
        ).where(ListingIntelligenceSnapshot.channel == channel)
    return query.order_by(
        col(ListingCompletenessCheck.snapshot_date).desc(),
        col(ListingCompletenessCheck.created_at).desc(),
        col(ListingCompletenessCheck.id).desc(),
    )


def _evidence_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
):
    query = select(ListingIntelligenceEvidence).join(
        ListingIntelligenceSnapshot,
        ListingIntelligenceEvidence.intelligence_snapshot_id == ListingIntelligenceSnapshot.id,
    )
    if owner_user_id is not None:
        query = query.where(ListingIntelligenceSnapshot.owner_user_id == owner_user_id)
    if listing_id is not None:
        query = query.where(ListingIntelligenceSnapshot.listing_id == listing_id)
    if inventory_item_id is not None:
        query = query.where(ListingIntelligenceSnapshot.inventory_item_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        query = query.where(ListingIntelligenceSnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    if channel is not None:
        query = query.where(ListingIntelligenceSnapshot.channel == _normalize_channel(channel))
    if intelligence_status is not None:
        query = query.where(ListingIntelligenceSnapshot.intelligence_status == _normalize_status(intelligence_status))
    if snapshot_date_from is not None:
        query = query.where(ListingIntelligenceSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        query = query.where(ListingIntelligenceSnapshot.snapshot_date <= snapshot_date_to)
    return query.order_by(
        col(ListingIntelligenceSnapshot.snapshot_date).desc(),
        col(ListingIntelligenceEvidence.evidence_type).asc(),
        col(ListingIntelligenceEvidence.evidence_key).asc(),
        col(ListingIntelligenceEvidence.id).asc(),
    )


def _channel_perf_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
):
    query = select(ListingChannelPerformanceSnapshot)
    if owner_user_id is not None:
        query = query.where(ListingChannelPerformanceSnapshot.owner_user_id == owner_user_id)
    if channel is not None:
        query = query.where(ListingChannelPerformanceSnapshot.channel == _normalize_channel(channel))
    if snapshot_date_from is not None:
        query = query.where(ListingChannelPerformanceSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        query = query.where(ListingChannelPerformanceSnapshot.snapshot_date <= snapshot_date_to)
    return query.order_by(
        col(ListingChannelPerformanceSnapshot.snapshot_date).desc(),
        col(ListingChannelPerformanceSnapshot.channel).asc(),
        col(ListingChannelPerformanceSnapshot.id).desc(),
    )


def _existing_intelligence_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int,
    snapshot_date: date,
) -> ListingIntelligenceSnapshot | None:
    return session.exec(
        select(ListingIntelligenceSnapshot).where(
            ListingIntelligenceSnapshot.owner_user_id == owner_user_id,
            ListingIntelligenceSnapshot.listing_id == listing_id,
            ListingIntelligenceSnapshot.snapshot_date == snapshot_date,
        )
    ).first()


def _existing_channel_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    channel: str,
    snapshot_date: date,
) -> ListingChannelPerformanceSnapshot | None:
    return session.exec(
        select(ListingChannelPerformanceSnapshot).where(
            ListingChannelPerformanceSnapshot.owner_user_id == owner_user_id,
            ListingChannelPerformanceSnapshot.channel == channel,
            ListingChannelPerformanceSnapshot.snapshot_date == snapshot_date,
        )
    ).first()


def _build_listing_checks(
    *,
    snapshot: ListingIntelligenceSnapshot,
    listing: Listing,
    image_score: Decimal,
    title_ok: bool,
    description_ok: bool,
    condition_ok: bool,
    price_ok: bool,
    currency_ok: bool,
    primary_image_ok: bool,
    image_present: bool,
    inventory_link_ok: bool,
    export_ready: bool,
) -> list[ListingCompletenessCheck]:
    status_map = {
        "title_present": title_ok,
        "description_present": description_ok,
        "condition_present": condition_ok,
        "price_present": price_ok,
        "currency_present": currency_ok,
        "image_present": image_present,
        "primary_image_present": primary_image_ok,
        "inventory_link_present": inventory_link_ok,
        "exportable_status": export_ready,
    }
    checks: list[ListingCompletenessCheck] = []
    for key, ok in status_map.items():
        if ok:
            status_value = "PASS"
            severity_value = "info"
            message = f"{key} passed"
        elif key in {"image_present", "primary_image_present"}:
            status_value = "WARNING"
            severity_value = "warning"
            message = f"{key} missing or incomplete"
        elif key == "exportable_status":
            status_value = "WARNING"
            severity_value = "warning"
            message = "listing not export-ready"
        else:
            status_value = "FAIL"
            severity_value = "critical"
            message = f"{key} missing"
        checks.append(
            ListingCompletenessCheck(
                intelligence_snapshot_id=int(snapshot.id or 0),
                owner_user_id=int(snapshot.owner_user_id),
                listing_id=int(listing.id or 0),
                replay_key=snapshot.replay_key,
                status=status_value,
                check_key=key,
                message=message,
                severity=severity_value,
                snapshot_date=snapshot.snapshot_date,
                created_at=listing_utc_now(),
            )
        )
    return checks


def _latest_sales_for_listing(session: Session, listing_id: int) -> list[SaleRecord]:
    return list(
        session.exec(
            select(SaleRecord)
            .where(SaleRecord.listing_id == listing_id)
            .order_by(col(SaleRecord.sale_date).desc(), col(SaleRecord.id).desc())
        ).all()
    )


def _latest_liquidity_for_inventory(
    session: Session,
    inventory_item_id: int | None,
) -> InventoryLiquiditySnapshot | None:
    if inventory_item_id is None:
        return None
    return session.exec(
        select(InventoryLiquiditySnapshot)
        .where(InventoryLiquiditySnapshot.inventory_item_id == inventory_item_id)
        .order_by(
            col(InventoryLiquiditySnapshot.snapshot_date).desc(),
            col(InventoryLiquiditySnapshot.created_at).desc(),
            col(InventoryLiquiditySnapshot.id).desc(),
        )
    ).first()


def _latest_convention_event_for_inventory(
    session: Session,
    inventory_item_id: int | None,
) -> ConventionEvent | None:
    if inventory_item_id is None:
        return None
    assignment = session.exec(
        select(ConventionInventoryAssignment)
        .where(
            ConventionInventoryAssignment.inventory_item_id == inventory_item_id,
            ConventionInventoryAssignment.removed_at.is_(None),
        )
        .order_by(
            col(ConventionInventoryAssignment.created_at).desc(),
            col(ConventionInventoryAssignment.id).desc(),
        )
    ).first()
    if assignment is None:
        return None
    return session.get(ConventionEvent, assignment.convention_event_id)


def _build_listing_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    listing: Listing,
    snapshot_date: date,
    replay_key: str | None,
) -> tuple[ListingIntelligenceSnapshot, list[ListingIntelligenceEvidence], list[ListingCompletenessCheck]]:
    images = _listing_images_sorted(session, int(listing.id))
    inventory_link = session.exec(
        select(ListingInventoryLink).where(ListingInventoryLink.listing_id == listing.id)
    ).first()
    inventory_copy = session.get(InventoryCopy, listing.inventory_copy_id)
    channel = _normalize_channel(listing.source_type)
    title_score, title_ok, title_warning = _score_title(listing.title)
    description_score, description_ok, description_warning = _score_description(listing.description)
    condition_score, condition_ok, condition_warning = _score_condition(listing.condition_summary)
    price_score, price_ok, price_warning = _score_price(listing.asking_price_amount, listing.asking_price_currency)
    image_score, image_present, primary_image_ok, image_warning = _score_images(images)
    inventory_score, inventory_ok, inventory_warning = _score_inventory_link(inventory_link is not None)
    completeness_score = _money(title_score + description_score + condition_score + price_score + image_score + inventory_score)
    export_ready = _export_ready(
        title_ok=title_ok,
        condition_ok=condition_ok,
        price_ok=price_ok,
        currency_ok=listing.asking_price_currency is not None,
        inventory_ok=inventory_ok,
        status=listing.status,
    )
    sale_records = _latest_sales_for_listing(session, int(listing.id))
    sale_outcome_score: Decimal | None
    if any(row.status == "RECORDED" for row in sale_records):
        sale_outcome_score = _money(100)
    elif listing.status in {"CANCELLED", "ARCHIVED"}:
        sale_outcome_score = _money(0)
    elif sale_records:
        sale_outcome_score = _money(50)
    else:
        sale_outcome_score = None
    stale_risk_flag = bool(
        session.exec(
            select(ListingStalenessEvent).where(ListingStalenessEvent.listing_id == listing.id)
        ).first()
    )
    warning_flags: list[str] = []
    if title_warning:
        warning_flags.append("SHORT_TITLE")
    if description_warning:
        warning_flags.append("SHORT_DESCRIPTION")
    if condition_warning:
        warning_flags.append("MISSING_CONDITION")
    if price_warning:
        warning_flags.append("MISSING_PRICE")
    if image_warning:
        warning_flags.append("MISSING_PRIMARY_IMAGE" if not primary_image_ok else "MISSING_IMAGES")
    if inventory_warning:
        warning_flags.append("MISSING_INVENTORY_LINK")
    if stale_risk_flag:
        warning_flags.append("STALE_RISK")
    if not export_ready:
        warning_flags.append("NOT_EXPORT_READY")
    if sale_outcome_score is None:
        warning_flags.append("NO_SALE_OUTCOME")
    missing_required_fields = [key for key, ok in {
        "title": title_ok,
        "description": description_ok,
        "condition": condition_ok,
        "price": price_ok,
        "currency": listing.asking_price_currency is not None,
        "inventory_link": inventory_ok,
    }.items() if not ok]
    evidence_rows: list[ListingIntelligenceEvidence] = []

    def add_evidence(
        *,
        evidence_type: str,
        evidence_key: str,
        evidence_value_json: dict[str, Any],
        source_listing_id: int | None = None,
        source_export_run_id: int | None = None,
        source_sale_id: int | None = None,
        source_liquidity_snapshot_id: int | None = None,
        source_convention_event_id: int | None = None,
    ) -> None:
        evidence_rows.append(
            ListingIntelligenceEvidence(
                intelligence_snapshot_id=0,
                evidence_type=evidence_type,
                source_listing_id=source_listing_id,
                source_export_run_id=source_export_run_id,
                source_sale_id=source_sale_id,
                source_liquidity_snapshot_id=source_liquidity_snapshot_id,
                source_convention_event_id=source_convention_event_id,
                evidence_key=evidence_key,
                evidence_value_json=evidence_value_json,
                created_at=listing_utc_now(),
            )
        )

    add_evidence(
        evidence_type="LISTING_FIELD",
        evidence_key="title",
        evidence_value_json={"value": listing.title, "present": title_ok},
        source_listing_id=listing.id,
    )
    add_evidence(
        evidence_type="LISTING_FIELD",
        evidence_key="description",
        evidence_value_json={"value": listing.description, "present": description_ok},
        source_listing_id=listing.id,
    )
    add_evidence(
        evidence_type="LISTING_FIELD",
        evidence_key="condition_summary",
        evidence_value_json={"value": listing.condition_summary, "present": condition_ok},
        source_listing_id=listing.id,
    )
    add_evidence(
        evidence_type="PRICE",
        evidence_key="asking_price",
        evidence_value_json={
            "amount": str(listing.asking_price_amount) if listing.asking_price_amount is not None else None,
            "currency": listing.asking_price_currency,
            "present": price_ok,
        },
        source_listing_id=listing.id,
    )
    add_evidence(
        evidence_type="IMAGE",
        evidence_key="images",
        evidence_value_json={
            "image_count": len(images),
            "primary_image_present": primary_image_ok,
            "present": image_present,
        },
        source_listing_id=listing.id,
    )
    add_evidence(
        evidence_type="LISTING_FIELD",
        evidence_key="inventory_link",
        evidence_value_json={
            "inventory_copy_id": inventory_link.inventory_copy_id if inventory_link else None,
            "present": inventory_ok,
        },
        source_listing_id=listing.id,
    )
    if inventory_copy is not None:
        add_evidence(
            evidence_type="LISTING_FIELD",
            evidence_key="inventory_copy",
            evidence_value_json={
                "inventory_copy_id": inventory_copy.id,
                "order_item_id": inventory_copy.order_item_id,
                "canonical_series_id": inventory_copy.canonical_series_id,
            },
            source_listing_id=listing.id,
        )
    for idx, img in enumerate(images, start=1):
        add_evidence(
            evidence_type="IMAGE",
            evidence_key=f"image_{idx}",
            evidence_value_json={
                "display_order": img.display_order,
                "role": img.role,
                "cover_image_id": img.cover_image_id,
                "scan_session_item_id": img.scan_session_item_id,
            },
            source_listing_id=listing.id,
        )
    for sale in sale_records:
        add_evidence(
            evidence_type="SALE",
            evidence_key=f"sale_{sale.id}",
            evidence_value_json={
                "status": sale.status,
                "channel": sale.channel,
                "sale_date": sale.sale_date.isoformat(),
                "gross_sale_amount": str(sale.gross_sale_amount),
                "net_proceeds_amount": str(sale.net_proceeds_amount),
            },
            source_listing_id=listing.id,
            source_sale_id=sale.id,
        )
    liquidity = _latest_liquidity_for_inventory(session, listing.inventory_copy_id)
    if liquidity is not None:
        add_evidence(
            evidence_type="LIQUIDITY",
            evidence_key=f"liquidity_{liquidity.id}",
            evidence_value_json={
                "snapshot_date": liquidity.snapshot_date.isoformat(),
                "liquidity_status": liquidity.liquidity_status,
                "stale_listing_rate_pct": str(liquidity.stale_listing_rate_pct),
                "sell_through_rate_pct": str(liquidity.sell_through_rate_pct),
            },
            source_listing_id=listing.id,
            source_liquidity_snapshot_id=liquidity.id,
        )
    convention_event = _latest_convention_event_for_inventory(session, listing.inventory_copy_id)
    if convention_event is not None:
        add_evidence(
            evidence_type="CONVENTION",
            evidence_key=f"convention_{convention_event.id}",
            evidence_value_json={
                "name": convention_event.name,
                "status": convention_event.status,
                "event_type": convention_event.event_type,
                "start_date": convention_event.start_date.isoformat(),
                "end_date": convention_event.end_date.isoformat(),
            },
            source_listing_id=listing.id,
            source_convention_event_id=convention_event.id,
        )
    export_runs = session.exec(
        select(ListingExportRun)
        .join(ListingExportRunItem, ListingExportRunItem.export_run_id == ListingExportRun.id)
        .where(ListingExportRunItem.listing_id == listing.id)
        .order_by(col(ListingExportRun.created_at).desc(), col(ListingExportRun.id).desc())
    ).all()
    for run in export_runs:
        add_evidence(
            evidence_type="EXPORT_RUN",
            evidence_key=f"export_run_{run.id}",
            evidence_value_json={
                "channel": run.channel,
                "status": run.status,
                "exported_listing_count": run.exported_listing_count,
                "skipped_listing_count": run.skipped_listing_count,
                "checksum": run.checksum,
            },
            source_listing_id=listing.id,
            source_export_run_id=run.id,
        )
    evidence_rows.sort(
        key=lambda row: (
            row.evidence_type,
            row.evidence_key,
            int(row.source_listing_id or 0),
            int(row.source_export_run_id or 0),
            int(row.source_sale_id or 0),
            int(row.source_liquidity_snapshot_id or 0),
            int(row.source_convention_event_id or 0),
        )
    )
    evidence_count = len(evidence_rows)
    intelligence_status = _classify_status(evidence_count=evidence_count, completeness_score=completeness_score)
    snapshot_payload = {
        "owner_user_id": owner_user_id,
        "listing_id": listing.id,
        "inventory_item_id": listing.inventory_copy_id,
        "canonical_comic_issue_id": listing.canonical_comic_issue_id,
        "channel": channel,
        "status": intelligence_status,
        "completeness_score": str(completeness_score),
        "image_score": str(image_score),
        "title_score": str(title_score),
        "description_score": str(description_score),
        "pricing_score": str(price_score),
        "export_readiness_score": str(_money(100 if export_ready else 0)),
        "sale_outcome_score": str(sale_outcome_score) if sale_outcome_score is not None else None,
        "stale_risk_flag": stale_risk_flag,
        "missing_required_fields": missing_required_fields,
        "warning_flags": warning_flags,
        "snapshot_date": snapshot_date,
        "evidence": [
            {
                "type": e.evidence_type,
                "key": e.evidence_key,
                "value": e.evidence_value_json,
                "source_listing_id": e.source_listing_id,
                "source_export_run_id": e.source_export_run_id,
                "source_sale_id": e.source_sale_id,
                "source_liquidity_snapshot_id": e.source_liquidity_snapshot_id,
                "source_convention_event_id": e.source_convention_event_id,
            }
            for e in evidence_rows
        ],
    }
    checksum = _hash_payload(snapshot_payload)
    snapshot = ListingIntelligenceSnapshot(
        owner_user_id=owner_user_id,
        listing_id=listing.id,
        inventory_item_id=listing.inventory_copy_id,
        canonical_comic_issue_id=listing.canonical_comic_issue_id,
        channel=channel,
        replay_key=replay_key,
        intelligence_status=intelligence_status,
        completeness_score=completeness_score,
        image_score=image_score,
        title_score=title_score,
        description_score=description_score,
        pricing_score=price_score,
        export_readiness_score=_money(100 if export_ready else 0),
        sale_outcome_score=sale_outcome_score,
        stale_risk_flag=stale_risk_flag,
        missing_required_fields_json=missing_required_fields,
        warning_flags_json=warning_flags,
        evidence_count=evidence_count,
        checksum=checksum,
        snapshot_date=snapshot_date,
        created_at=listing_utc_now(),
    )
    return snapshot, evidence_rows, _build_listing_checks(
        snapshot=snapshot,
        listing=listing,
        image_score=image_score,
        title_ok=title_ok,
        description_ok=description_ok,
        condition_ok=condition_ok,
        price_ok=price_ok,
        currency_ok=listing.asking_price_currency is not None,
        primary_image_ok=primary_image_ok,
        image_present=image_present,
        inventory_link_ok=inventory_ok,
        export_ready=export_ready,
    )


def _channel_snapshot_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str,
    snapshot_date: date,
    replay_key: str | None,
) -> ListingChannelPerformanceSnapshot:
    listings = session.exec(
        select(Listing)
        .where(Listing.owner_user_id == owner_user_id)
        .order_by(col(Listing.created_at).asc(), col(Listing.id).asc())
    ).all()
    relevant_listings = [row for row in listings if _normalize_channel(row.source_type) == channel]
    active_listings = sum(1 for row in relevant_listings if row.status == "ACTIVE")
    sold_listings = sum(1 for row in relevant_listings if row.status == "SOLD")
    cancelled_listings = sum(1 for row in relevant_listings if row.status in {"CANCELLED", "ARCHIVED"})
    exported_count = int(
        session.scalar(
            select(func.count())
            .select_from(ListingExportRunItem)
            .join(ListingExportRun, ListingExportRun.id == ListingExportRunItem.export_run_id)
            .where(ListingExportRun.owner_user_id == owner_user_id, ListingExportRun.channel == channel, ListingExportRunItem.status == "EXPORTED")
        )
        or 0
    )
    sales = session.exec(
        select(SaleRecord).where(SaleRecord.owner_user_id == owner_user_id, SaleRecord.channel == channel, SaleRecord.status == "RECORDED")
    ).all()
    sales_count = len(sales)
    gross_sales = _money(sum((_decimal(row.gross_sale_amount) for row in sales), ZERO))
    net_proceeds = _money(sum((_decimal(row.net_proceeds_amount) for row in sales), ZERO))
    velocity_rows = session.exec(
        select(ListingVelocitySnapshot)
        .where(ListingVelocitySnapshot.owner_user_id == owner_user_id, ListingVelocitySnapshot.final_status == "SOLD")
        .order_by(col(ListingVelocitySnapshot.created_at).desc(), col(ListingVelocitySnapshot.id).desc())
    ).all()
    relevant_listing_ids = {int(l.id) for l in relevant_listings}
    latest_velocity_by_listing: dict[int, ListingVelocitySnapshot] = {}
    for row in velocity_rows:
        if row.listing_id in relevant_listing_ids and row.listing_id not in latest_velocity_by_listing:
            latest_velocity_by_listing[row.listing_id] = row
    channel_velocity_days = [
        _decimal(row.days_active) for row in latest_velocity_by_listing.values() if row.days_active is not None
    ]
    if channel_velocity_days:
        ordered = sorted(channel_velocity_days)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            median_days = _money(ordered[mid])
        else:
            median_days = _money((ordered[mid - 1] + ordered[mid]) / Decimal("2"))
    else:
        median_days = None
    stale_listing_count = int(
        session.scalar(
            select(func.count(func.distinct(ListingStalenessEvent.listing_id)))
            .select_from(ListingStalenessEvent)
            .join(Listing, Listing.id == ListingStalenessEvent.listing_id)
            .where(Listing.owner_user_id == owner_user_id, Listing.id.in_(relevant_listing_ids))
        )
        or 0
    )
    payload = {
        "owner_user_id": owner_user_id,
        "channel": channel,
        "total_listings": len(relevant_listings),
        "active_listings": active_listings,
        "sold_listings": sold_listings,
        "cancelled_listings": cancelled_listings,
        "exported_count": exported_count,
        "sales_count": sales_count,
        "gross_sales_amount": str(gross_sales),
        "net_proceeds_amount": str(net_proceeds),
        "median_days_to_sale": str(median_days) if median_days is not None else None,
        "stale_listing_count": stale_listing_count,
        "snapshot_date": snapshot_date,
    }
    checksum = _hash_payload(payload)
    return ListingChannelPerformanceSnapshot(
        owner_user_id=owner_user_id,
        channel=channel,
        replay_key=replay_key,
        total_listings=len(relevant_listings),
        active_listings=active_listings,
        sold_listings=sold_listings,
        cancelled_listings=cancelled_listings,
        exported_count=exported_count,
        sales_count=sales_count,
        gross_sales_amount=gross_sales,
        net_proceeds_amount=net_proceeds,
        median_days_to_sale=median_days,
        stale_listing_count=stale_listing_count,
        checksum=checksum,
        snapshot_date=snapshot_date,
        created_at=listing_utc_now(),
    )


def generate_listing_intelligence(
    session: Session,
    *,
    owner_user_id: int,
    payload: ListingIntelligenceGeneratePayload | dict | None = None,
) -> ListingIntelligenceGenerateResponse:
    if payload is None:
        payload = ListingIntelligenceGeneratePayload()
    elif not isinstance(payload, ListingIntelligenceGeneratePayload):
        payload = ListingIntelligenceGeneratePayload.model_validate(payload)
    snapshot_date = payload.snapshot_date or listing_utc_now().date()
    query = select(Listing).where(Listing.owner_user_id == owner_user_id)
    if payload.listing_id is not None:
        query = query.where(Listing.id == payload.listing_id)
    if payload.inventory_item_id is not None:
        query = query.where(Listing.inventory_copy_id == payload.inventory_item_id)
    if payload.canonical_comic_issue_id is not None:
        query = query.where(Listing.canonical_comic_issue_id == payload.canonical_comic_issue_id)
    if payload.channel is not None:
        query = query.where(Listing.source_type == payload.channel)
    listings = session.exec(query.order_by(col(Listing.created_at).asc(), col(Listing.id).asc())).all()
    if payload.channel is not None:
        channel_filter = _normalize_channel(payload.channel)
        listings = [row for row in listings if _normalize_channel(row.source_type) == channel_filter]
    generated_snapshot_count = 0
    generated_evidence_count = 0
    generated_check_count = 0
    checksums: list[str] = []
    for listing in listings:
        existing = _existing_intelligence_snapshot(
            session,
            owner_user_id=owner_user_id,
            listing_id=int(listing.id),
            snapshot_date=snapshot_date,
        )
        if existing is not None:
            generated_snapshot_count += 1
            checksums.append(existing.checksum)
            continue
        snapshot, evidence_rows, check_rows = _build_listing_snapshot(
            session,
            owner_user_id=owner_user_id,
            listing=listing,
            snapshot_date=snapshot_date,
            replay_key=payload.replay_key,
        )
        session.add(snapshot)
        session.flush()
        for evidence in evidence_rows:
            evidence.intelligence_snapshot_id = int(snapshot.id or 0)
            session.add(evidence)
        for check in check_rows:
            check.intelligence_snapshot_id = int(snapshot.id or 0)
            session.add(check)
        generated_snapshot_count += 1
        generated_evidence_count += len(evidence_rows)
        generated_check_count += len(check_rows)
        checksums.append(snapshot.checksum)
    channels = sorted({_normalize_channel(row.source_type) or "unknown" for row in listings})
    for channel in channels:
        if channel is None:
            continue
        existing_channel = _existing_channel_snapshot(
            session,
            owner_user_id=owner_user_id,
            channel=channel,
            snapshot_date=snapshot_date,
        )
        if existing_channel is not None:
            checksums.append(existing_channel.checksum)
            continue
        channel_snapshot = _channel_snapshot_for_owner(
            session,
            owner_user_id=owner_user_id,
            channel=channel,
            snapshot_date=snapshot_date,
            replay_key=payload.replay_key,
        )
        session.add(channel_snapshot)
        session.flush()
        checksums.append(channel_snapshot.checksum)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Re-read existing rows for replay-safe behavior.
        return generate_listing_intelligence(session, owner_user_id=owner_user_id, payload=payload)
    final_checksum = _hash_payload(
        {
            "owner_user_id": owner_user_id,
            "snapshot_date": snapshot_date,
            "listing_ids": [int(row.id) for row in listings],
            "checksums": checksums,
        }
    )
    return ListingIntelligenceGenerateResponse(
        generated_snapshot_count=generated_snapshot_count,
        generated_evidence_count=generated_evidence_count,
        generated_check_count=generated_check_count,
        generated_channel_performance_count=len(channels),
        checksum=final_checksum,
        snapshot_date=snapshot_date,
        replay_key=payload.replay_key,
    )


def build_listing_intelligence_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> ListingIntelligenceDashboardSummary:
    query = select(ListingIntelligenceSnapshot).order_by(
        col(ListingIntelligenceSnapshot.snapshot_date).desc(),
        col(ListingIntelligenceSnapshot.created_at).desc(),
        col(ListingIntelligenceSnapshot.id).desc(),
    )
    if owner_user_id is not None:
        query = query.where(ListingIntelligenceSnapshot.owner_user_id == owner_user_id)
    snapshots = session.exec(query).all()
    latest_by_listing: dict[int, ListingIntelligenceSnapshot] = {}
    for row in snapshots:
        if row.listing_id not in latest_by_listing:
            latest_by_listing[row.listing_id] = row
    latest = list(latest_by_listing.values())
    strong = sum(1 for row in latest if row.intelligence_status == "STRONG")
    incomplete = sum(1 for row in latest if row.intelligence_status == "INCOMPLETE")
    stale = sum(1 for row in latest if row.stale_risk_flag)
    export_ready = sum(1 for row in latest if row.export_readiness_score >= _money(100))
    avg = None
    if latest:
        avg = _money(sum((_decimal(row.completeness_score) for row in latest), ZERO) / Decimal(str(len(latest))))
    recent_weak = [row for row in latest if row.intelligence_status in {"WEAK", "INCOMPLETE"}]
    recent_weak.sort(key=lambda row: (row.snapshot_date, row.created_at, row.id or 0), reverse=True)
    return ListingIntelligenceDashboardSummary(
        strong_listing_count=strong,
        incomplete_listing_count=incomplete,
        average_completeness_score=avg,
        export_ready_count=export_ready,
        stale_risk_count=stale,
        recent_weak_or_incomplete=[_snapshot_read(row) for row in recent_weak[:6]],
    )


def list_listing_intelligence_owner(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    stale_risk_flag: bool | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingIntelligenceSnapshot], int]:
    q = _listing_intelligence_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        stale_risk_flag=stale_risk_flag,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_intelligence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    stale_risk_flag: bool | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingIntelligenceSnapshot], int]:
    q = _listing_intelligence_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        stale_risk_flag=stale_risk_flag,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def get_listing_intelligence_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> ListingIntelligenceSnapshot:
    row = session.get(ListingIntelligenceSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing intelligence snapshot not found")
    return row


def get_listing_intelligence_ops(session: Session, *, snapshot_id: int) -> ListingIntelligenceSnapshot:
    row = session.get(ListingIntelligenceSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing intelligence snapshot not found")
    return row


def list_listing_intelligence_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingIntelligenceEvidence], int]:
    q = _evidence_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_intelligence_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
    intelligence_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingIntelligenceEvidence], int]:
    q = _evidence_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_completeness_checks_owner(
    session: Session,
    *,
    owner_user_id: int,
    listing_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    check_status: str | None = None,
    severity: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingCompletenessCheck], int]:
    q = _check_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        check_status=check_status,
        severity=severity,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_completeness_checks_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    listing_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    check_status: str | None = None,
    severity: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingCompletenessCheck], int]:
    q = _check_query(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        check_status=check_status,
        severity=severity,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_channel_performance_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingChannelPerformanceSnapshot], int]:
    q = _channel_perf_query(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def list_listing_channel_performance_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingChannelPerformanceSnapshot], int]:
    q = _channel_perf_query(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )
    total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = session.exec(q.offset(offset).limit(limit)).all()
    return list(rows), total


def get_listing_completeness_check_owner(
    session: Session, *, owner_user_id: int, check_id: int
) -> ListingCompletenessCheck:
    row = session.get(ListingCompletenessCheck, check_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing completeness check not found")
    return row


def get_listing_channel_performance_owner(
    session: Session, *, owner_user_id: int, snapshot_id: int
) -> ListingChannelPerformanceSnapshot:
    row = session.get(ListingChannelPerformanceSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing channel performance snapshot not found")
    return row


def get_listing_channel_performance_ops(
    session: Session, *, snapshot_id: int
) -> ListingChannelPerformanceSnapshot:
    row = session.get(ListingChannelPerformanceSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing channel performance snapshot not found")
    return row

