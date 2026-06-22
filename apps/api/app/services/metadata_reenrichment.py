from dataclasses import dataclass

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    CatalogVariant,
    DraftImport,
    InventoryCopy,
    OrderItem,
    Variant,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    cover_name_expr,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.schemas.orders import OrderItemCreate
from app.services.imports import (
    build_draft_import_audit_snapshot,
    normalize_parsed_order_response,
    sync_canonical_creators_for_payload,
)
from app.services.metadata_audits import record_metadata_audit
from app.services.orders import resolve_order_item_canonical_series


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class _CopyMetadataFields:
    publisher_name: str
    title_name: str
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None


def get_draft_import_for_ops_or_404(session: Session, import_id: int) -> DraftImport:
    draft_import = session.get(DraftImport, import_id)
    if draft_import is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return draft_import


def get_inventory_copy_for_ops_or_404(session: Session, inventory_copy_id: int) -> InventoryCopy:
    inventory_copy = session.get(InventoryCopy, inventory_copy_id)
    if inventory_copy is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    return inventory_copy


def enqueue_reenrichment_audit(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    actor_user_id: int | None,
    reason: str | None,
) -> None:
    record_metadata_audit(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        action="re_enrichment_queued",
        reason=reason,
        actor_user_id=actor_user_id,
    )


def re_enrich_draft_import(
    session: Session,
    *,
    draft_import_id: int,
    actor_user_id: int | None = None,
    reason: str | None = None,
) -> DraftImport:
    draft_import = get_draft_import_for_ops_or_404(session, draft_import_id)
    if draft_import.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft imports can be re-enriched")

    before_snapshot = build_draft_import_audit_snapshot(draft_import)
    normalized_payload = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(draft_import.parsed_payload_json),
        session=session,
        owner_user_id=draft_import.user_id,
        raw_text=draft_import.raw_text,
    )
    sync_canonical_creators_for_payload(
        session,
        normalized_payload,
        actor_user_id=actor_user_id,
        audit_reason="Deterministic draft re-enrichment.",
    )
    draft_import.parsed_payload_json = normalized_payload.model_dump(mode="json")
    draft_import.confidence_score = normalized_payload.confidence_score
    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="draft_item",
        entity_id=draft_import.id,
        action="re_enriched",
        before_snapshot=before_snapshot,
        after_snapshot=build_draft_import_audit_snapshot(draft_import),
        reason=reason or "Draft metadata re-enriched deterministically.",
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(draft_import)
    return draft_import


