"""P68 Market Pricing Engine — ingest, match, snapshot, computed FMV (separate from P66 stub pricing)."""

from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.market_pricing_engine import (
    P68_SOURCE_VERSION,
    PROVIDER_EBAY_SOLD,
    PROVIDER_INTERNAL_SALE,
    PROVIDER_MANUAL,
    P68InventoryComputedFmv,
    P68MarketPriceMatchResult,
    P68MarketPriceObservation,
    P68MarketPriceSnapshot,
    utc_now,
)
from app.services.ebay_sold_listings_provider import EbaySoldListingsProvider
from app.services.fmv_calculation_engine import compute_fmv_bundle
from app.services.internal_sale_provider import ingest_internal_sale_observations
from app.services.market_price_identity_matching import IdentityTarget, score_observation_match
from app.services.market_pricing_provider_registry import ensure_provider_registry, mark_provider_ingest
from app.services.p68_feature_flags import p68_auto_overwrite_inventory_fmv, p68_ebay_provider_enabled
from app.services.printing_intelligence import parse_printing_profile
from app.services.sell_candidate_engine import _split_identity_key


def list_observations(session: Session, *, owner_user_id: int, limit: int = 500) -> list[P68MarketPriceObservation]:
    return list(
        session.exec(
            select(P68MarketPriceObservation)
            .where(P68MarketPriceObservation.owner_user_id == owner_user_id)
            .order_by(P68MarketPriceObservation.observed_at.desc(), P68MarketPriceObservation.id.desc())
            .limit(limit)
        ).all()
    )


def get_latest_p68_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 200,
) -> list[P68MarketPriceSnapshot]:
    return list(
        session.exec(
            select(P68MarketPriceSnapshot)
            .where(P68MarketPriceSnapshot.owner_user_id == owner_user_id)
            .order_by(P68MarketPriceSnapshot.generated_at.desc(), P68MarketPriceSnapshot.id.desc())
            .limit(limit)
        ).all()
    )


def add_manual_observation(session: Session, *, owner_user_id: int, **fields) -> P68MarketPriceObservation:
    total = float(fields.pop("total_price", 0) or 0)
    obs = P68MarketPriceObservation(
        owner_user_id=owner_user_id,
        provider=PROVIDER_MANUAL,
        title=str(fields.get("title") or ""),
        publisher=str(fields.get("publisher") or ""),
        issue_number=str(fields.get("issue_number") or ""),
        variant_label=fields.get("variant_label"),
        raw_or_graded=str(fields.get("raw_or_graded") or "raw"),
        sold_price=total,
        total_price=total,
        confidence=0.75,
        inventory_copy_id=fields.get("inventory_copy_id"),
        metadata_json={"manual_override": True},
    )
    session.add(obs)
    session.flush()
    return obs


def _identity_target_from_copy(copy: InventoryCopy) -> IdentityTarget:
    pub, series, issue, variant = _split_identity_key(copy.metadata_identity_key)
    profile = parse_printing_profile(title=series or "", description=copy.printing or "")
    raw_or_graded = "graded" if (copy.grade_status or "raw") != "raw" else "raw"
    return IdentityTarget(
        title=series or (copy.metadata_identity_key or ""),
        publisher=pub,
        issue_number=issue,
        variant_label=variant or None,
        printing_number=profile.printing_number,
        printing_kind=profile.printing_kind,
        raw_or_graded=raw_or_graded,
        grade=copy.grade_status if raw_or_graded == "graded" else None,
    )


def _ingest_ebay_fixtures(session: Session, *, owner_user_id: int, copies: list[InventoryCopy]) -> list[P68MarketPriceObservation]:
    if not p68_ebay_provider_enabled():
        return []
    provider = EbaySoldListingsProvider()
    seen: set[tuple[str, str, str]] = set()
    created: list[P68MarketPriceObservation] = []
    for copy in copies:
        if (copy.hold_status or "") in {"sold", "sold_internal"}:
            continue
        pub, series, issue, variant = _split_identity_key(copy.metadata_identity_key)
        key = (pub.lower(), issue, (variant or "").lower())
        if key in seen or not issue:
            continue
        seen.add(key)
        for row in provider.fetch(
            owner_user_id=owner_user_id,
            search_query=series or "",
            publisher=pub,
            issue_number=issue,
            variant_label=variant or "",
            raw_or_graded="graded" if (copy.grade_status or "raw") != "raw" else "raw",
        ):
            session.add(row)
            created.append(row)
    session.flush()
    return created


