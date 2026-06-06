from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session
from sqlmodel import select

from app.models import EbayCompImportRun, EbayCompRecord, P68MarketPricingProvider
from app.models.market_pricing_engine import PROVIDER_EBAY_SOLD
from app.schemas.ebay_comp_import import EbayCompImportSummaryResponse
from app.services.ebay_sold_search_service import (
    EbaySoldSearchRequest,
    extract_ebay_sold_search_items,
    normalize_ebay_sold_search_payload,
)
from app.services.market_normalization import deterministic_normalize_title
from app.services.market_pricing_provider_registry import ensure_provider_registry


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return None


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _search_criteria_json(search_request: EbaySoldSearchRequest, criteria: dict[str, Any] | None) -> dict[str, Any]:
    if criteria is not None:
        return {k: v for k, v in criteria.items() if v is not None}
    return {"query": search_request.query, "params": dict(search_request.params)}


def import_ebay_comp_results(
    session: Session,
    *,
    owner_user_id: int,
    search_request: EbaySoldSearchRequest,
    search_payload: dict[str, Any],
    search_criteria: dict[str, Any] | None = None,
) -> EbayCompImportSummaryResponse:
    now = _utc_now()
    raw_items = extract_ebay_sold_search_items(search_payload)
    preview_items = normalize_ebay_sold_search_payload(search_payload, search_request)
    inserted = 0
    updated = 0
    duplicates = 0
    errors = 0

    provider_rows = ensure_provider_registry(session, owner_user_id=owner_user_id)
    provider_row = next((row for row in provider_rows if row.provider_type == PROVIDER_EBAY_SOLD), None)

    for raw_item, preview_item in zip(raw_items, preview_items):
        try:
            provider_listing_id = preview_item.provider_listing_id.strip()
            if not provider_listing_id:
                raise ValueError("Missing provider listing id")

            normalized_title = deterministic_normalize_title(preview_item.title)
            sold_at = _normalize_dt(preview_item.sold_at or preview_item.ended_at)
            ended_at = _normalize_dt(preview_item.ended_at)
            sold_price = _to_decimal(preview_item.sold_price)
            shipping_price = _to_decimal(preview_item.shipping_price)
            total_price = _to_decimal(preview_item.total_price)
            if total_price is None and sold_price is not None and shipping_price is not None:
                total_price = (sold_price + shipping_price).quantize(Decimal("0.01"))

            existing = session.exec(
                select(EbayCompRecord).where(
                    EbayCompRecord.owner_user_id == owner_user_id,
                    EbayCompRecord.provider == "EBAY",
                    EbayCompRecord.provider_listing_id == provider_listing_id,
                )
            ).first()

            payload_json = dict(raw_item)
            if existing is None:
                session.add(
                    EbayCompRecord(
                        owner_user_id=owner_user_id,
                        provider="EBAY",
                        provider_listing_id=provider_listing_id,
                        title=str(preview_item.title),
                        normalized_title=normalized_title,
                        sold_price=sold_price or Decimal("0.00"),
                        shipping_price=shipping_price,
                        total_price=total_price,
                        currency=str(preview_item.currency or "USD").upper(),
                        sold_at=sold_at,
                        ended_at=ended_at,
                        condition=_normalize_text(preview_item.condition),
                        listing_type=_normalize_text(preview_item.listing_type),
                        item_url=_normalize_text(preview_item.item_url),
                        image_url=_normalize_text(preview_item.image_url),
                        raw_payload_json=payload_json,
                        match_confidence=float(preview_item.raw_match_confidence),
                        imported_at=now,
                        updated_at=now,
                    )
                )
                inserted += 1
                continue

            changed = (
                existing.title != str(preview_item.title)
                or existing.normalized_title != normalized_title
                or existing.sold_price != (sold_price or Decimal("0.00"))
                or existing.shipping_price != shipping_price
                or existing.total_price != total_price
                or existing.currency != str(preview_item.currency or "USD").upper()
                or _normalize_dt(existing.sold_at) != sold_at
                or _normalize_dt(existing.ended_at) != ended_at
                or existing.condition != _normalize_text(preview_item.condition)
                or existing.listing_type != _normalize_text(preview_item.listing_type)
                or existing.item_url != _normalize_text(preview_item.item_url)
                or existing.image_url != _normalize_text(preview_item.image_url)
                or existing.raw_payload_json != payload_json
                or float(existing.match_confidence) != float(preview_item.raw_match_confidence)
            )

            if changed:
                existing.title = str(preview_item.title)
                existing.normalized_title = normalized_title
                existing.sold_price = sold_price or Decimal("0.00")
                existing.shipping_price = shipping_price
                existing.total_price = total_price
                existing.currency = str(preview_item.currency or "USD").upper()
                existing.sold_at = sold_at
                existing.ended_at = ended_at
                existing.condition = _normalize_text(preview_item.condition)
                existing.listing_type = _normalize_text(preview_item.listing_type)
                existing.item_url = _normalize_text(preview_item.item_url)
                existing.image_url = _normalize_text(preview_item.image_url)
                existing.raw_payload_json = payload_json
                existing.match_confidence = float(preview_item.raw_match_confidence)
                existing.updated_at = now
                session.add(existing)
                updated += 1
            else:
                duplicates += 1
        except Exception:
            errors += 1

    run = EbayCompImportRun(
        owner_user_id=owner_user_id,
        provider="EBAY",
        import_status="COMPLETED" if errors == 0 else "COMPLETED_WITH_ERRORS",
        search_criteria_json=_search_criteria_json(search_request, search_criteria),
        fetched_count=len(raw_items),
        inserted_count=inserted,
        updated_count=updated,
        duplicate_count=duplicates,
        error_count=errors,
        imported_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    if provider_row is not None:
        provider_row.enabled = True
        provider_row.health_status = "AUTHENTICATED"
        provider_row.last_ingest_at = now
        provider_row.metadata_json = {
            **(provider_row.metadata_json or {}),
            "import_available": True,
            "last_import_at": now.isoformat(),
            "last_import_run_id": int(run.id or 0),
            "last_error": None,
            "last_import_summary": {
                "fetched": len(raw_items),
                "inserted": inserted,
                "updated": updated,
                "duplicates": duplicates,
                "error_count": errors,
            },
        }
        session.add(provider_row)

    return EbayCompImportSummaryResponse(
        import_run_id=int(run.id or 0),
        fetched=len(raw_items),
        inserted=inserted,
        updated=updated,
        duplicates=duplicates,
        error_count=errors,
        imported_at=now,
    )
