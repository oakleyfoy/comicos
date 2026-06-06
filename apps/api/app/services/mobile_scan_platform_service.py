"""P80-01 mobile scan identification and intelligence consolidation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.asset_ledger import CoverImage, CoverImageBarcodeCandidate, InventoryCopy, Variant
from app.models.external_catalog import ExternalCatalogIssue
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.intelligence import IntelligenceRecommendation
from app.models.p80_mobile_scan import P80MobileScan, P80_CONFIDENCE_LEVELS, utc_now
from app.models.storage_location import (
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageSlot,
)
from app.schemas.mobile_scan_platform import (
    P80ActionCardRead,
    P80BookIdentificationRead,
    P80BookIntelligenceRead,
    P80FmvIntelligenceRead,
    P80GradingIntelligenceRead,
    P80MobileScanCreateRequest,
    P80MobileScanResultRead,
    P80OwnershipIntelligenceRead,
    P80RecommendationIntelligenceRead,
    P80ScanIdentificationRead,
    P80StorageIntelligenceRead,
    P80StorageLocationRead,
)
from app.services.authoritative_fmv_service import _liquidity_bucket, get_authoritative_fmv
from app.services.grading_candidate_engine import REC_GRADE, REC_PRESS_AND_GRADE, build_grading_decision_for_copy
from app.services.inventory_locator_service import _path_fields
from app.services.mobile_scan_registry import normalize_scan_value
from app.services.mobile_scan_upc_registry import lookup_known_upc
from app.services.p72_grading_decision_dashboard import get_p72_decision_for_copy
from app.services.storage_copy_meta import copy_display_meta

P79_QR_PATTERN = re.compile(r"^comicos://p79/storage/([^/]+)/(\d+)$", re.IGNORECASE)

GRADED_STATUSES = frozenset({"graded", "cgc", "cbcs", "pgx"})


@dataclass(frozen=True)
class _BookIdentity:
    book_identity_key: str
    variant_id: int | None
    title: str
    series_name: str
    issue_number: str
    variant_description: str
    publisher: str
    release_date: str | None
    cover_image_url: str | None
    identification_source: str
    representative_copy_id: int | None


def _normalize_barcode(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Barcode or manual entry is required.")
    try:
        if value.lower().startswith("comicos://"):
            return value.strip()
        if len(value) >= 12 and value.isdigit():
            return normalize_scan_value("upc", value)
        return normalize_scan_value("barcode", value)
    except ValueError:
        return value.strip().upper()


def _book_from_copy(session: Session, copy: InventoryCopy, *, source: str) -> _BookIdentity:
    meta = copy_display_meta(session, copy)
    variant_id = int(copy.variant_id) if copy.variant_id else None
    key = f"variant:{variant_id}" if variant_id else f"copy:{int(copy.id or 0)}"
    release: str | None = None
    if copy.release_year:
        release = str(copy.release_year)
    return _BookIdentity(
        book_identity_key=key,
        variant_id=variant_id,
        title=meta["title"],
        series_name=meta["series_name"],
        issue_number=meta["issue_number"],
        variant_description=meta["variant_label"],
        publisher=meta["publisher"],
        release_date=release,
        cover_image_url=None,
        identification_source=source,
        representative_copy_id=int(copy.id or 0),
    )


def _book_from_known_upc(payload: dict[str, Any]) -> _BookIdentity:
    title = str(payload.get("title") or "Unknown title")
    key = f"catalog:{payload.get('catalog_key') or payload.get('upc')}"
    return _BookIdentity(
        book_identity_key=key,
        variant_id=None,
        title=title,
        series_name=title,
        issue_number="",
        variant_description=str(payload.get("format") or ""),
        publisher="",
        release_date=None,
        cover_image_url=None,
        identification_source="known_upc",
        representative_copy_id=None,
    )


def _book_from_external_issue(row: ExternalCatalogIssue) -> _BookIdentity:
    key = f"external_issue:{int(row.id or 0)}"
    title = row.title or f"{row.series_name} #{row.issue_number or ''}".strip()
    release = row.release_date.isoformat() if row.release_date else None
    return _BookIdentity(
        book_identity_key=key,
        variant_id=None,
        title=title.strip(),
        series_name=row.series_name or "",
        issue_number=row.issue_number or "",
        variant_description="",
        publisher=row.publisher or "",
        release_date=release,
        cover_image_url=row.cover_image_url or row.thumbnail_url,
        identification_source="external_catalog",
        representative_copy_id=None,
    )


def _parse_p79_qr(value: str) -> tuple[str, int] | None:
    match = P79_QR_PATTERN.match(value.strip())
    if not match:
        return None
    return match.group(1).lower(), int(match.group(2))


def _find_external_by_upc(session: Session, upc: str) -> ExternalCatalogIssue | None:
    rows = session.exec(select(ExternalCatalogIssue).order_by(ExternalCatalogIssue.id.asc())).all()
    for row in rows:
        signals = row.importance_signals_json or {}
        signal_upc = str(signals.get("upc") or "").strip()
        if signal_upc and signal_upc == upc:
            return row
    return None


def _variant_from_barcode_candidate(session: Session, upc: str) -> Variant | None:
    candidate = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.normalized_upc_value == upc)
        .order_by(CoverImageBarcodeCandidate.id.desc())
    ).first()
    if candidate is None:
        return None
    cover = session.get(CoverImage, candidate.cover_image_id)
    if cover is None or cover.inventory_copy_id is None:
        return None
    copy = session.get(InventoryCopy, cover.inventory_copy_id)
    if copy is None:
        return None
    return session.get(Variant, copy.variant_id) if copy.variant_id else None


def _copies_for_variant(session: Session, *, owner_user_id: int, variant_id: int) -> list[InventoryCopy]:
    return list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.variant_id == variant_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )


def _copies_for_book_key(
    session: Session,
    *,
    owner_user_id: int,
    identity: _BookIdentity,
) -> list[InventoryCopy]:
    if identity.variant_id is not None:
        return _copies_for_variant(session, owner_user_id=owner_user_id, variant_id=identity.variant_id)
    if identity.representative_copy_id is not None:
        copy = session.get(InventoryCopy, identity.representative_copy_id)
        if copy is not None and copy.user_id == owner_user_id:
            return [copy]
    if identity.series_name and identity.issue_number:
        matches: list[InventoryCopy] = []
        key = f"{identity.series_name}|{identity.issue_number}".lower()
        for copy in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all():
            meta = copy_display_meta(session, copy)
            if f"{meta['series_name']}|{meta['issue_number']}".lower() == key:
                matches.append(copy)
        return matches
    return []


def _identify_book(
    session: Session,
    *,
    owner_user_id: int,
    normalized: str,
) -> tuple[_BookIdentity | None, str, str, dict | None]:
    storage_entity: dict | None = None
    qr = _parse_p79_qr(normalized)
    if qr is not None:
        entity_type, entity_id = qr
        storage_entity = {"entity_type": entity_type, "entity_id": entity_id, "qr_payload": normalized}
        if entity_type == "box":
            box = session.get(P79StorageBox, entity_id)
            if box is not None and box.owner_user_id == owner_user_id:
                slot_ids = [
                    int(s.id or 0)
                    for s in session.exec(select(P79StorageSlot).where(P79StorageSlot.box_id == entity_id)).all()
                ]
                if slot_ids:
                    assign = session.exec(
                        select(P79InventoryLocationAssignment)
                        .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
                        .where(col(P79InventoryLocationAssignment.storage_slot_id).in_(slot_ids))
                        .order_by(P79InventoryLocationAssignment.id.asc())
                    ).first()
                    if assign is not None:
                        copy = session.get(InventoryCopy, assign.inventory_copy_id)
                        if copy is not None and copy.user_id == owner_user_id:
                            return (
                                _book_from_copy(session, copy, source="p79_storage_qr"),
                                "HIGH",
                                "QR_STORAGE",
                                storage_entity,
                            )
        return None, "MEDIUM", "QR_STORAGE", storage_entity

    if normalized.isdigit():
        copy_id = int(normalized)
        copy = session.get(InventoryCopy, copy_id)
        if copy is not None and copy.user_id == owner_user_id:
            return _book_from_copy(session, copy, source="inventory_copy_id"), "HIGH", "BARCODE", None

    external = _find_external_by_upc(session, normalized)
    if external is not None:
        identity = _book_from_external_issue(external)
        owned = _copies_for_book_key(session, owner_user_id=owner_user_id, identity=identity)
        if owned:
            identity = _book_from_copy(session, owned[0], source="external_catalog_inventory")
            return identity, "HIGH", "BARCODE", None
        return identity, "MEDIUM", "BARCODE", None

    known = lookup_known_upc(normalized)
    if known is not None:
        identity = _book_from_known_upc(known)
        owned = _copies_for_book_key(session, owner_user_id=owner_user_id, identity=identity)
        if owned:
            identity = _book_from_copy(session, owned[0], source="known_upc_inventory")
            return identity, "HIGH", "BARCODE", None
        return identity, "MEDIUM", "BARCODE", None

    variant = _variant_from_barcode_candidate(session, normalized)
    if variant is not None:
        copies = _copies_for_variant(session, owner_user_id=owner_user_id, variant_id=int(variant.id or 0))
        if copies:
            return _book_from_copy(session, copies[0], source="barcode_candidate"), "HIGH", "BARCODE", None

    return None, "LOW", "BARCODE", storage_entity


def _ownership_for_identity(
    session: Session,
    *,
    owner_user_id: int,
    identity: _BookIdentity,
) -> P80OwnershipIntelligenceRead:
    copies = _copies_for_book_key(session, owner_user_id=owner_user_id, identity=identity)
    graded = 0
    raw = 0
    ids: list[int] = []
    for copy in copies:
        cid = int(copy.id or 0)
        ids.append(cid)
        status = (copy.grade_status or "raw").lower()
        if status in GRADED_STATUSES:
            graded += 1
        else:
            raw += 1
    return P80OwnershipIntelligenceRead(
        owned=len(copies) > 0,
        total_copies=len(copies),
        graded_copies=graded,
        raw_copies=raw,
        inventory_copy_ids=ids,
    )


def _fmv_for_copy(session: Session, *, owner_user_id: int, copy_id: int) -> P80FmvIntelligenceRead:
    view = get_authoritative_fmv(session, owner_user_id=owner_user_id, inventory_copy_id=copy_id)
    if view is None:
        copy = session.get(InventoryCopy, copy_id)
        fmv = float(copy.current_fmv) if copy and copy.current_fmv else None
        return P80FmvIntelligenceRead(
            authoritative_fmv=fmv,
            confidence_score=None,
            liquidity_rating=None,
            sales_velocity=None,
        )
    velocity = float(view.sales_count or 0) / 3.0
    return P80FmvIntelligenceRead(
        authoritative_fmv=view.authoritative_fmv,
        confidence_score=view.confidence,
        liquidity_rating=_liquidity_bucket(view.liquidity_score),
        sales_velocity=round(velocity, 3),
        price_trend_30d=view.price_trend_30d,
    )


def _recommendation_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    copy_id: int,
    title: str,
) -> P80RecommendationIntelligenceRead:
    hold = session.exec(
        select(HoldSellRecommendation)
        .where(HoldSellRecommendation.owner_user_id == owner_user_id)
        .where(HoldSellRecommendation.inventory_item_id == copy_id)
        .order_by(HoldSellRecommendation.created_at.desc(), HoldSellRecommendation.id.desc())
    ).first()
    if hold is not None:
        return P80RecommendationIntelligenceRead(
            recommendation=hold.recommendation,
            conviction_score=hold.conviction_score,
            confidence_score=hold.confidence_score,
            rationale=hold.rationale,
            source_system="P51_HOLD_SELL",
        )
    intel = session.exec(
        select(IntelligenceRecommendation)
        .where(IntelligenceRecommendation.inventory_copy_id == copy_id)
        .order_by(IntelligenceRecommendation.priority_score.desc(), IntelligenceRecommendation.id.desc())
    ).first()
    if intel is not None:
        rec = _map_intel_type_to_action(intel.recommendation_type)
        return P80RecommendationIntelligenceRead(
            recommendation=rec,
            conviction_score=intel.opportunity_score,
            confidence_score=intel.confidence_score,
            rationale=intel.description,
            source_system="P51_INTELLIGENCE",
        )
    return P80RecommendationIntelligenceRead(
        recommendation="WATCH" if title else None,
        source_system="P73_DEFAULT",
        rationale="No personalized recommendation yet; defaulting to watch.",
    )


def _map_intel_type_to_action(recommendation_type: str) -> str:
    token = recommendation_type.strip().lower()
    if "sell" in token:
        return "SELL"
    if "buy" in token or "acquire" in token:
        return "BUY"
    if "grade" in token:
        return "GRADE"
    if "watch" in token:
        return "WATCH"
    return "HOLD"


def _grading_for_copy(session: Session, *, owner_user_id: int, copy_id: int) -> P80GradingIntelligenceRead:
    decision = get_p72_decision_for_copy(session, owner_user_id=owner_user_id, inventory_copy_id=copy_id)
    if decision is not None:
        return P80GradingIntelligenceRead(
            grade_recommendation=decision.recommendation,
            press_recommendation=decision.pressing_recommendation,
            expected_grade=decision.expected_grade,
            estimated_roi_pct=decision.expected_roi_pct,
        )
    copy = session.get(InventoryCopy, copy_id)
    if copy is None:
        return P80GradingIntelligenceRead()
    built = build_grading_decision_for_copy(session, owner_user_id=owner_user_id, copy=copy)
    if built is None:
        return P80GradingIntelligenceRead()
    return P80GradingIntelligenceRead(
        grade_recommendation=built.recommendation,
        press_recommendation=built.pressing_recommendation,
        expected_grade=built.expected_grade,
        estimated_roi_pct=built.expected_roi_pct,
    )


def _storage_for_copies(
    session: Session,
    *,
    owner_user_id: int,
    copy_ids: list[int],
) -> P80StorageIntelligenceRead:
    locations: list[P80StorageLocationRead] = []
    for copy_id in copy_ids:
        assign = session.exec(
            select(P79InventoryLocationAssignment)
            .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
            .where(P79InventoryLocationAssignment.inventory_copy_id == copy_id)
            .order_by(P79InventoryLocationAssignment.assigned_at.desc(), P79InventoryLocationAssignment.id.desc())
        ).first()
        if assign is None:
            continue
        slot = session.get(P79StorageSlot, assign.storage_slot_id)
        if slot is None:
            continue
        box = session.get(P79StorageBox, slot.box_id)
        if box is None:
            continue
        path = _path_fields(session, owner_user_id=owner_user_id, box=box, slot_number=int(slot.slot_number))
        locations.append(
            P80StorageLocationRead(
                inventory_copy_id=copy_id,
                location_path_text=path.location_path_text,
                box_name=box.name,
                slot_number=int(slot.slot_number),
            )
        )
    return P80StorageIntelligenceRead(locations=locations)


def _build_action_card(
    *,
    ownership: P80OwnershipIntelligenceRead,
    recommendation: P80RecommendationIntelligenceRead,
    grading: P80GradingIntelligenceRead,
    fmv: P80FmvIntelligenceRead,
    storage: P80StorageIntelligenceRead,
) -> P80ActionCardRead:
    reasons: list[str] = []
    rec = (recommendation.recommendation or "HOLD").upper()
    if not ownership.owned and rec in {"BUY", "ACQUIRE", "PREORDER"}:
        action = "BUY"
        reasons.append("Recommendation favors acquisition")
        if ownership.total_copies == 0:
            reasons.append("User owns 0 copies")
    elif rec == "SELL":
        action = "SELL"
        reasons.append("Sell intelligence active")
    elif grading.grade_recommendation in {REC_GRADE, REC_PRESS_AND_GRADE}:
        action = "GRADE"
        reasons.append(f"Grading recommendation: {grading.grade_recommendation}")
        if grading.estimated_roi_pct is not None:
            reasons.append(f"Estimated ROI {grading.estimated_roi_pct:.1f}%")
    elif ownership.owned and len(storage.locations) < ownership.total_copies:
        action = "STORE"
        reasons.append("Owned copies lack full storage assignment")
    elif rec == "WATCH":
        action = "WATCH"
        reasons.append("Watch recommendation")
    else:
        action = "HOLD"
        reasons.append("Default hold posture")

    if recommendation.conviction_score is not None:
        reasons.append(f"Recommendation score {recommendation.conviction_score:.0f}")
    if fmv.price_trend_30d and fmv.price_trend_30d.upper() in {"RISING", "UP"}:
        reasons.append("FMV rising")
    if fmv.sales_velocity is not None and fmv.sales_velocity >= 1.0:
        reasons.append("Strong sales velocity")
    return P80ActionCardRead(action=action, reasons=reasons[:6])


def build_book_intelligence(
    session: Session,
    *,
    owner_user_id: int,
    identity: _BookIdentity,
) -> P80BookIntelligenceRead:
    ownership = _ownership_for_identity(session, owner_user_id=owner_user_id, identity=identity)
    rep_id = ownership.inventory_copy_ids[0] if ownership.inventory_copy_ids else identity.representative_copy_id
    fmv = P80FmvIntelligenceRead()
    recommendation = P80RecommendationIntelligenceRead()
    grading = P80GradingIntelligenceRead()
    if rep_id is not None:
        fmv = _fmv_for_copy(session, owner_user_id=owner_user_id, copy_id=rep_id)
        recommendation = _recommendation_for_copy(
            session,
            owner_user_id=owner_user_id,
            copy_id=rep_id,
            title=identity.title,
        )
        grading = _grading_for_copy(session, owner_user_id=owner_user_id, copy_id=rep_id)
    elif not ownership.owned:
        recommendation = P80RecommendationIntelligenceRead(
            recommendation="BUY",
            conviction_score=70.0,
            confidence_score=0.55,
            rationale="Not in collection; acquisition candidate from catalog match.",
            source_system="P51_CATALOG",
        )
    storage = _storage_for_copies(session, owner_user_id=owner_user_id, copy_ids=ownership.inventory_copy_ids)
    action = _build_action_card(
        ownership=ownership,
        recommendation=recommendation,
        grading=grading,
        fmv=fmv,
        storage=storage,
    )
    return P80BookIntelligenceRead(
        inventory_id=rep_id,
        ownership=ownership,
        fmv=fmv,
        recommendation=recommendation,
        grading=grading,
        storage=storage,
        action_card=action,
    )


def _to_identification_read(
    *,
    confidence: str,
    scan_source: str,
    normalized: str,
    identity: _BookIdentity | None,
    storage_entity: dict | None,
) -> P80ScanIdentificationRead:
    book: P80BookIdentificationRead | None = None
    if identity is not None:
        book = P80BookIdentificationRead(
            cover_image_url=identity.cover_image_url,
            title=identity.title,
            series_name=identity.series_name,
            issue_number=identity.issue_number,
            variant_description=identity.variant_description,
            publisher=identity.publisher,
            release_date=identity.release_date,
            identification_source=identity.identification_source,
            book_identity_key=identity.book_identity_key,
        )
    return P80ScanIdentificationRead(
        confidence=confidence,
        requires_manual_review=confidence == "LOW",
        scan_source=scan_source,
        normalized_barcode=normalized,
        book=book,
        storage_entity=storage_entity,
    )


def _row_to_result(row: P80MobileScan) -> P80MobileScanResultRead:
    if row.identification_json:
        identification = P80ScanIdentificationRead.model_validate(row.identification_json)
    else:
        payload = dict(row.result_payload_json or {})
        identification = P80ScanIdentificationRead.model_validate(payload.get("identification") or {})
    payload = dict(row.result_payload_json or {})
    book_intel_raw = payload.get("book_intelligence")
    book_intel = P80BookIntelligenceRead.model_validate(book_intel_raw) if book_intel_raw else None
    return P80MobileScanResultRead(
        scan_id=int(row.id or 0),
        created_at=row.created_at,
        identification=identification,
        book_intelligence=book_intel,
    )


def identify_for_scan_input(
    session: Session,
    *,
    owner_user_id: int,
    barcode: str | None = None,
    manual_entry: str | None = None,
) -> tuple[P80ScanIdentificationRead, _BookIdentity | None]:
    """Resolve barcode/manual entry without persisting a scan row (P80-03 shopping)."""
    raw = (barcode or manual_entry or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Provide barcode or manual_entry.")
    normalized = _normalize_barcode(raw)
    identity, confidence, scan_source, storage_entity = _identify_book(
        session,
        owner_user_id=owner_user_id,
        normalized=normalized,
    )
    if confidence not in P80_CONFIDENCE_LEVELS:
        confidence = "LOW"
    identification = _to_identification_read(
        confidence=confidence,
        scan_source=scan_source,
        normalized=normalized,
        identity=identity,
        storage_entity=storage_entity,
    )
    return identification, identity


def create_mobile_scan(
    session: Session,
    *,
    owner_user_id: int,
    payload: P80MobileScanCreateRequest,
) -> P80MobileScanResultRead:
    raw = (payload.barcode or payload.manual_entry or "").strip()
    if not raw and not payload.image:
        raise HTTPException(status_code=422, detail="Provide barcode, manual_entry, or image.")
    normalized = _normalize_barcode(raw) if raw else "ocr:pending"
    scan_source = "OCR_PENDING" if not raw else "BARCODE"

    identity: _BookIdentity | None = None
    confidence = "LOW"
    storage_entity: dict | None = None
    if raw:
        identity, confidence, scan_source, storage_entity = _identify_book(
            session,
            owner_user_id=owner_user_id,
            normalized=normalized,
        )
    elif payload.image:
        scan_source = "OCR_PENDING"
        confidence = "LOW"

    if confidence not in P80_CONFIDENCE_LEVELS:
        confidence = "LOW"

    book_intel: P80BookIntelligenceRead | None = None
    if identity is not None:
        book_intel = build_book_intelligence(session, owner_user_id=owner_user_id, identity=identity)

    identification = _to_identification_read(
        confidence=confidence,
        scan_source=scan_source,
        normalized=normalized,
        identity=identity,
        storage_entity=storage_entity,
    )
    result = P80MobileScanResultRead(
        scan_id=0,
        created_at=utc_now(),
        identification=identification,
        book_intelligence=book_intel,
    )
    row = P80MobileScan(
        owner_user_id=owner_user_id,
        scan_source=scan_source,
        raw_input=raw or (payload.image or "")[:512],
        normalized_barcode=normalized,
        image_reference=(payload.image or "")[:512] or None,
        confidence=confidence,
        requires_manual_review=confidence == "LOW",
        inventory_copy_id=book_intel.inventory_id if book_intel else None,
        book_identity_key=identity.book_identity_key if identity else "",
        identification_json=identification.model_dump(mode="json"),
        result_payload_json=result.model_dump(mode="json"),
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    persisted = _row_to_result(row)
    return P80MobileScanResultRead(
        scan_id=int(row.id or 0),
        created_at=row.created_at,
        identification=persisted.identification,
        book_intelligence=persisted.book_intelligence,
    )


def get_mobile_scan(session: Session, *, owner_user_id: int, scan_id: int) -> P80MobileScanResultRead:
    row = session.get(P80MobileScan, scan_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return _row_to_result(row)


def resolve_barcode_identification(
    session: Session,
    *,
    owner_user_id: int,
    raw_barcode: str,
) -> tuple[_BookIdentity | None, str, str, dict | None, str]:
    normalized = _normalize_barcode(raw_barcode)
    identity, confidence, scan_source, storage_entity = _identify_book(
        session,
        owner_user_id=owner_user_id,
        normalized=normalized,
    )
    return identity, confidence, scan_source, storage_entity, normalized


def get_book_intelligence(
    session: Session,
    *,
    owner_user_id: int,
    inventory_id: int,
) -> P80BookIntelligenceRead:
    copy = session.get(InventoryCopy, inventory_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    identity = _book_from_copy(session, copy, source="inventory_lookup")
    return build_book_intelligence(session, owner_user_id=owner_user_id, identity=identity)


def list_mobile_scans(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[P80MobileScanResultRead], int]:
    lim = max(1, min(limit, 100))
    off = max(0, offset)
    total = session.exec(
        select(col(P80MobileScan.id)).where(P80MobileScan.owner_user_id == owner_user_id)
    ).all()
    rows = session.exec(
        select(P80MobileScan)
        .where(P80MobileScan.owner_user_id == owner_user_id)
        .order_by(P80MobileScan.created_at.desc(), P80MobileScan.id.desc())
        .offset(off)
        .limit(lim)
    ).all()
    return [_row_to_result(row) for row in rows], len(total)
