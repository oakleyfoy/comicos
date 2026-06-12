"""Catalog enrichment for retailer-sourced draft imports (non-blocking)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlmodel import Session, select

from app.models import DraftImport, InventoryCopy, OrderItem, RetailerOrderItemSnapshot
from app.models.release_intelligence import ReleaseIssue
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.services.import_cover_resolver import ImportCoverResolutionResultPayload, resolve_import_cover
from app.services.import_line_cover_resolution_service import upsert_line_cover_resolution_from_item
from app.services.import_release_lifecycle_service import enrich_import_item_lifecycle

logger = logging.getLogger(__name__)

EnrichmentStatus = Literal["matched", "partial_match", "needs_review"]

# Confirm must never block inventory creation on slow catalog enrichment. Once this
# wall-clock budget is exceeded, remaining lines are left as needs_review and the
# confirm flow proceeds to materialize inventory immediately.
DEFAULT_ENRICH_TIME_BUDGET_SECONDS = 5.0


@dataclass(frozen=True)
class RetailerEnrichmentSummary:
    total_items: int
    enriched_items: int
    skipped_items: int
    matched_items: int
    needs_review_items: int
    budget_exceeded: bool
    elapsed_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "complete",
            "total_items": self.total_items,
            "enriched_items": self.enriched_items,
            "skipped_items": self.skipped_items,
            "matched_items": self.matched_items,
            "needs_review_items": self.needs_review_items,
            "budget_exceeded": self.budget_exceeded,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


def _is_broken_local_retailer_image(url: str | None) -> bool:
    if not url:
        return False
    cleaned = url.strip()
    return cleaned.startswith("/") and not cleaned.startswith("//")


def _enrichment_status_from_item(item: dict[str, Any]) -> EnrichmentStatus:
    if item.get("catalog_match_matched") is True:
        return "matched"
    if item.get("catalog_match_possible") is True:
        return "partial_match"
    return "needs_review"


def _confidence_from_item(item: dict[str, Any]) -> Decimal | None:
    score = item.get("catalog_match_score")
    if score is None:
        return None
    try:
        return Decimal(str(int(score)))
    except (TypeError, ValueError):
        return None


def _lookup_foc_date(session: Session, item: dict[str, Any]) -> date | None:
    if item.get("catalog_match_source") != "ReleaseIssue":
        return None
    source_id = item.get("catalog_match_source_id")
    if source_id is None:
        return None
    row = session.get(ReleaseIssue, int(source_id))
    if row is None:
        return None
    return row.foc_date


def _apply_cover_resolution_to_dict(
    item: dict[str, Any],
    cover: ImportCoverResolutionResultPayload,
) -> None:
    if cover.cover_image_url:
        item["cover_image_url"] = cover.cover_image_url
    if cover.cover_thumbnail_url:
        item["cover_thumbnail_url"] = cover.cover_thumbnail_url
    if cover.cover_image_source:
        item["cover_image_source"] = cover.cover_image_source
    if cover.cover_image_source_id is not None:
        item["cover_image_source_id"] = cover.cover_image_source_id
    item["has_cover_image"] = cover.has_cover_image
    if cover.cover_source:
        item["cover_source"] = cover.cover_source
    if cover.cover_confidence is not None:
        item["cover_confidence"] = cover.cover_confidence
    if cover.cover_resolution_debug:
        item["cover_resolution_debug"] = cover.cover_resolution_debug


def _prefer_catalog_cover_over_broken_local(item: dict[str, Any]) -> None:
    retailer_url = (item.get("retailer_cover_url") or item.get("retailer_thumbnail_url") or "").strip()
    item["source_image_url"] = retailer_url or None
    catalog_url = (item.get("cover_image_url") or "").strip()
    if _is_broken_local_retailer_image(catalog_url):
        catalog_url = ""
    if catalog_url and (_is_broken_local_retailer_image(retailer_url) or item.get("catalog_match_matched") is True):
        item["cover_image_url"] = catalog_url
        item["cover_thumbnail_url"] = item.get("cover_thumbnail_url") or catalog_url
    elif _is_broken_local_retailer_image(item.get("cover_image_url")):
        item["cover_image_url"] = None
        item["cover_thumbnail_url"] = None


def enrich_retailer_draft_item_dict(
    session: Session,
    *,
    owner_user_id: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    """Best-effort catalog + cover enrichment; never raises."""
    retailer_url = (item.get("retailer_cover_url") or item.get("retailer_thumbnail_url") or "").strip()
    if retailer_url:
        item["source_image_url"] = retailer_url

    try:
        enrich_import_item_lifecycle(session, owner_user_id=owner_user_id, item=item)
    except Exception:
        logger.warning(
            "retailer_catalog_enrich lifecycle failed title=%r",
            item.get("title"),
            exc_info=True,
        )

    try:
        cover = resolve_import_cover(session, item, owner_user_id=owner_user_id)
        _apply_cover_resolution_to_dict(item, cover)
    except Exception:
        logger.warning(
            "retailer_catalog_enrich cover failed title=%r",
            item.get("title"),
            exc_info=True,
        )

    if _is_broken_local_retailer_image(item.get("cover_image_url")):
        saved_retailer = item.get("source_image_url") or item.get("retailer_cover_url")
        item["retailer_cover_url"] = None
        item["retailer_thumbnail_url"] = None
        try:
            catalog_cover = resolve_import_cover(session, item, owner_user_id=owner_user_id)
            _apply_cover_resolution_to_dict(item, catalog_cover)
        except Exception:
            logger.warning(
                "retailer_catalog_enrich catalog cover retry failed title=%r",
                item.get("title"),
                exc_info=True,
            )
        finally:
            if saved_retailer:
                item["retailer_cover_url"] = saved_retailer
                item["source_image_url"] = saved_retailer

    _prefer_catalog_cover_over_broken_local(item)

    status = _enrichment_status_from_item(item)
    item["enrichment_status"] = status
    conf = _confidence_from_item(item)
    item["enrichment_confidence"] = float(conf) if conf is not None else None
    if item.get("catalog_match_source_id") is not None:
        item["catalog_match_id"] = int(item["catalog_match_source_id"])
    notes: list[str] = []
    if item.get("catalog_release_source_text"):
        notes.append(str(item["catalog_release_source_text"]))
    rejected = (item.get("catalog_match_diagnostics") or {}).get("rejected_reason")
    if rejected:
        notes.append(f"rejected: {rejected}")
    item["enrichment_notes"] = "; ".join(notes) if notes else None

    foc = _lookup_foc_date(session, item)
    if foc is not None:
        item["foc_date"] = foc.isoformat()

    if status == "matched":
        if item.get("catalog_match_title"):
            item["canonical_title"] = item["catalog_match_title"]
        if item.get("catalog_match_publisher"):
            item["publisher"] = item["catalog_match_publisher"]
            item["canonical_publisher"] = item["catalog_match_publisher"]
        if item.get("catalog_match_issue_number"):
            item["issue_number"] = item["catalog_match_issue_number"]

    return item


def enrich_retailer_draft_import_for_confirm(
    session: Session,
    *,
    owner_user_id: int,
    draft_import: DraftImport,
    time_budget_seconds: float | None = None,
) -> RetailerEnrichmentSummary:
    """Enrich draft lines with catalog metadata before confirm (errors are logged, not raised).

    Enrichment is best-effort and time-boxed: once ``time_budget_seconds`` of wall-clock
    time is consumed, the remaining lines are left as ``needs_review`` so that confirm can
    proceed to create inventory immediately rather than hanging on slow catalog lookups.
    """
    if time_budget_seconds is None:
        time_budget_seconds = DEFAULT_ENRICH_TIME_BUDGET_SECONDS
    payload = ParseOrderResponse.model_validate(draft_import.parsed_payload_json or {})
    enriched_items: list[AiDraftOrderItem] = []
    draft_id = int(draft_import.id or 0)

    started = time.monotonic()
    budget_exceeded = False
    enriched_count = 0
    skipped_count = 0
    matched_count = 0
    needs_review_count = 0

    for line_index, item in enumerate(payload.items, start=1):
        item_dict = item.model_dump(mode="json")

        if not budget_exceeded and (time.monotonic() - started) > time_budget_seconds:
            budget_exceeded = True

        if budget_exceeded:
            item_dict["enrichment_status"] = "needs_review"
            enriched_item = AiDraftOrderItem.model_validate(item_dict)
            enriched_items.append(enriched_item)
            skipped_count += 1
            needs_review_count += 1
            continue

        enriched = enrich_retailer_draft_item_dict(session, owner_user_id=owner_user_id, item=item_dict)
        enriched_item = AiDraftOrderItem.model_validate(enriched)
        enriched_items.append(enriched_item)
        enriched_count += 1
        if enriched.get("enrichment_status") == "matched":
            matched_count += 1
        else:
            needs_review_count += 1
        if draft_id:
            try:
                upsert_line_cover_resolution_from_item(
                    session,
                    owner_user_id=owner_user_id,
                    draft_import_id=draft_id,
                    line_index=line_index,
                    item=enriched_item,
                )
            except Exception:
                logger.warning(
                    "retailer_catalog_enrich line cover persist failed draft=%s line=%s",
                    draft_id,
                    line_index,
                    exc_info=True,
                )

    payload = payload.model_copy(update={"items": enriched_items})
    draft_import.parsed_payload_json = payload.model_dump(mode="json")
    session.add(draft_import)
    session.flush()

    elapsed = time.monotonic() - started
    if budget_exceeded:
        logger.warning(
            "retailer_catalog_enrich budget exceeded draft=%s budget=%.1fs elapsed=%.2fs enriched=%s skipped=%s",
            draft_id,
            time_budget_seconds,
            elapsed,
            enriched_count,
            skipped_count,
        )
    return RetailerEnrichmentSummary(
        total_items=len(payload.items),
        enriched_items=enriched_count,
        skipped_items=skipped_count,
        matched_items=matched_count,
        needs_review_items=needs_review_count,
        budget_exceeded=budget_exceeded,
        elapsed_seconds=elapsed,
    )


def apply_retailer_enrichment_to_confirmed_order(
    session: Session,
    *,
    owner_user_id: int,
    order_id: int,
    draft_import: DraftImport,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> None:
    """Copy enrichment fields from draft items onto order lines and inventory copies."""
    _ = owner_user_id
    payload = ParseOrderResponse.model_validate(draft_import.parsed_payload_json or {})
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id.asc())
    ).all()
    if len(order_items) != len(payload.items):
        logger.warning(
            "retailer_enrichment_apply count mismatch order=%s items=%s draft_lines=%s",
            order_id,
            len(order_items),
            len(payload.items),
        )

    for index, draft_item in enumerate(payload.items):
        if index >= len(order_items):
            break
        order_item = order_items[index]
        order_item.catalog_match_id = draft_item.catalog_match_id
        order_item.enrichment_status = draft_item.enrichment_status
        if draft_item.enrichment_confidence is not None:
            order_item.enrichment_confidence = Decimal(str(draft_item.enrichment_confidence))
        order_item.enrichment_notes = draft_item.enrichment_notes
        foc_val = draft_item.foc_date
        if foc_val:
            if isinstance(foc_val, date):
                order_item.foc_date = foc_val
            else:
                try:
                    order_item.foc_date = date.fromisoformat(str(foc_val))
                except ValueError:
                    pass
        session.add(order_item)

        source_url = draft_item.source_image_url or draft_item.retailer_cover_url
        copies = session.exec(
            select(InventoryCopy).where(InventoryCopy.order_item_id == order_item.id)
        ).all()
        for copy in copies:
            if source_url:
                copy.source_image_url = source_url
            if draft_item.parsed_release_date and copy.release_date is None:
                copy.release_date = draft_item.parsed_release_date
            # Keep release_year / release_status consistent with the resolved
            # release date so detail pages don't show "Not recorded" / "unknown"
            # for a book whose date we actually know.
            if copy.release_date is not None:
                copy.release_year = copy.release_date.year
                if copy.release_status not in ("released", "not_released_yet"):
                    copy.release_status = (
                        "released" if copy.release_date <= date.today() else "not_released_yet"
                    )
            session.add(copy)

        if index < len(item_snapshots):
            snap = item_snapshots[index]
            raw = dict(snap.raw_item_json or {})
            raw["enrichment_status"] = draft_item.enrichment_status
            raw["enrichment_confidence"] = draft_item.enrichment_confidence
            raw["catalog_match_id"] = draft_item.catalog_match_id
            raw["enrichment_notes"] = draft_item.enrichment_notes
            raw["cover_image_url"] = draft_item.cover_image_url
            raw["source_image_url"] = source_url
            snap.raw_item_json = raw
            session.add(snap)
