"""P89-03 listing draft generation and CRUD."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy
from app.models.p89_listing_draft import P89ListingDraft, utc_now
from app.models.p89_market_price_snapshot import P89MarketPriceSnapshot
from app.models.p89_sell_candidate import P89SellCandidate
from app.services.condition_note_service import generate_condition_notes, grade_display_label, is_slabs
from app.services.listing_description_generator import DescriptionInputs, generate_listing_description
from app.services.listing_title_generator import TitleInputs, generate_listing_title
from app.services.p89_market_pricing_service import lookup_latest_snapshot
from app.services.storage_copy_meta import copy_display_meta


@dataclass(frozen=True)
class PricingBundle:
    suggested: float | None
    minimum: float | None
    premium: float | None
    snapshot_id: int | None
    pricing_unavailable: bool


def _shipping_for_marketplace(marketplace: str) -> str:
    m = marketplace.upper()
    if m == "WHATNOT":
        return "Ships securely with rigid protection; live-show friendly packaging."
    if m == "MYCOMICSHOP":
        return "Ships bagged and boarded in a Gemini mailer via USPS."
    return "Gemini mailer, USPS Ground Advantage."


def _estimated_grade(copy: InventoryCopy) -> str | None:
    if is_slabs(copy.grade_status):
        return None
    if copy.star_rating is not None and int(copy.star_rating) >= 1:
        return f"{int(copy.star_rating)}.0 (collector estimate)"
    return None


def _resolve_pricing(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    meta: dict[str, str],
    snapshot_id: int | None = None,
) -> PricingBundle:
    snap: P89MarketPriceSnapshot | None = None
    if snapshot_id is not None:
        snap = session.get(P89MarketPriceSnapshot, snapshot_id)
        if snap is None or snap.owner_user_id != owner_user_id:
            snap = None
    if snap is None:
        snap = lookup_latest_snapshot(
            session,
            owner_user_id=owner_user_id,
            series=meta.get("series_name") or "",
            issue_number=meta.get("issue_number") or "",
            variant=meta.get("variant_label") or "",
        )
    if snap is not None:
        return PricingBundle(
            suggested=float(snap.market_price) if snap.market_price else None,
            minimum=float(snap.quick_sale_price) if snap.quick_sale_price else None,
            premium=float(snap.premium_price) if snap.premium_price else None,
            snapshot_id=int(snap.id or 0),
            pricing_unavailable=False,
        )
    fmv = float(copy.current_fmv or 0)
    if fmv > 0:
        return PricingBundle(
            suggested=round(fmv, 2),
            minimum=round(fmv * 0.88, 2),
            premium=round(fmv * 1.1, 2),
            snapshot_id=None,
            pricing_unavailable=False,
        )
    return PricingBundle(None, None, None, None, True)


def _key_notes_from_sell_candidate(row: P89SellCandidate | None) -> list[str]:
    if row is None:
        return []
    notes = list(row.reasons_json or [])[:2]
    return [str(n) for n in notes if str(n).strip()]


def _find_copy_for_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snap: P89MarketPriceSnapshot,
) -> InventoryCopy | None:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
        ).all()
    )
    for copy in copies:
        meta = copy_display_meta(session, copy)
        if (meta.get("series_name") or "").strip().lower() == snap.series.strip().lower() and (
            meta.get("issue_number") or ""
        ).strip().lower() == snap.issue_number.strip().lower():
            return copy
    return copies[0] if copies else None


def generate_listing_draft(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int | None,
    marketplace: str,
    sell_candidate_id: int | None = None,
    market_price_snapshot_id: int | None = None,
) -> P89ListingDraft:
    copy: InventoryCopy | None = None
    if inventory_copy_id is None and sell_candidate_id is not None:
        sell_row = session.get(P89SellCandidate, sell_candidate_id)
        if sell_row is not None:
            inventory_copy_id = int(sell_row.inventory_copy_id)
    if inventory_copy_id is None and market_price_snapshot_id is None and sell_candidate_id is None:
        raise HTTPException(status_code=400, detail="inventory_copy_id or market_price_snapshot_id required.")
    if inventory_copy_id is not None:
        copy = session.get(InventoryCopy, inventory_copy_id)
    elif market_price_snapshot_id is not None:
        snap = session.get(P89MarketPriceSnapshot, market_price_snapshot_id)
        if snap is not None and snap.owner_user_id == owner_user_id:
            copy = _find_copy_for_snapshot(session, owner_user_id=owner_user_id, snap=snap)
    if copy is None or int(copy.user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")
    inventory_copy_id = int(copy.id or 0)
    meta = copy_display_meta(session, copy)
    sell_row: P89SellCandidate | None = None
    if sell_candidate_id is not None:
        sell_row = session.get(P89SellCandidate, sell_candidate_id)
        if sell_row is None or sell_row.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="Sell candidate not found.")
    year = str(copy.release_year) if copy.release_year else ""
    est = _estimated_grade(copy)
    grade_label = grade_display_label(copy.grade_status)
    if est and not is_slabs(copy.grade_status):
        grade_label = f"VF/NM est" if int(copy.star_rating or 0) >= 4 else grade_label
    key_notes = _key_notes_from_sell_candidate(sell_row)
    key_note_title = key_notes[0] if key_notes else ""
    title = generate_listing_title(
        TitleInputs(
            series=meta.get("series_name") or meta.get("title") or "Comic",
            issue_number=meta.get("issue_number") or "",
            publisher=meta.get("publisher") or "",
            year=year,
            variant=meta.get("variant_label") or "",
            grade_label=grade_label if not is_slabs(copy.grade_status) else grade_label,
            key_note=key_note_title[:40] if key_note_title else "",
            marketplace=marketplace,
        )
    )
    condition_notes = generate_condition_notes(
        grade_status=copy.grade_status,
        estimated_grade=est,
        inventory_condition_notes=copy.condition_notes,
    )
    shipping = _shipping_for_marketplace(marketplace)
    description = generate_listing_description(
        DescriptionInputs(
            display_title=meta.get("title") or title,
            publisher=meta.get("publisher") or "",
            issue_number=meta.get("issue_number") or "",
            variant=meta.get("variant_label") or "",
            grade_condition=grade_label,
            key_notes=key_notes,
            condition_paragraph=condition_notes,
            shipping_paragraph=shipping,
        )
    )
    pricing = _resolve_pricing(
        session,
        owner_user_id=owner_user_id,
        copy=copy,
        meta=meta,
        snapshot_id=market_price_snapshot_id,
    )
    now = utc_now()
    row = P89ListingDraft(
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        sell_candidate_id=sell_candidate_id,
        market_price_snapshot_id=pricing.snapshot_id,
        marketplace=marketplace.upper(),
        title=title,
        description=description,
        condition_notes=condition_notes,
        shipping_notes=shipping,
        suggested_price=pricing.suggested,
        minimum_price=pricing.minimum,
        premium_price=pricing.premium,
        status="DRAFT",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def list_listing_drafts(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    marketplace: str | None = None,
    inventory_copy_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[P89ListingDraft], int]:
    lim = min(max(limit, 1), 200)
    off = max(offset, 0)
    q = select(P89ListingDraft).where(P89ListingDraft.owner_user_id == owner_user_id)
    if status:
        q = q.where(P89ListingDraft.status == status.strip().upper())
    if marketplace:
        q = q.where(P89ListingDraft.marketplace == marketplace.strip().upper())
    if inventory_copy_id is not None:
        q = q.where(P89ListingDraft.inventory_copy_id == inventory_copy_id)
    rows = list(session.exec(q.order_by(col(P89ListingDraft.created_at).desc())).all())
    total = len(rows)
    return rows[off : off + lim], total


def get_listing_draft(session: Session, *, owner_user_id: int, draft_id: int) -> P89ListingDraft:
    row = session.get(P89ListingDraft, draft_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Listing draft not found.")
    return row


def update_listing_draft(
    session: Session,
    *,
    owner_user_id: int,
    draft_id: int,
    fields: dict,
) -> P89ListingDraft:
    row = get_listing_draft(session, owner_user_id=owner_user_id, draft_id=draft_id)
    allowed = {
        "title",
        "description",
        "condition_notes",
        "shipping_notes",
        "suggested_price",
        "minimum_price",
        "premium_price",
        "status",
    }
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "status" and value:
            value = str(value).upper()
        setattr(row, key, value)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return row


def mark_listing_draft_reviewed(session: Session, *, owner_user_id: int, draft_id: int) -> P89ListingDraft:
    return update_listing_draft(session, owner_user_id=owner_user_id, draft_id=draft_id, fields={"status": "REVIEWED"})


def archive_listing_draft(session: Session, *, owner_user_id: int, draft_id: int) -> P89ListingDraft:
    return update_listing_draft(session, owner_user_id=owner_user_id, draft_id=draft_id, fields={"status": "ARCHIVED"})


def count_drafts_awaiting_review(session: Session, *, owner_user_id: int) -> int:
    from sqlalchemy import func

    n = session.exec(
        select(func.count())
        .select_from(P89ListingDraft)
        .where(P89ListingDraft.owner_user_id == owner_user_id)
        .where(P89ListingDraft.status == "DRAFT")
    ).one()
    if isinstance(n, tuple):
        n = n[0]
    return int(n or 0)


def build_listing_draft_briefing(session: Session, *, owner_user_id: int) -> dict[str, int]:
    from sqlalchemy import func

    total = session.exec(
        select(func.count())
        .select_from(P89ListingDraft)
        .where(P89ListingDraft.owner_user_id == owner_user_id)
    ).one()
    awaiting = count_drafts_awaiting_review(session, owner_user_id=owner_user_id)
    if isinstance(total, tuple):
        total = total[0]
    return {"new_drafts_created": int(total or 0), "drafts_awaiting_review": awaiting}


def draft_display_meta(session: Session, row: P89ListingDraft) -> dict:
    copy = session.get(InventoryCopy, row.inventory_copy_id)
    meta = copy_display_meta(session, copy) if copy else {"title": "Comic"}
    return {
        "comic_title": meta.get("title") or row.title,
        "pricing_unavailable": row.suggested_price is None and row.minimum_price is None,
    }


def full_listing_text(row: P89ListingDraft) -> str:
    price_line = ""
    if row.suggested_price is not None:
        price_line = f"Suggested Price: ${row.suggested_price:.2f}\n"
    elif row.minimum_price is None:
        price_line = "Pricing unavailable.\n"
    parts = [
        f"Title:\n{row.title}\n",
        f"Description:\n{row.description}\n",
    ]
    if price_line:
        parts.append(price_line)
    parts.append(f"Shipping:\n{row.shipping_notes}")
    return "\n".join(parts)