def _load_inventory_copy_context(
    session: Session,
    inventory_copy_id: int,
) -> tuple[InventoryCopy, OrderItem | None, _CopyMetadataFields]:
    inventory_copy = session.get(InventoryCopy, inventory_copy_id)
    if inventory_copy is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    order_item = (
        session.get(OrderItem, inventory_copy.order_item_id)
        if inventory_copy.order_item_id is not None
        else None
    )
    row = session.exec(
        apply_inventory_spine_joins(
            select(
                title_expr().label("title_name"),
                publisher_expr().label("publisher_name"),
                issue_number_expr().label("issue_number"),
                cover_name_expr().label("cover_name"),
                func.coalesce(Variant.printing, None).label("printing"),
                func.coalesce(Variant.ratio, CatalogVariant.ratio).label("ratio"),
                func.coalesce(Variant.variant_type, None).label("variant_type"),
                func.coalesce(Variant.cover_artist, CatalogVariant.cover_artist).label("cover_artist"),
            ).select_from(InventoryCopy)
        ).where(InventoryCopy.id == inventory_copy_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    fields = _CopyMetadataFields(
        publisher_name=str(row.publisher_name or "Unknown"),
        title_name=str(row.title_name or "Unknown"),
        issue_number=str(row.issue_number or ""),
        cover_name=row.cover_name,
        printing=row.printing,
        ratio=row.ratio,
        variant_type=row.variant_type,
        cover_artist=row.cover_artist,
    )
    return inventory_copy, order_item, fields


def _inventory_copy_snapshot(
    copy: InventoryCopy,
    *,
    fields: _CopyMetadataFields,
) -> dict:
    return {
        "id": copy.id,
        "metadata_identity_key": copy.metadata_identity_key,
        "canonical_series_id": copy.canonical_series_id,
        "release_date": copy.release_date,
        "release_year": copy.release_year,
        "variant_id": copy.variant_id,
        "order_item_id": copy.order_item_id,
        "publisher": fields.publisher_name,
        "title": fields.title_name,
        "issue_number": fields.issue_number,
        "cover_name": fields.cover_name,
        "printing": fields.printing,
        "ratio": fields.ratio,
        "variant_type": fields.variant_type,
        "cover_artist": fields.cover_artist,
        "acquisition_cost": copy.acquisition_cost,
        "grade_status": copy.grade_status,
        "hold_status": copy.hold_status,
        "current_fmv": copy.current_fmv,
        "star_rating": copy.star_rating,
        "condition_notes": copy.condition_notes,
    }


def re_enrich_inventory_copy(
    session: Session,
    *,
    inventory_copy_id: int,
    actor_user_id: int | None = None,
    reason: str | None = None,
) -> InventoryCopy:
    inventory_copy, order_item, fields = _load_inventory_copy_context(
        session,
        inventory_copy_id,
    )

    before_snapshot = _inventory_copy_snapshot(
        inventory_copy,
        fields=fields,
    )
    order_item_payload = OrderItemCreate.model_validate(
        {
            "publisher": fields.publisher_name,
            "title": fields.title_name,
            "release_date": inventory_copy.release_date,
            "release_year": inventory_copy.release_year,
            "issue_number": fields.issue_number,
            "cover_name": fields.cover_name,
            "printing": fields.printing,
            "ratio": fields.ratio,
            "variant_type": fields.variant_type,
            "cover_artist": fields.cover_artist,
            "metadata_identity_key": inventory_copy.metadata_identity_key,
            "quantity": 1,
            "raw_item_price": inventory_copy.acquisition_cost,
        }
    )
    canonical_series = resolve_order_item_canonical_series(
        session,
        order_item_payload,
        actor_user_id=actor_user_id,
        audit_reason="Canonical series sync during inventory re-enrichment.",
    )

    source_item = AiDraftOrderItem.model_validate(
        {
            "publisher": fields.publisher_name,
            "raw_publisher": fields.publisher_name,
            "title": fields.title_name,
            "raw_title": fields.title_name,
            "release_date": (
                inventory_copy.release_date.isoformat()
                if inventory_copy.release_date is not None
                else str(inventory_copy.release_year)
                if inventory_copy.release_year is not None
                else None
            ),
            "raw_release_date": (
                inventory_copy.release_date.isoformat()
                if inventory_copy.release_date is not None
                else str(inventory_copy.release_year)
                if inventory_copy.release_year is not None
                else None
            ),
            "release_status": inventory_copy.release_status,
            "order_status": inventory_copy.order_status,
            "expected_ship_date": (
                inventory_copy.expected_ship_date.isoformat()
                if inventory_copy.expected_ship_date is not None
                else None
            ),
            "received_at": inventory_copy.received_at,
            "issue_number": fields.issue_number,
            "raw_issue_number": fields.issue_number,
            "cover_name": fields.cover_name,
            "printing": fields.printing,
            "ratio": fields.ratio,
            "variant_type": fields.variant_type,
            "cover_artist": fields.cover_artist,
            "quantity": 1,
            "raw_item_price": inventory_copy.acquisition_cost,
            "metadata_identity_key": inventory_copy.metadata_identity_key,
        }
    )
    normalized = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(
            {
                "retailer": None,
                "order_date": None,
                "source_type": "manual_draft",
                "shipping_amount": "0.00",
                "tax_amount": "0.00",
                "items": [source_item.model_dump(mode="json")],
                "warnings": [],
                "confidence_score": 1.0,
            }
        ),
        session=session,
        owner_user_id=inventory_copy.user_id,
        raw_text="",
    )
    normalized_item = normalized.items[0]
    inventory_copy.metadata_identity_key = normalized_item.metadata_identity_key
    inventory_copy.canonical_series_id = canonical_series.id
    inventory_copy.release_date = normalized_item.parsed_release_date
    inventory_copy.release_year = normalized_item.parsed_release_year
    session.add(inventory_copy)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="inventory_copy",
        entity_id=inventory_copy.id,
        action="re_enriched",
        before_snapshot=before_snapshot,
        after_snapshot=_inventory_copy_snapshot(
            inventory_copy,
            fields=fields,
        ),
        reason=reason or "Inventory metadata re-enriched deterministically.",
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(inventory_copy)
    return inventory_copy


def build_metadata_reenrichment_job_result(
    *,
    entity_type: str,
    entity_id: int,
    status: str = "success",
    reason: str | None = None,
) -> dict:
    result = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": status,
    }
    if reason:
        result["reason"] = reason
    return result