def build_market_price_snapshots(session: Session, *, owner_user_id: int) -> list[P68MarketPriceSnapshot]:
    providers = ensure_provider_registry(session, owner_user_id=owner_user_id)
    by_type = {p.provider_type: p for p in providers}

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())

    internal_rows = ingest_internal_sale_observations(session, owner_user_id=owner_user_id)
    if internal_rows and PROVIDER_INTERNAL_SALE in by_type:
        mark_provider_ingest(session, provider=by_type[PROVIDER_INTERNAL_SALE])

    ebay_rows = _ingest_ebay_fixtures(session, owner_user_id=owner_user_id, copies=copies)
    if ebay_rows and PROVIDER_EBAY_SOLD in by_type:
        mark_provider_ingest(session, provider=by_type[PROVIDER_EBAY_SOLD])

    all_obs = list_observations(session, owner_user_id=owner_user_id, limit=2000)
    snaps: list[P68MarketPriceSnapshot] = []
    now = utc_now()

    for copy in copies:
        if (copy.hold_status or "") in {"sold", "sold_internal"}:
            continue
        copy_id = int(copy.id or 0)
        target = _identity_target_from_copy(copy)
        matched: list[P68MarketPriceObservation] = []
        for obs in all_obs:
            score, reason, rejected, warnings = score_observation_match(obs, target)
            if score <= 0 or rejected:
                continue
            matched.append(obs)
            session.add(
                P68MarketPriceMatchResult(
                    owner_user_id=owner_user_id,
                    observation_id=int(obs.id or 0),
                    target_inventory_copy_id=copy_id,
                    match_score=score,
                    matched=True,
                    matched_reason=reason,
                    rejected_reason=None,
                    identity_warnings=warnings,
                )
            )

        if not matched:
            continue

        bundle = compute_fmv_bundle(matched)
        pub, series, issue, variant = _split_identity_key(copy.metadata_identity_key)
        profile = parse_printing_profile(title=series or "", description=copy.printing or "")
        snap = P68MarketPriceSnapshot(
            owner_user_id=owner_user_id,
            generated_at=now,
            inventory_copy_id=copy_id,
            title=series or target.title,
            publisher=pub or target.publisher,
            issue_number=issue or target.issue_number,
            variant_label=variant or None,
            printing_number=profile.printing_number,
            printing_kind=profile.printing_kind,
            raw_fmv=bundle["raw_fmv"],
            graded_fmv=bundle["graded_fmv"],
            blended_fmv=bundle["blended_fmv"],
            low_sale=bundle["low_sale"],
            high_sale=bundle["high_sale"],
            median_sale=bundle["median_sale"],
            average_sale=bundle["average_sale"],
            sales_count=int(bundle["sales_count"]),
            liquidity_score=float(bundle["liquidity_score"]),
            confidence=float(bundle["confidence"]),
            price_trend_30d=bundle["price_trend_30d"],
            price_trend_90d=bundle["price_trend_90d"],
            primary_provider=bundle["primary_provider"],
            metadata_json={"matched_observation_ids": [int(o.id or 0) for o in matched]},
            source_version=P68_SOURCE_VERSION,
        )
        session.add(snap)
        session.flush()

        fmv_val = bundle["blended_fmv"] or bundle["raw_fmv"] or bundle["graded_fmv"] or 0.0
        source = bundle["primary_provider"] or "BLEND"
        session.add(
            P68InventoryComputedFmv(
                owner_user_id=owner_user_id,
                inventory_copy_id=copy_id,
                snapshot_id=int(snap.id or 0),
                computed_fmv=float(fmv_val or 0),
                computed_fmv_source=source,
                confidence=float(bundle["confidence"]),
                provider_blend_json={"providers": list({o.provider for o in matched})},
                generated_at=now,
            )
        )
        if p68_auto_overwrite_inventory_fmv() and fmv_val and fmv_val > 0:
            copy.current_fmv = fmv_val
            session.add(copy)
        snaps.append(snap)

    if not snaps and all_obs:
        groups: dict[str, list[P68MarketPriceObservation]] = defaultdict(list)
        for obs in all_obs:
            key = obs.series_key or f"{obs.publisher}|{obs.title}|{obs.issue_number}".lower()
            groups[key].append(obs)
        for _key, group in groups.items():
            bundle = compute_fmv_bundle(group)
            lead = group[0]
            snap = P68MarketPriceSnapshot(
                owner_user_id=owner_user_id,
                generated_at=now,
                title=lead.title,
                publisher=lead.publisher,
                issue_number=lead.issue_number,
                variant_label=lead.variant_label,
                printing_number=lead.printing_number,
                printing_kind=lead.printing_kind,
                raw_fmv=bundle["raw_fmv"],
                graded_fmv=bundle["graded_fmv"],
                blended_fmv=bundle["blended_fmv"],
                low_sale=bundle["low_sale"],
                high_sale=bundle["high_sale"],
                median_sale=bundle["median_sale"],
                average_sale=bundle["average_sale"],
                sales_count=int(bundle["sales_count"]),
                liquidity_score=float(bundle["liquidity_score"]),
                confidence=float(bundle["confidence"]),
                price_trend_30d=bundle["price_trend_30d"],
                price_trend_90d=bundle["price_trend_90d"],
                primary_provider=bundle["primary_provider"],
                metadata_json={"aggregate": True},
                source_version=P68_SOURCE_VERSION,
            )
            session.add(snap)
            snaps.append(snap)

    session.flush()
    return snaps
