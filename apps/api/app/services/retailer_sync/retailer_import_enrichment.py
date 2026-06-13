from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from sqlmodel import Session, select

from app.models import (
    DraftImport,
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.schemas.imports import DraftImportUpdate
from app.services.imports import persist_draft_import, update_import_for_user


def _retailer_display_name(retailer: str) -> str:
    return {
        "midtown": "Midtown Comics",
    }.get(retailer.casefold(), retailer.title())


def _draft_warning(order_number: str) -> str:
    return f"Enriched from connected retailer account order #{order_number}."


def _match_existing_item(
    items: list[AiDraftOrderItem], snapshot: RetailerOrderItemSnapshot
) -> int | None:
    for index, item in enumerate(items):
        if snapshot.retailer_item_id and item.retailer_item_id == snapshot.retailer_item_id:
            return index
        if snapshot.product_url and item.retailer_product_url == snapshot.product_url:
            return index
        if (
            item.retailer_order_number == snapshot.retailer_order_number
            and (item.title or "").casefold() == snapshot.title.casefold()
            and (item.issue_number or "") == (snapshot.issue_number or "")
            and (item.cover_name or "") == (snapshot.cover_name or "")
            and item.quantity == snapshot.quantity
            and item.raw_item_price == snapshot.unit_price
        ):
            return index
    return None


def _snapshot_cover_url(snapshot: RetailerOrderItemSnapshot) -> str | None:
    """Web-servable retailer cover URL.

    Saved-HTML imports store a *local* file path in ``image_url`` (e.g.
    ``./Order_files/2539636_ful.jpg``) plus a derived remote URL
    (``remote_midtown_image_url``) in ``raw_item_json``. Prefer the remote URL so
    the cover renders without a catalog match; fall back to the stored ``image_url``.
    """
    raw = snapshot.raw_item_json if isinstance(snapshot.raw_item_json, dict) else {}
    remote = raw.get("remote_midtown_image_url")
    if isinstance(remote, str) and remote.strip():
        return remote.strip()
    return snapshot.image_url


def _snapshot_to_item(snapshot: RetailerOrderItemSnapshot) -> AiDraftOrderItem:
    cover_url = _snapshot_cover_url(snapshot)
    return AiDraftOrderItem(
        title=snapshot.title,
        publisher=snapshot.publisher,
        issue_number=snapshot.issue_number,
        cover_name=snapshot.cover_name,
        variant_type=snapshot.variant_type,
        cover_artist=snapshot.cover_artist,
        quantity=snapshot.quantity,
        raw_item_price=snapshot.unit_price,
        retailer_cover_url=cover_url,
        retailer_thumbnail_url=cover_url or snapshot.thumbnail_url,
        retailer_product_url=snapshot.product_url,
        retailer_sku=snapshot.retailer_item_id,
        retailer_order_number=snapshot.retailer_order_number,
        retailer_item_id=snapshot.retailer_item_id,
        retailer_item_status=snapshot.item_status,
        retailer_shipped_qty=snapshot.shipped_qty,
        retailer_backordered_qty=snapshot.backordered_qty,
        retailer_unavailable_qty=snapshot.unavailable_qty,
        retailer_returned_qty=snapshot.returned_qty,
        order_status=_normalize_order_status(snapshot.item_status),
    )


def _normalize_order_status(status: str | None) -> str | None:
    value = (status or "").casefold()
    if not value:
        return None
    if "cancel" in value:
        return "cancelled"
    if "receive" in value:
        return "received"
    if "ship" in value:
        return "shipped"
    if "pre" in value:
        return "preordered"
    return "ordered"


def _merge_item(
    existing: AiDraftOrderItem, snapshot: RetailerOrderItemSnapshot
) -> AiDraftOrderItem:
    update = {
        "publisher": existing.publisher or snapshot.publisher,
        "title": existing.title or snapshot.title,
        "issue_number": existing.issue_number or snapshot.issue_number,
        "cover_name": existing.cover_name or snapshot.cover_name,
        "variant_type": existing.variant_type or snapshot.variant_type,
        "cover_artist": existing.cover_artist or snapshot.cover_artist,
        "quantity": existing.quantity or snapshot.quantity,
        "raw_item_price": existing.raw_item_price or snapshot.unit_price,
        "retailer_cover_url": _snapshot_cover_url(snapshot) or existing.retailer_cover_url,
        "retailer_thumbnail_url": _snapshot_cover_url(snapshot)
        or snapshot.thumbnail_url
        or existing.retailer_thumbnail_url,
        "retailer_product_url": snapshot.product_url or existing.retailer_product_url,
        "retailer_sku": snapshot.retailer_item_id or existing.retailer_sku,
        "retailer_order_number": snapshot.retailer_order_number,
        "retailer_item_id": snapshot.retailer_item_id or existing.retailer_item_id,
        "retailer_item_status": snapshot.item_status or existing.retailer_item_status,
        "retailer_shipped_qty": snapshot.shipped_qty,
        "retailer_backordered_qty": snapshot.backordered_qty,
        "retailer_unavailable_qty": snapshot.unavailable_qty,
        "retailer_returned_qty": snapshot.returned_qty,
        "order_status": _normalize_order_status(snapshot.item_status) or existing.order_status,
    }
    return existing.model_copy(update=update)


def _build_parsed_payload(
    *,
    retailer: str,
    order_snapshot: RetailerOrderSnapshot,
    item_snapshots: list[RetailerOrderItemSnapshot],
    existing: ParseOrderResponse | None = None,
) -> ParseOrderResponse:
    items = list(existing.items) if existing is not None else []
    for snapshot in item_snapshots:
        match_index = _match_existing_item(items, snapshot)
        if match_index is None:
            items.append(_snapshot_to_item(snapshot))
        else:
            items[match_index] = _merge_item(items[match_index], snapshot)
    warnings = list(existing.warnings) if existing is not None else []
    warning = _draft_warning(order_snapshot.retailer_order_number)
    if warning not in warnings:
        warnings.append(warning)
    return ParseOrderResponse(
        retailer=_retailer_display_name(retailer),
        order_date=order_snapshot.order_date,
        source_type="retailer_account",
        shipping_amount=existing.shipping_amount if existing is not None else Decimal("0"),
        tax_amount=existing.tax_amount if existing is not None else Decimal("0"),
        order_total=order_snapshot.order_total,
        total_books=sum(snapshot.quantity for snapshot in item_snapshots),
        items=items,
        warnings=warnings,
        confidence_score=1.0,
    )


def _retailer_raw_text(
    order_snapshot: RetailerOrderSnapshot,
    item_snapshots: Iterable[RetailerOrderItemSnapshot],
) -> str:
    header = (
        "Retailer account sync import for "
        f"{_retailer_display_name(order_snapshot.retailer)} "
        f"order #{order_snapshot.retailer_order_number}."
    )
    lines = [
        header
    ]
    for item in item_snapshots:
        price = f"${item.unit_price}" if item.unit_price is not None else "unknown price"
        lines.append(f"- {item.quantity} x {item.title} ({price})")
    return "\n".join(lines)


def _find_existing_draft(
    session: Session,
    *,
    owner_user_id: int,
    retailer_order_number: str,
) -> DraftImport | None:
    candidate_imports = session.exec(
        select(DraftImport).where(
            DraftImport.user_id == owner_user_id,
            DraftImport.status == "draft",
        )
    ).all()
    for draft in candidate_imports:
        payload = draft.parsed_payload_json or {}
        items = payload.get("items") or []
        if any(
            isinstance(item, dict) and item.get("retailer_order_number") == retailer_order_number
            for item in items
        ):
            return draft
    return None


def build_parsed_payload_for_retailer_snapshots(
    *,
    retailer: str,
    order_snapshot: RetailerOrderSnapshot,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> ParseOrderResponse:
    """One draft line per retailer snapshot row (no merge with prior draft items)."""
    return _build_parsed_payload(
        retailer=retailer,
        order_snapshot=order_snapshot,
        item_snapshots=item_snapshots,
        existing=None,
    )


def retailer_order_import_raw_text(
    order_snapshot: RetailerOrderSnapshot,
    item_snapshots: Iterable[RetailerOrderItemSnapshot],
) -> str:
    return _retailer_raw_text(order_snapshot, item_snapshots)


def enrich_drafts_from_retailer_orders(
    session: Session,
    *,
    account: RetailerAccount,
    order_snapshots: list[RetailerOrderSnapshot] | None = None,
) -> list[int]:
    owner = session.get(User, account.owner_user_id)
    if owner is None:
        return []
    if order_snapshots is None:
        order_snapshots = session.exec(
            select(RetailerOrderSnapshot)
            .where(RetailerOrderSnapshot.retailer_account_id == account.id)
            .order_by(RetailerOrderSnapshot.order_date.desc(), RetailerOrderSnapshot.id.desc())
        ).all()
    touched_ids: list[int] = []
    for order_snapshot in order_snapshots:
        item_snapshots = session.exec(
            select(RetailerOrderItemSnapshot)
            .where(RetailerOrderItemSnapshot.retailer_order_snapshot_id == order_snapshot.id)
            .order_by(RetailerOrderItemSnapshot.id.asc())
        ).all()
        existing_draft = _find_existing_draft(
            session,
            owner_user_id=account.owner_user_id,
            retailer_order_number=order_snapshot.retailer_order_number,
        )
        existing_payload = (
            ParseOrderResponse.model_validate(existing_draft.parsed_payload_json)
            if existing_draft is not None
            else None
        )
        parsed = _build_parsed_payload(
            retailer=account.retailer,
            order_snapshot=order_snapshot,
            item_snapshots=item_snapshots,
            existing=existing_payload,
        )
        raw_text = _retailer_raw_text(order_snapshot, item_snapshots)
        if existing_draft is None:
            created = persist_draft_import(
                session,
                current_user=owner,
                raw_text=raw_text,
                parsed=parsed,
            )
            touched_ids.append(created.id)
            continue
        updated = update_import_for_user(
            session,
            current_user=owner,
            import_id=int(existing_draft.id),
            payload=DraftImportUpdate(
                raw_text=raw_text,
                parsed_payload_json=parsed,
                confidence_score=parsed.confidence_score,
            ),
        )
        touched_ids.append(updated.id)
    return touched_ids
