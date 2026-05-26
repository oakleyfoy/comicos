"""P36-04 deterministic inventory liquidity analytics."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    InventoryCopy,
    InventoryLiquidityEvidence,
    InventoryLiquiditySnapshot,
    Listing,
    ListingLifecycleEvent,
    ListingStalenessEvent,
    ListingVelocitySnapshot,
    SaleRecord,
)
from app.models.listing_registry import utc_now as listing_utc_now
from app.schemas.liquidity_engine import (
    InventoryLiquidityEvidenceRead,
    InventoryLiquidityListResponse,
    InventoryLiquiditySnapshotRead,
    LiquidityConfidence,
    LiquidityDashboardSummary,
    LiquidityEvidenceType,
    LiquidityStatus,
    ListingStalenessEventListResponse,
    ListingStalenessEventRead,
    ListingStalenessEventType,
    ListingVelocityListResponse,
    ListingVelocitySnapshotRead,
)

MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
DEFAULT_EVALUATION_WINDOW_DAYS = 365
STALE_THRESHOLDS: dict[int, ListingStalenessEventType] = {
    30: "STALE_WARNING",
    60: "STALE_CONFIRMED",
    120: "LONG_RUNNING",
}
CHANNEL_ALIASES: dict[str, str] = {
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
ALLOWED_CHANNELS = frozenset(CHANNEL_ALIASES.values())


@dataclass(frozen=True)
class _ListingCycle:
    listing: Listing
    channel: str | None
    days_active: Decimal | None
    relist_count: int
    price_change_count: int
    terminal_at: datetime | None
    sold: bool
    failed: bool
    stale: bool


def utc_now() -> datetime:
    return listing_utc_now()


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _quantize_pct(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _median_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return _quantize_money(ordered[0])
    if len(ordered) % 2 == 1:
        return _quantize_money(ordered[len(ordered) // 2])
    mid = len(ordered) // 2
    return _quantize_money((ordered[mid - 1] + ordered[mid]) / Decimal("2"))


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


def _normalize_channel(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized not in ALLOWED_CHANNELS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid liquidity channel")
    return normalized


def _channel_from_source(source_type: str | None) -> str | None:
    if source_type is None:
        return None
    return CHANNEL_ALIASES.get(str(source_type).strip().lower(), str(source_type).strip().lower())


def _quantize_days_from_delta(delta: timedelta) -> Decimal:
    days = Decimal(str(delta.total_seconds())) / Decimal("86400")
    return days.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _listing_terminal_at(session: Session, listing: Listing) -> datetime | None:
    if listing.status == "SOLD":
        return listing.sold_at or listing.updated_at
    if listing.status == "ARCHIVED":
        return listing.archived_at or listing.updated_at
    if listing.status == "CANCELLED":
        event = session.exec(
            select(ListingLifecycleEvent)
            .where(ListingLifecycleEvent.listing_id == listing.id, ListingLifecycleEvent.new_status == "CANCELLED")
            .order_by(col(ListingLifecycleEvent.created_at).desc())
            .order_by(col(ListingLifecycleEvent.id).desc())
        ).first()
        return event.created_at if event is not None else listing.updated_at
    return None


def _listing_days_active(session: Session, listing: Listing, snapshot_at: datetime) -> Decimal | None:
    if listing.activated_at is None:
        return None
    terminal_at = _naive_utc(_listing_terminal_at(session, listing) or snapshot_at)
    activated_at = _naive_utc(listing.activated_at)
    if terminal_at < activated_at:
        return ZERO
    return _quantize_days_from_delta(terminal_at - activated_at)


def _listing_price_change_count(session: Session, listing_id: int) -> int:
    row = session.exec(
        select(func.count(ListingLifecycleEvent.id)).where(
            ListingLifecycleEvent.listing_id == listing_id,
            ListingLifecycleEvent.event_type == "PRICE_CHANGED",
        )
    ).one()
    return int(row or 0)


def _relist_count_for_listing(
    listings_by_inventory: dict[int, list[Listing]],
    *,
    inventory_copy_id: int,
    listing_id: int,
) -> int:
    rows = sorted(
        listings_by_inventory.get(inventory_copy_id, []),
        key=lambda row: (row.created_at, row.id or 0),
    )
    relist_index = 0
    for row in rows:
        if int(row.id or 0) == listing_id:
            return relist_index
        relist_index += 1
    return 0


def _derive_canonical_issue_id(listings: list[Listing]) -> int | None:
    values = [int(row.canonical_comic_issue_id) for row in listings if row.canonical_comic_issue_id is not None]
    if not values:
        return None
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _listing_cycle_rows(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_at: datetime,
    inventory_items: list[InventoryCopy],
) -> list[_ListingCycle]:
    listings = session.exec(
        select(Listing)
        .where(Listing.owner_user_id == owner_user_id)
        .order_by(col(Listing.created_at).asc())
        .order_by(col(Listing.id).asc())
    ).all()
    by_inventory: dict[int, list[Listing]] = defaultdict(list)
    for listing in listings:
        by_inventory[int(listing.inventory_copy_id)].append(listing)

    cycles: list[_ListingCycle] = []
    for listing in listings:
        days_active = _listing_days_active(session, listing, snapshot_at)
        terminal_at = _listing_terminal_at(session, listing)
        relist_count = _relist_count_for_listing(
            by_inventory,
            inventory_copy_id=int(listing.inventory_copy_id),
            listing_id=int(listing.id or 0),
        )
        price_change_count = _listing_price_change_count(session, int(listing.id or 0))
        sold = listing.status == "SOLD"
        failed = listing.status in {"CANCELLED", "ARCHIVED"}
        stale = bool(days_active is not None and days_active >= Decimal("30.00"))
        channel = _channel_from_source(listing.source_type)
        cycles.append(
            _ListingCycle(
                listing=listing,
                channel=channel,
                days_active=days_active,
                relist_count=relist_count,
                price_change_count=price_change_count,
                terminal_at=terminal_at,
                sold=sold,
                failed=failed,
                stale=stale,
            )
        )
    return cycles


def _snapshot_signature_payload(
    *,
    owner_user_id: int,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    channel: str | None,
    evaluation_window_days: int,
    snapshot_date: date,
) -> dict[str, Any]:
    return {
        "owner_user_id": owner_user_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "channel": channel,
        "evaluation_window_days": evaluation_window_days,
        "snapshot_date": snapshot_date.isoformat(),
    }


def _snapshot_checksum(payload: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> str:
    body = {"payload": payload, "evidence": evidence_rows}
    raw = json.dumps(_json_safe(body), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _liquidity_confidence(*, evidence_count: int, successful_sale_count: int, active_listing_count: int) -> LiquidityConfidence:
    if evidence_count >= 12 and successful_sale_count >= 6:
        return "HIGH"
    if evidence_count >= 5 or successful_sale_count >= 2 or active_listing_count >= 2:
        return "MEDIUM"
    return "LOW"


def _liquidity_status(
    *,
    successful_sale_count: int,
    failed_listing_count: int,
    active_listing_count: int,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
    relist_rate_pct: Decimal,
) -> LiquidityStatus:
    completed_cycles = successful_sale_count + failed_listing_count
    if completed_cycles < 3:
        return "INSUFFICIENT_DATA"
    if successful_sale_count == 0 and stale_listing_rate_pct >= Decimal("60.00"):
        return "ILLIQUID"
    if sell_through_rate_pct < Decimal("20.00") and stale_listing_rate_pct >= Decimal("60.00"):
        return "ILLIQUID"
    if sell_through_rate_pct >= Decimal("70.00") and stale_listing_rate_pct <= Decimal("15.00") and relist_rate_pct <= Decimal("15.00"):
        return "HIGH"
    if sell_through_rate_pct < Decimal("40.00") or stale_listing_rate_pct >= Decimal("35.00"):
        return "LOW"
    return "MODERATE"


def _snapshot_rows_for_group(
    *,
    owner_user_id: int,
    inventory_item_id: int,
    canonical_comic_issue_id: int | None,
    channel: str | None,
    evaluation_window_days: int,
    snapshot_date: date,
    cycles: list[_ListingCycle],
    sales: list[SaleRecord],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relevant_cycles = [cycle for cycle in cycles if channel is None or cycle.channel == channel]
    relevant_sales = [sale for sale in sales if channel is None or _channel_from_source(sale.channel) == channel]
    completed_cycles = [cycle for cycle in relevant_cycles if cycle.sold or cycle.failed]
    active_cycles = [cycle for cycle in relevant_cycles if cycle.listing.status in {"READY", "ACTIVE"}]
    stale_cycles = [cycle for cycle in relevant_cycles if cycle.stale]
    sold_cycles = [cycle for cycle in relevant_cycles if cycle.sold]
    failed_cycles = [cycle for cycle in relevant_cycles if cycle.failed]

    days_on_market_values = [cycle.days_active for cycle in completed_cycles if cycle.days_active is not None]
    days_to_sale_values = [cycle.days_active for cycle in sold_cycles if cycle.days_active is not None]
    relist_count = sum(1 for cycle in relevant_cycles if cycle.relist_count > 0)
    total_cycles = len(relevant_cycles)
    completed_count = len(completed_cycles)
    sell_through = (
        _quantize_pct((Decimal(len(sold_cycles)) / Decimal(completed_count)) * Decimal("100"))
        if completed_count > 0
        else ZERO
    )
    stale_rate = (
        _quantize_pct((Decimal(len(stale_cycles)) / Decimal(total_cycles)) * Decimal("100"))
        if total_cycles > 0
        else ZERO
    )
    relist_rate = (
        _quantize_pct((Decimal(relist_count) / Decimal(total_cycles)) * Decimal("100"))
        if total_cycles > 0
        else ZERO
    )
    liquidity_status = _liquidity_status(
        successful_sale_count=len(sold_cycles),
        failed_listing_count=len(failed_cycles),
        active_listing_count=len(active_cycles),
        sell_through_rate_pct=sell_through,
        stale_listing_rate_pct=stale_rate,
        relist_rate_pct=relist_rate,
    )
    evidence_rows: list[dict[str, Any]] = []
    for cycle in relevant_cycles:
        if cycle.sold:
            evidence_rows.append(
                {
                    "evidence_type": "SALE",
                    "source_listing_id": int(cycle.listing.id or 0),
                    "source_sale_id": next((int(sale.id or 0) for sale in relevant_sales if sale.listing_id == cycle.listing.id), None),
                    "days_on_market": cycle.days_active,
                }
            )
        elif cycle.failed:
            evidence_rows.append(
                {
                    "evidence_type": "FAILED_LISTING",
                    "source_listing_id": int(cycle.listing.id or 0),
                    "source_sale_id": None,
                    "days_on_market": cycle.days_active,
                }
            )
        elif cycle.listing.status in {"READY", "ACTIVE"}:
            evidence_rows.append(
                {
                    "evidence_type": "ACTIVE_LISTING",
                    "source_listing_id": int(cycle.listing.id or 0),
                    "source_sale_id": None,
                    "days_on_market": cycle.days_active,
                }
            )
        if cycle.relist_count > 0:
            evidence_rows.append(
                {
                    "evidence_type": "RELIST",
                    "source_listing_id": int(cycle.listing.id or 0),
                    "source_sale_id": None,
                    "days_on_market": cycle.days_active,
                    "relist_count": cycle.relist_count,
                }
            )
        if cycle.stale:
            evidence_rows.append(
                {
                    "evidence_type": "STALE",
                    "source_listing_id": int(cycle.listing.id or 0),
                    "source_sale_id": None,
                    "days_on_market": cycle.days_active,
                }
            )

    snapshot_payload = {
        "owner_user_id": owner_user_id,
        "inventory_item_id": inventory_item_id,
        "canonical_comic_issue_id": canonical_comic_issue_id,
        "channel": channel,
        "liquidity_status": liquidity_status,
        "days_on_market_median": _median_decimal([_quantize_money(value) for value in days_on_market_values]),
        "days_to_sale_median": _median_decimal([_quantize_money(value) for value in days_to_sale_values]),
        "sell_through_rate_pct": sell_through,
        "stale_listing_rate_pct": stale_rate,
        "relist_rate_pct": relist_rate,
        "successful_sale_count": len(sold_cycles),
        "failed_listing_count": len(failed_cycles),
        "active_listing_count": len(active_cycles),
        "liquidity_confidence": _liquidity_confidence(
            evidence_count=len(evidence_rows),
            successful_sale_count=len(sold_cycles),
            active_listing_count=len(active_cycles),
        ),
        "evaluation_window_days": evaluation_window_days,
        "snapshot_date": snapshot_date,
    }
    snapshot_payload["checksum"] = _snapshot_checksum(
        _snapshot_signature_payload(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_item_id,
            canonical_comic_issue_id=canonical_comic_issue_id,
            channel=channel,
            evaluation_window_days=evaluation_window_days,
            snapshot_date=snapshot_date,
        ),
        evidence_rows,
    )
    return snapshot_payload, evidence_rows, [dict(row) for row in evidence_rows], [
        {
            "source_listing_id": int(cycle.listing.id or 0),
            "channel": cycle.channel,
            "days_active": cycle.days_active,
            "relist_count": cycle.relist_count,
            "price_change_count": cycle.price_change_count,
            "final_status": cycle.listing.status,
            "sold_at": cycle.listing.sold_at,
            "first_activated_at": cycle.listing.activated_at,
        }
        for cycle in relevant_cycles
    ]


def _ensure_staleness_events(session: Session, *, owner_user_id: int, cycles: list[_ListingCycle]) -> None:
    for cycle in cycles:
        if cycle.days_active is None:
            continue
        for threshold, event_type in STALE_THRESHOLDS.items():
            if cycle.days_active < Decimal(str(threshold)):
                continue
            dup = session.exec(
                select(ListingStalenessEvent).where(
                    ListingStalenessEvent.listing_id == cycle.listing.id,
                    ListingStalenessEvent.event_type == event_type,
                    ListingStalenessEvent.threshold_days == threshold,
                )
            ).first()
            if dup is not None:
                continue
            session.add(
                ListingStalenessEvent(
                    listing_id=int(cycle.listing.id or 0),
                    owner_user_id=owner_user_id,
                    event_type=event_type,
                    threshold_days=threshold,
                    days_active=_quantize_money(cycle.days_active),
                    created_at=utc_now(),
                )
            )


def _snapshot_signature_exists(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int | None,
    canonical_comic_issue_id: int | None,
    channel: str | None,
    evaluation_window_days: int,
    snapshot_date: date,
) -> InventoryLiquiditySnapshot | None:
    return session.exec(
        select(InventoryLiquiditySnapshot).where(
            InventoryLiquiditySnapshot.owner_user_id == owner_user_id,
            InventoryLiquiditySnapshot.inventory_item_id == inventory_item_id,
            InventoryLiquiditySnapshot.canonical_comic_issue_id == canonical_comic_issue_id,
            InventoryLiquiditySnapshot.channel == channel,
            InventoryLiquiditySnapshot.evaluation_window_days == evaluation_window_days,
            InventoryLiquiditySnapshot.snapshot_date == snapshot_date,
        )
    ).first()


def _snapshot_read(row: InventoryLiquiditySnapshot) -> InventoryLiquiditySnapshotRead:
    return InventoryLiquiditySnapshotRead.model_validate(row, from_attributes=True)


def _evidence_read(row: InventoryLiquidityEvidence) -> InventoryLiquidityEvidenceRead:
    return InventoryLiquidityEvidenceRead.model_validate(row, from_attributes=True)


def _velocity_read(row: ListingVelocitySnapshot) -> ListingVelocitySnapshotRead:
    return ListingVelocitySnapshotRead.model_validate(row, from_attributes=True)


def _staleness_read(row: ListingStalenessEvent) -> ListingStalenessEventRead:
    return ListingStalenessEventRead.model_validate(row, from_attributes=True)


def materialize_liquidity_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
    evaluation_window_days: int = DEFAULT_EVALUATION_WINDOW_DAYS,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    channel: str | None = None,
) -> list[InventoryLiquiditySnapshot]:
    channel = _normalize_channel(channel)
    snapshot_date = snapshot_date or utc_now().date()
    snapshot_at = datetime.combine(snapshot_date, datetime.min.time())

    inventory_query = select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)
    if inventory_item_id is not None:
        inventory_query = inventory_query.where(InventoryCopy.id == inventory_item_id)
    inventory_items = session.exec(inventory_query.order_by(col(InventoryCopy.id).asc())).all()

    listings = session.exec(
        select(Listing)
        .where(Listing.owner_user_id == owner_user_id)
        .order_by(col(Listing.created_at).asc())
        .order_by(col(Listing.id).asc())
    ).all()
    listings_by_inventory: dict[int, list[Listing]] = defaultdict(list)
    for listing in listings:
        listings_by_inventory[int(listing.inventory_copy_id)].append(listing)

    sales = session.exec(
        select(SaleRecord)
        .where(SaleRecord.owner_user_id == owner_user_id)
        .order_by(col(SaleRecord.sale_date).asc())
        .order_by(col(SaleRecord.id).asc())
    ).all()
    sales_by_listing: dict[int, list[SaleRecord]] = defaultdict(list)
    for sale in sales:
        if sale.listing_id is not None:
            sales_by_listing[int(sale.listing_id)].append(sale)

    cycles = _listing_cycle_rows(session, owner_user_id=owner_user_id, snapshot_at=snapshot_at, inventory_items=inventory_items)
    _ensure_staleness_events(session, owner_user_id=owner_user_id, cycles=cycles)

    created: list[InventoryLiquiditySnapshot] = []
    for item in inventory_items:
        item_listings = listings_by_inventory.get(int(item.id or 0), [])
        if not item_listings:
            continue
        derived_issue_id = _derive_canonical_issue_id(item_listings)
        if canonical_comic_issue_id is not None and derived_issue_id != canonical_comic_issue_id:
            continue
        if channel is not None:
            channels = [channel]
        else:
            channel_values = sorted(
                {
                    cycle.channel
                    for cycle in cycles
                    if cycle.listing.inventory_copy_id == item.id and cycle.channel is not None
                }
            )
            channels = [None, *channel_values]
        for scope_channel in channels:
            snapshot_payload, evidence_rows, evidence_json_rows, velocity_rows = _snapshot_rows_for_group(
                owner_user_id=owner_user_id,
                inventory_item_id=int(item.id or 0),
                canonical_comic_issue_id=derived_issue_id,
                channel=scope_channel,
                evaluation_window_days=evaluation_window_days,
                snapshot_date=snapshot_date,
                cycles=[cycle for cycle in cycles if cycle.listing.inventory_copy_id == item.id],
                sales=[sale for sale in sales if sale.listing_id in {int(lst.id or 0) for lst in item_listings}],
            )

            existing = _snapshot_signature_exists(
                session,
                owner_user_id=owner_user_id,
                inventory_item_id=int(item.id or 0),
                canonical_comic_issue_id=derived_issue_id,
                channel=scope_channel,
                evaluation_window_days=evaluation_window_days,
                snapshot_date=snapshot_date,
            )
            if existing is not None:
                created.append(existing)
                continue

            snapshot = InventoryLiquiditySnapshot(
                owner_user_id=owner_user_id,
                inventory_item_id=int(item.id or 0),
                canonical_comic_issue_id=derived_issue_id,
                channel=scope_channel,
                liquidity_status=snapshot_payload["liquidity_status"],
                days_on_market_median=snapshot_payload["days_on_market_median"],
                days_to_sale_median=snapshot_payload["days_to_sale_median"],
                sell_through_rate_pct=snapshot_payload["sell_through_rate_pct"],
                stale_listing_rate_pct=snapshot_payload["stale_listing_rate_pct"],
                relist_rate_pct=snapshot_payload["relist_rate_pct"],
                successful_sale_count=snapshot_payload["successful_sale_count"],
                failed_listing_count=snapshot_payload["failed_listing_count"],
                active_listing_count=snapshot_payload["active_listing_count"],
                liquidity_confidence=snapshot_payload["liquidity_confidence"],
                evaluation_window_days=evaluation_window_days,
                snapshot_date=snapshot_date,
                checksum=snapshot_payload["checksum"],
                evidence_count=len(evidence_rows),
                created_at=utc_now(),
            )
            session.add(snapshot)
            session.flush()

            for row in evidence_json_rows:
                session.add(
                    InventoryLiquidityEvidence(
                        liquidity_snapshot_id=int(snapshot.id or 0),
                        evidence_type=row["evidence_type"],
                        source_listing_id=row.get("source_listing_id"),
                        source_sale_id=row.get("source_sale_id"),
                        source_export_run_id=None,
                        days_on_market=row.get("days_on_market"),
                        evidence_json=_json_safe(row),
                        created_at=utc_now(),
                    )
                )

            for velocity in velocity_rows:
                listing_row = next((lst for lst in item_listings if int(lst.id or 0) == int(velocity["source_listing_id"])), None)
                if listing_row is None:
                    continue
                existing_velocity = session.exec(
                    select(ListingVelocitySnapshot).where(
                        ListingVelocitySnapshot.listing_id == listing_row.id,
                        ListingVelocitySnapshot.snapshot_date == snapshot_date,
                    )
                ).first()
                if existing_velocity is not None:
                    continue
                session.add(
                    ListingVelocitySnapshot(
                        listing_id=int(listing_row.id or 0),
                        owner_user_id=owner_user_id,
                        first_activated_at=velocity["first_activated_at"],
                        sold_at=velocity["sold_at"],
                        days_active=velocity["days_active"],
                        relist_count=velocity["relist_count"],
                        price_change_count=velocity["price_change_count"],
                        final_status=velocity["final_status"],
                        snapshot_date=snapshot_date,
                        created_at=utc_now(),
                    )
                )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = _snapshot_signature_exists(
                    session,
                    owner_user_id=owner_user_id,
                    inventory_item_id=int(item.id or 0),
                    canonical_comic_issue_id=derived_issue_id,
                    channel=scope_channel,
                    evaluation_window_days=evaluation_window_days,
                    snapshot_date=snapshot_date,
                )
                if existing is not None:
                    created.append(existing)
                    continue
                raise
            created.append(snapshot)
    return created


def _filter_snapshot_query(
    *,
    owner_user_id: int | None,
    channel: str | None,
    liquidity_status: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    canonical_comic_issue_id: int | None,
    inventory_item_id: int | None,
) -> Any:
    q = select(InventoryLiquiditySnapshot)
    if owner_user_id is not None:
        q = q.where(InventoryLiquiditySnapshot.owner_user_id == owner_user_id)
    if channel is not None:
        q = q.where(InventoryLiquiditySnapshot.channel == channel)
    if liquidity_status is not None:
        q = q.where(InventoryLiquiditySnapshot.liquidity_status == liquidity_status)
    if snapshot_date_from is not None:
        q = q.where(InventoryLiquiditySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(InventoryLiquiditySnapshot.snapshot_date <= snapshot_date_to)
    if canonical_comic_issue_id is not None:
        q = q.where(InventoryLiquiditySnapshot.canonical_comic_issue_id == canonical_comic_issue_id)
    if inventory_item_id is not None:
        q = q.where(InventoryLiquiditySnapshot.inventory_item_id == inventory_item_id)
    return q


def _count_snapshot_query(
    *,
    owner_user_id: int | None,
    channel: str | None,
    liquidity_status: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    canonical_comic_issue_id: int | None,
    inventory_item_id: int | None,
) -> Any:
    return _filter_snapshot_query(
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
    )


def list_liquidity_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str | None = None,
    liquidity_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    canonical_comic_issue_id: int | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
    snapshot_date: date | None = None,
    evaluation_window_days: int = DEFAULT_EVALUATION_WINDOW_DAYS,
) -> tuple[list[InventoryLiquiditySnapshot], int]:
    materialize_liquidity_snapshots(
        session,
        owner_user_id=owner_user_id,
        snapshot_date=snapshot_date,
        evaluation_window_days=evaluation_window_days,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
    )
    channel = _normalize_channel(channel)
    q = _filter_snapshot_query(
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc())
        .order_by(col(InventoryLiquiditySnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_liquidity_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    liquidity_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    canonical_comic_issue_id: int | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[InventoryLiquiditySnapshot], int]:
    channel = _normalize_channel(channel)
    q = _filter_snapshot_query(
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc())
        .order_by(col(InventoryLiquiditySnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def get_liquidity_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> InventoryLiquiditySnapshot:
    row = session.get(InventoryLiquiditySnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="liquidity snapshot not found")
    return row


def get_liquidity_ops(session: Session, *, snapshot_id: int) -> InventoryLiquiditySnapshot:
    row = session.get(InventoryLiquiditySnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="liquidity snapshot not found")
    return row


def _snapshot_evidence_query(snapshot_id: int):
    return select(InventoryLiquidityEvidence).where(InventoryLiquidityEvidence.liquidity_snapshot_id == snapshot_id)


def list_liquidity_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str | None = None,
    liquidity_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    canonical_comic_issue_id: int | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
    snapshot_date: date | None = None,
) -> tuple[list[InventoryLiquidityEvidence], int]:
    snapshots, _ = list_liquidity_owner(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=10_000,
        offset=0,
        snapshot_date=snapshot_date,
    )
    snapshot_ids = [int(row.id or 0) for row in snapshots]
    q = select(InventoryLiquidityEvidence).where(InventoryLiquidityEvidence.liquidity_snapshot_id.in_(snapshot_ids))
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(InventoryLiquidityEvidence.created_at).asc())
        .order_by(col(InventoryLiquidityEvidence.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_liquidity_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    liquidity_status: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    canonical_comic_issue_id: int | None = None,
    inventory_item_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[InventoryLiquidityEvidence], int]:
    snapshots, _ = list_liquidity_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=10_000,
        offset=0,
    )
    snapshot_ids = [int(row.id or 0) for row in snapshots]
    q = select(InventoryLiquidityEvidence).where(InventoryLiquidityEvidence.liquidity_snapshot_id.in_(snapshot_ids))
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(InventoryLiquidityEvidence.created_at).asc())
        .order_by(col(InventoryLiquidityEvidence.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_velocity_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingVelocitySnapshot], int]:
    channel = _normalize_channel(channel)
    q = select(ListingVelocitySnapshot).where(ListingVelocitySnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        q = q.where(ListingVelocitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(ListingVelocitySnapshot.snapshot_date <= snapshot_date_to)
    if inventory_item_id is not None:
        q = q.join(Listing, ListingVelocitySnapshot.listing_id == Listing.id).where(Listing.inventory_copy_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        q = q.join(Listing, ListingVelocitySnapshot.listing_id == Listing.id).where(
            Listing.canonical_comic_issue_id == canonical_comic_issue_id
        )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(ListingVelocitySnapshot.snapshot_date).desc())
        .order_by(col(ListingVelocitySnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    if channel is not None:
        rows = [row for row in rows if _channel_from_source(session.get(Listing, row.listing_id).source_type if session.get(Listing, row.listing_id) else None) == channel]
        total = len(rows)
    return list(rows), total


def list_velocity_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingVelocitySnapshot], int]:
    channel = _normalize_channel(channel)
    q = select(ListingVelocitySnapshot)
    if owner_user_id is not None:
        q = q.where(ListingVelocitySnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        q = q.where(ListingVelocitySnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        q = q.where(ListingVelocitySnapshot.snapshot_date <= snapshot_date_to)
    if inventory_item_id is not None:
        q = q.join(Listing, ListingVelocitySnapshot.listing_id == Listing.id).where(Listing.inventory_copy_id == inventory_item_id)
    if canonical_comic_issue_id is not None:
        q = q.join(Listing, ListingVelocitySnapshot.listing_id == Listing.id).where(
            Listing.canonical_comic_issue_id == canonical_comic_issue_id
        )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(ListingVelocitySnapshot.snapshot_date).desc())
        .order_by(col(ListingVelocitySnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    if channel is not None:
        rows = [row for row in rows if _channel_from_source(session.get(Listing, row.listing_id).source_type if session.get(Listing, row.listing_id) else None) == channel]
        total = len(rows)
    return list(rows), total


def list_staleness_owner(
    session: Session,
    *,
    owner_user_id: int,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingStalenessEvent], int]:
    channel = _normalize_channel(channel)
    q = select(ListingStalenessEvent).where(ListingStalenessEvent.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        q = q.where(ListingStalenessEvent.created_at >= datetime.combine(snapshot_date_from, datetime.min.time()))
    if snapshot_date_to is not None:
        q = q.where(ListingStalenessEvent.created_at < datetime.combine(snapshot_date_to, datetime.max.time()))
    if inventory_item_id is not None or canonical_comic_issue_id is not None or channel is not None:
        q = q.join(Listing, ListingStalenessEvent.listing_id == Listing.id)
        if inventory_item_id is not None:
            q = q.where(Listing.inventory_copy_id == inventory_item_id)
        if canonical_comic_issue_id is not None:
            q = q.where(Listing.canonical_comic_issue_id == canonical_comic_issue_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(ListingStalenessEvent.created_at).desc())
        .order_by(col(ListingStalenessEvent.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    if channel is not None:
        rows = [row for row in rows if _channel_from_source(session.get(Listing, row.listing_id).source_type if session.get(Listing, row.listing_id) else None) == channel]
        total = len(rows)
    return list(rows), total


def list_staleness_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    channel: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    inventory_item_id: int | None = None,
    canonical_comic_issue_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ListingStalenessEvent], int]:
    channel = _normalize_channel(channel)
    q = select(ListingStalenessEvent)
    if owner_user_id is not None:
        q = q.where(ListingStalenessEvent.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        q = q.where(ListingStalenessEvent.created_at >= datetime.combine(snapshot_date_from, datetime.min.time()))
    if snapshot_date_to is not None:
        q = q.where(ListingStalenessEvent.created_at < datetime.combine(snapshot_date_to, datetime.max.time()))
    if inventory_item_id is not None or canonical_comic_issue_id is not None or channel is not None:
        q = q.join(Listing, ListingStalenessEvent.listing_id == Listing.id)
        if inventory_item_id is not None:
            q = q.where(Listing.inventory_copy_id == inventory_item_id)
        if canonical_comic_issue_id is not None:
            q = q.where(Listing.canonical_comic_issue_id == canonical_comic_issue_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(ListingStalenessEvent.created_at).desc())
        .order_by(col(ListingStalenessEvent.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    if channel is not None:
        rows = [row for row in rows if _channel_from_source(session.get(Listing, row.listing_id).source_type if session.get(Listing, row.listing_id) else None) == channel]
        total = len(rows)
    return list(rows), total


def _summary_from_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
) -> LiquidityDashboardSummary:
    q = select(InventoryLiquiditySnapshot).where(InventoryLiquiditySnapshot.owner_user_id == owner_user_id)
    if snapshot_date is not None:
        q = q.where(InventoryLiquiditySnapshot.snapshot_date == snapshot_date)
    snapshots = session.exec(q.order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc())).all()
    high_count = sum(1 for row in snapshots if row.liquidity_status == "HIGH")
    stale_count = sum(1 for row in snapshots if row.stale_listing_rate_pct > ZERO)
    recent_snapshots = list(snapshots[:10])
    stale_events = session.exec(
        select(ListingStalenessEvent)
        .where(ListingStalenessEvent.owner_user_id == owner_user_id)
        .order_by(col(ListingStalenessEvent.created_at).desc())
        .order_by(col(ListingStalenessEvent.id).desc())
        .limit(10)
    ).all()
    completed_rows = session.exec(
        select(ListingVelocitySnapshot.days_active).where(
            ListingVelocitySnapshot.owner_user_id == owner_user_id,
            ListingVelocitySnapshot.days_active.is_not(None),
            ListingVelocitySnapshot.final_status.in_(["SOLD", "CANCELLED", "ARCHIVED"]),
        )
    ).all()
    median_days = _median_decimal([_quantize_money(row) for row in completed_rows if row is not None])
    sold = session.exec(
        select(func.count(ListingVelocitySnapshot.id)).where(
            ListingVelocitySnapshot.owner_user_id == owner_user_id,
            ListingVelocitySnapshot.final_status == "SOLD",
        )
    ).one()
    total = session.exec(
        select(func.count(ListingVelocitySnapshot.id)).where(
            ListingVelocitySnapshot.owner_user_id == owner_user_id,
        )
    ).one()
    sell_through = _quantize_pct((Decimal(int(sold or 0)) / Decimal(int(total or 1))) * Decimal("100")) if int(total or 0) > 0 else ZERO
    return LiquidityDashboardSummary(
        high_liquidity_count=high_count,
        stale_inventory_count=stale_count,
        recent_stale_events=[_staleness_read(row) for row in stale_events],
        median_days_to_sale=median_days,
        sell_through_pct=sell_through,
        recent_snapshots=[_snapshot_read(row) for row in recent_snapshots],
    )


def dashboard_summary_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date | None = None,
) -> LiquidityDashboardSummary:
    materialize_liquidity_snapshots(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    return _summary_from_snapshots(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)


def dashboard_summary_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    snapshot_date: date | None = None,
) -> LiquidityDashboardSummary:
    if owner_user_id is None:
        q = select(InventoryLiquiditySnapshot)
        if snapshot_date is not None:
            q = q.where(InventoryLiquiditySnapshot.snapshot_date == snapshot_date)
        snapshots = session.exec(q.order_by(col(InventoryLiquiditySnapshot.snapshot_date).desc())).all()
        high_count = sum(1 for row in snapshots if row.liquidity_status == "HIGH")
        stale_count = sum(1 for row in snapshots if row.stale_listing_rate_pct > ZERO)
        stale_events = session.exec(
            select(ListingStalenessEvent).order_by(col(ListingStalenessEvent.created_at).desc()).limit(10)
        ).all()
        median_days = _median_decimal(
            [
                _quantize_money(row.days_active)
                for row in session.exec(
                    select(ListingVelocitySnapshot.days_active).where(
                        ListingVelocitySnapshot.days_active.is_not(None),
                        ListingVelocitySnapshot.final_status.in_(["SOLD", "CANCELLED", "ARCHIVED"]),
                    )
                ).all()
                if row is not None
            ]
        )
        sold = session.exec(select(func.count(ListingVelocitySnapshot.id)).where(ListingVelocitySnapshot.final_status == "SOLD")).one()
        total = session.exec(select(func.count(ListingVelocitySnapshot.id))).one()
        sell_through = _quantize_pct((Decimal(int(sold or 0)) / Decimal(int(total or 1))) * Decimal("100")) if int(total or 0) > 0 else ZERO
        return LiquidityDashboardSummary(
            high_liquidity_count=high_count,
            stale_inventory_count=stale_count,
            recent_stale_events=[_staleness_read(row) for row in stale_events],
            median_days_to_sale=median_days,
            sell_through_pct=sell_through,
            recent_snapshots=[_snapshot_read(row) for row in snapshots[:10]],
        )
    return _summary_from_snapshots(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)


def build_snapshot_detail_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> InventoryLiquiditySnapshot:
    row = session.get(InventoryLiquiditySnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="liquidity snapshot not found")
    return row


def build_snapshot_detail_ops(session: Session, *, snapshot_id: int) -> InventoryLiquiditySnapshot:
    row = session.get(InventoryLiquiditySnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="liquidity snapshot not found")
    return row
