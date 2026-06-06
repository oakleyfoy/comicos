"""P78-01 listing draft generation and pricing."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.p78_sell_workflow import P78ListingDraft, utc_now
from app.schemas.p78_sell_workflow import (
    P78ListingDraftCreate,
    P78ListingDraftListResponse,
    P78ListingDraftRead,
    P78ListingDraftUpdate,
    P78ListingPricingRead,
)
from app.services.p71_sell_context import load_sell_intel_contexts
from app.services.p71_sell_scoring import score_listing
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.storage_copy_meta import copy_display_meta


def _condition_for(grade_status: str) -> str:
    g = (grade_status or "raw").lower()
    if g in {"9.8", "9.6", "nm"}:
        return "NM"
    if g in {"9.4", "9.2", "9.0"}:
        return "VF/NM"
    if g in {"8.5", "8.0", "vf"}:
        return "VF"
    return "NM"


def _pricing_from_fmv(fmv: float, *, days: float | None = None) -> P78ListingPricingRead:
    if fmv <= 0:
        return P78ListingPricingRead(fmv=0, quick_sale_price=0, market_price=0, premium_price=0, expected_days_to_sell=days)
    return P78ListingPricingRead(
        fmv=round(fmv, 2),
        quick_sale_price=round(fmv * 0.86, 2),
        market_price=round(fmv * 0.99, 2),
        premium_price=round(fmv * 1.14, 2),
        expected_days_to_sell=days,
    )


def _build_description(meta: dict[str, str], *, grade_status: str, notes: str = "") -> str:
    lines = [
        meta.get("title", "Comic book listing"),
        f"Publisher: {meta.get('publisher') or 'See photos'}",
        f"Issue: {meta.get('issue_number') or '—'}",
        f"Variant: {meta.get('variant_label') or 'Standard'}",
        f"Condition: {_condition_for(grade_status)} (collector-estimated; see photos).",
        "Shipped bagged and boarded in a rigid mailer.",
    ]
    if notes.strip():
        lines.append(notes.strip())
    return "\n".join(lines)


def _ebay_title(meta: dict[str, str], *, publisher: str) -> str:
    series = meta.get("series_name") or meta.get("title") or "Comic"
    issue = meta.get("issue_number") or ""
    pub = publisher or meta.get("publisher") or ""
    variant = meta.get("variant_label") or ""
    bits = [series]
    if issue:
        bits.append(f"#{issue}")
    if variant and variant != "Standard":
        bits.append(variant)
    bits.append("NM")
    if pub:
        bits.append(pub)
    bits.append("Comics")
    return " ".join(bits)[:80]


def _to_read(row: P78ListingDraft) -> P78ListingDraftRead:
    return P78ListingDraftRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_copy_id=row.inventory_copy_id,
        status=row.status,  # type: ignore[arg-type]
        title=row.title,
        description=row.description,
        condition_suggested=row.condition_suggested,
        category=row.category,
        shipping_recommendation=row.shipping_recommendation,
        suggested_sell_quantity=int(row.suggested_sell_quantity),
        fmv_at_generation=float(row.fmv_at_generation),
        quick_sale_price=float(row.quick_sale_price),
        market_price=float(row.market_price),
        premium_price=float(row.premium_price),
        priority=row.priority,  # type: ignore[arg-type]
        signals=list(row.signals_json or []),
        bundle_key=row.bundle_key,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _ctx_for_copy(session: Session, *, owner_user_id: int, copy_id: int):
    for ctx in load_sell_intel_contexts(session, owner_user_id=owner_user_id):
        if ctx.copy_id == copy_id:
            return ctx
    return None


def generate_listing_draft(
    session: Session,
    *,
    owner_user_id: int,
    payload: P78ListingDraftCreate,
) -> P78ListingDraftRead:
    copy = session.get(InventoryCopy, payload.inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")
    ctx = _ctx_for_copy(session, owner_user_id=owner_user_id, copy_id=payload.inventory_copy_id)
    meta = copy_display_meta(session, copy)
    fmv = float(ctx.estimated_fmv if ctx else float(copy.current_fmv or 0))
    bin_p, _, _, _, _, _, days, _, _ = score_listing(ctx) if ctx else (None, None, None, None, 0, 0, 14.0, "", {})
    if bin_p:
        fmv = float(bin_p) / 0.97 if fmv <= 0 else fmv
    pricing = _pricing_from_fmv(fmv, days=days)
    queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=200, offset=0, refresh_upstream=False)
    q_item = next((i for i in queue.items if i.inventory_copy_id == payload.inventory_copy_id), None)
    priority = q_item.priority if q_item else "MEDIUM"
    signals = q_item.signals if q_item else []
    qty = payload.suggested_sell_quantity or (q_item.suggested_sell_quantity if q_item else 1) or 1

    now = utc_now()
    row = P78ListingDraft(
        owner_user_id=owner_user_id,
        inventory_copy_id=payload.inventory_copy_id,
        status=payload.status,
        title=_ebay_title(meta, publisher=meta.get("publisher", "")),
        description=_build_description(meta, grade_status=copy.grade_status or "raw", notes=copy.condition_notes or ""),
        condition_suggested=_condition_for(copy.grade_status or "raw"),
        category="Comics & Graphic Novels",
        shipping_recommendation="Gemini Mailer · Bagged & Boarded",
        suggested_sell_quantity=int(qty),
        fmv_at_generation=pricing.fmv,
        quick_sale_price=pricing.quick_sale_price,
        market_price=pricing.market_price,
        premium_price=pricing.premium_price,
        priority=priority,
        signals_json=signals,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return _to_read(row)


def list_listing_drafts(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> P78ListingDraftListResponse:
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    stmt = select(P78ListingDraft).where(P78ListingDraft.owner_user_id == owner_user_id)
    if status:
        stmt = stmt.where(P78ListingDraft.status == status.strip().upper())
    rows = list(
        session.exec(stmt.order_by(P78ListingDraft.updated_at.desc(), P78ListingDraft.id.desc())).all()
    )
    total = len(rows)
    page = rows[off : off + lim]
    return P78ListingDraftListResponse(items=[_to_read(r) for r in page], total_items=total, limit=lim, offset=off)


def get_listing_draft(session: Session, *, owner_user_id: int, draft_id: int) -> P78ListingDraft:
    row = session.get(P78ListingDraft, draft_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Listing draft not found.")
    return row


def update_listing_draft(
    session: Session,
    *,
    owner_user_id: int,
    draft_id: int,
    payload: P78ListingDraftUpdate,
) -> P78ListingDraftRead:
    row = get_listing_draft(session, owner_user_id=owner_user_id, draft_id=draft_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.flush()
    return _to_read(row)


def pricing_for_draft(session: Session, *, owner_user_id: int, draft_id: int) -> P78ListingPricingRead:
    row = get_listing_draft(session, owner_user_id=owner_user_id, draft_id=draft_id)
    if row.inventory_copy_id is None:
        return _pricing_from_fmv(float(row.fmv_at_generation))
    ctx = _ctx_for_copy(session, owner_user_id=owner_user_id, copy_id=int(row.inventory_copy_id))
    fmv = float(ctx.estimated_fmv if ctx else row.fmv_at_generation)
    _, _, _, _, _, _, days, _, _ = score_listing(ctx) if ctx else (None, None, None, None, 0, 0, None, "", {})
    return _pricing_from_fmv(fmv, days=days)
