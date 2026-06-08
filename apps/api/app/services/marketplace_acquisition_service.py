"""P82 marketplace acquisition intelligence."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity, MarketplaceAcquisitionSnapshot, utc_now
from app.schemas.p82_p84_collector_expansion import (
    MarketplaceAcquisitionDashboardRead,
    MarketplaceAcquisitionListResponse,
    MarketplaceAcquisitionOpportunityRead,
    MarketplaceAcquisitionScanPayload,
    VerifiedMarketplaceListingRead,
)
from app.services.marketplace.marketplace_listing_service import listing_summary_for_opportunity
from app.services.p77_personalization_engine import load_personalization_context, personalize_score


def _rec(score: float) -> str:
    if score >= 85:
        return "STRONG_BUY"
    if score >= 70:
        return "GOOD_BUY"
    if score >= 50:
        return "WATCH"
    return "PASS"


def _to_read(
    row: MarketplaceAcquisitionOpportunity,
    *,
    summary: dict[str, object] | None = None,
    session: Session | None = None,
    owner_user_id: int | None = None,
) -> MarketplaceAcquisitionOpportunityRead:
    s = summary or {}
    best_verified_raw = s.get("best_verified_listing")
    best_verified: VerifiedMarketplaceListingRead | None = None
    if isinstance(best_verified_raw, dict) and best_verified_raw.get("listing_url"):
        best_verified = VerifiedMarketplaceListingRead.model_validate(best_verified_raw)
    effective_fmv = float(row.estimated_fmv)
    effective_discount = float(row.discount_to_fmv)
    fmv_v2_market: float | None = None
    fmv_v2_conf: str | None = None
    if session is not None and owner_user_id is not None:
        from app.services.fmv_v2_service import lookup_fmv_v2_display

        v2 = lookup_fmv_v2_display(
            session,
            owner_user_id=owner_user_id,
            series=row.series,
            issue_number=row.issue,
            variant=row.variant,
        )
        if v2 is not None and v2.market_value > 0:
            fmv_v2_market = v2.market_value
            fmv_v2_conf = v2.valuation_confidence
            effective_fmv = v2.market_value
            if effective_fmv > 0:
                effective_discount = round((effective_fmv - float(row.asking_price)) / effective_fmv * 100.0, 1)
    return MarketplaceAcquisitionOpportunityRead(
        id=int(row.id or 0),
        marketplace=row.marketplace,
        external_listing_id=row.external_listing_id,
        listing_url=row.listing_url,
        title=row.title,
        publisher=row.publisher,
        series=row.series,
        issue=row.issue,
        variant=row.variant,
        asking_price=float(row.asking_price),
        estimated_fmv=float(row.estimated_fmv),
        discount_to_fmv=float(row.discount_to_fmv),
        liquidity=float(row.liquidity),
        velocity=float(row.velocity),
        grading_upside=float(row.grading_upside),
        ownership_status=row.ownership_status,
        profile_match_score=float(row.profile_match_score),
        opportunity_score=float(row.opportunity_score),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        reasons=list(row.reasons_json or []),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        best_listing_id=row.best_listing_id,
        active_listing_count=int(s.get("active_listing_count") or 0),
        best_active_price=s.get("best_active_price"),  # type: ignore[arg-type]
        listing_marketplace=s.get("listing_marketplace"),  # type: ignore[arg-type]
        has_verified_listings=bool(s.get("has_verified_listings")),
        verified_listing_count=int(s.get("verified_listing_count") or 0),
        best_total_cost=s.get("best_total_cost"),  # type: ignore[arg-type]
        best_verified_listing=best_verified,
        best_marketplace=s.get("best_marketplace"),  # type: ignore[arg-type]
        best_marketplace_name=s.get("best_marketplace_name"),  # type: ignore[arg-type]
        best_market_price=s.get("best_market_price"),  # type: ignore[arg-type]
        savings_vs_highest=s.get("savings_vs_highest"),  # type: ignore[arg-type]
        best_buy_reason=s.get("best_buy_reason"),  # type: ignore[arg-type]
        marketplace_count=int(s.get("marketplace_count") or 0),
        fmv_v2_market_value=fmv_v2_market,
        fmv_v2_confidence=fmv_v2_conf,
        effective_discount_to_fmv=effective_discount if fmv_v2_market is not None else None,
    )


def _score_opportunity(
    *,
    asking: float,
    fmv: float,
    liquidity: float,
    velocity: float,
    grading_upside: float,
    profile_match: float,
    ownership: str,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 40.0
    if fmv > 0:
        disc = (fmv - asking) / fmv * 100.0
        if disc >= 25:
            score += 30
            reasons.append(f"Spread to FMV {disc:.0f}%")
        elif disc >= 15:
            score += 18
            reasons.append(f"Discount to FMV {disc:.0f}%")
        elif disc >= 5:
            score += 8
    if liquidity >= 55:
        score += 10
        reasons.append("High liquidity")
    if velocity >= 2:
        score += 6
        reasons.append("Strong sales velocity")
    if grading_upside >= 15:
        score += 12
        reasons.append("Grading upside")
    score += min(15.0, profile_match)
    if ownership == "GAP":
        score += 8
        reasons.append("Fills collection gap")
    return min(100.0, round(score, 1)), reasons[:6]


def scan_marketplace_listing(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketplaceAcquisitionScanPayload,
    persist: bool = True,
) -> MarketplaceAcquisitionOpportunityRead:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    fmv = max(payload.asking_price * 1.35, 10.0)
    snap = session.exec(
        select(P68MarketPriceSnapshot)
        .where(P68MarketPriceSnapshot.owner_user_id == owner_user_id)
        .order_by(P68MarketPriceSnapshot.id.desc())
        .limit(1)
    ).first()
    if snap and float(snap.blended_fmv or 0) > 0:
        fmv = max(fmv, float(snap.blended_fmv))
    hay = f"{payload.publisher} {payload.series} {payload.title}"
    pers, _, _, _, _, pers_reasons = personalize_score(
        ctx, global_score=70.0, publisher=payload.publisher, series_name=payload.series, title=payload.title
    )
    profile_match = max(0.0, pers - 70.0)
    liquidity = float(snap.liquidity_score if snap else 50.0)
    velocity = float((snap.metadata_json or {}).get("sales_velocity", 1.5) if snap else 1.5)
    grading_upside = 20.0 if "nm" in payload.title.lower() else 8.0
    ownership = "OWNED" if any(r.lower() in hay.lower() for r in pers_reasons if "owns" in r.lower()) else "GAP"
    disc = round((fmv - payload.asking_price) / fmv * 100.0, 1) if fmv > 0 else 0.0
    score, reasons = _score_opportunity(
        asking=payload.asking_price,
        fmv=fmv,
        liquidity=liquidity,
        velocity=velocity,
        grading_upside=grading_upside,
        profile_match=profile_match,
        ownership=ownership,
    )
    reasons = reasons + pers_reasons[:2]
    now = utc_now()
    row = session.exec(
        select(MarketplaceAcquisitionOpportunity).where(
            MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id,
            MarketplaceAcquisitionOpportunity.marketplace == payload.marketplace,
            MarketplaceAcquisitionOpportunity.external_listing_id == payload.external_listing_id,
        )
    ).first()
    if row is None:
        row = MarketplaceAcquisitionOpportunity(
            owner_user_id=owner_user_id,
            marketplace=payload.marketplace,
            external_listing_id=payload.external_listing_id,
            created_at=now,
        )
    row.listing_url = payload.listing_url or f"https://www.ebay.com/itm/{payload.external_listing_id}"
    row.title = payload.title
    row.publisher = payload.publisher
    row.series = payload.series or payload.title.split("#")[0].strip()
    row.issue = payload.issue
    row.variant = payload.variant
    row.asking_price = payload.asking_price
    row.estimated_fmv = round(fmv, 2)
    row.discount_to_fmv = disc
    row.liquidity = liquidity
    row.velocity = velocity
    row.grading_upside = grading_upside
    row.ownership_status = ownership
    row.profile_match_score = round(profile_match, 1)
    row.opportunity_score = score
    row.recommendation = _rec(score)
    row.reasons_json = reasons
    row.status = "ACTIVE"
    row.updated_at = now
    if persist:
        session.add(row)
        session.flush()
    return _to_read(row)


def _seed_simulated_deals(session: Session, *, owner_user_id: int, limit: int = 5) -> None:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
            .limit(limit)
        ).all()
    )
    for copy in copies:
        if copy.variant_id is None:
            continue
        variant = session.get(Variant, copy.variant_id)
        if not variant:
            continue
        issue = session.get(ComicIssue, variant.comic_issue_id) if variant.comic_issue_id else None
        title_row = session.get(ComicTitle, issue.comic_title_id) if issue and issue.comic_title_id else None
        pub_name = ""
        if title_row and title_row.publisher_id:
            pub = session.get(Publisher, title_row.publisher_id)
            pub_name = pub.name if pub else ""
        fmv = float(copy.current_fmv or copy.acquisition_cost or 10)
        asking = round(fmv * 0.72, 2)
        series = title_row.name if title_row else "Unknown"
        inum = issue.issue_number if issue else ""
        ext = f"SIM-EBAY-P82-{copy.id}"
        existing = session.exec(
            select(MarketplaceAcquisitionOpportunity).where(
                MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id,
                MarketplaceAcquisitionOpportunity.external_listing_id == ext,
            )
        ).first()
        if existing:
            continue
        scan_marketplace_listing(
            session,
            owner_user_id=owner_user_id,
            payload=MarketplaceAcquisitionScanPayload(
                marketplace="EBAY",
                external_listing_id=ext,
                title=f"{series} #{inum}".strip(),
                publisher=pub_name,
                series=series,
                issue=inum or "",
                asking_price=asking,
            ),
            persist=True,
        )


def list_acquisition_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
) -> MarketplaceAcquisitionListResponse:
    if refresh:
        _seed_simulated_deals(session, owner_user_id=owner_user_id)
    stmt = select(MarketplaceAcquisitionOpportunity).where(
        MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id,
        MarketplaceAcquisitionOpportunity.status == "ACTIVE",
    )
    if recommendation:
        stmt = stmt.where(MarketplaceAcquisitionOpportunity.recommendation == recommendation.strip().upper())
    rows = list(session.exec(stmt.order_by(MarketplaceAcquisitionOpportunity.opportunity_score.desc())).all())
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page_rows = rows[off : off + lim]
    page = [
        _to_read(
            r,
            summary=listing_summary_for_opportunity(
                session,
                owner_user_id=owner_user_id,
                opportunity_id=int(r.id or 0),
            ),
            session=session,
            owner_user_id=owner_user_id,
        )
        for r in page_rows
    ]
    return MarketplaceAcquisitionListResponse(items=page, total_items=len(rows), limit=lim, offset=off)


def get_acquisition_opportunity(session: Session, *, owner_user_id: int, opportunity_id: int) -> MarketplaceAcquisitionOpportunityRead:
    row = session.get(MarketplaceAcquisitionOpportunity, opportunity_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return _to_read(
        row,
        summary=listing_summary_for_opportunity(
            session,
            owner_user_id=owner_user_id,
            opportunity_id=int(row.id or 0),
        ),
        session=session,
        owner_user_id=owner_user_id,
    )


def build_acquisition_dashboard(session: Session, *, owner_user_id: int, refresh: bool = True) -> MarketplaceAcquisitionDashboardRead:
    if refresh:
        _seed_simulated_deals(session, owner_user_id=owner_user_id)
    body = list_acquisition_opportunities(session, owner_user_id=owner_user_id, limit=100, offset=0)
    items = body.items
    snap = MarketplaceAcquisitionSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        metrics_json={"total": len(items), "strong": sum(1 for i in items if i.recommendation == "STRONG_BUY")},
        created_at=utc_now(),
    )
    session.add(snap)
    session.flush()
    by_spread = sorted(
        items,
        key=lambda x: float(x.effective_discount_to_fmv if x.effective_discount_to_fmv is not None else x.discount_to_fmv),
        reverse=True,
    )
    by_grade = sorted(items, key=lambda x: x.grading_upside, reverse=True)
    by_prof = sorted(items, key=lambda x: x.profile_match_score, reverse=True)
    return MarketplaceAcquisitionDashboardRead(
        strong_buys=[i for i in items if i.recommendation == "STRONG_BUY"][:15],
        good_buys=[i for i in items if i.recommendation == "GOOD_BUY"][:15],
        watch=[i for i in items if i.recommendation == "WATCH"][:15],
        pass_list=[i for i in items if i.recommendation == "PASS"][:10],
        largest_spread=by_spread[:10],
        best_grading_upside=by_grade[:10],
        best_profile_matches=by_prof[:10],
        snapshot_id=int(snap.id or 0),
    )
