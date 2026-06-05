"""P66-01 Variant Intelligence — per-cover scoring (read-only upstream)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.models.variant_market_intelligence import (
    TIER_A,
    TIER_B,
    TIER_C,
    TIER_S,
    VariantIntelligenceItem,
    VariantIntelligenceSnapshot,
)
from app.services.buy_queue_service import get_latest_buy_queue_snapshot, list_buy_queue_items

_COVER_TYPES = (
    ("foil", 12.0),
    ("virgin", 8.0),
    ("sketch", 10.0),
    ("blank", 6.0),
    ("homage", 5.0),
)
_CHARACTER_HINTS = ("wolverine", "batman", "spider", "venom", "transformers", "spawn")


def get_latest_variant_intelligence_snapshot(session: Session, *, owner_user_id: int) -> VariantIntelligenceSnapshot | None:
    return session.exec(
        select(VariantIntelligenceSnapshot)
        .where(VariantIntelligenceSnapshot.owner_user_id == owner_user_id)
        .order_by(VariantIntelligenceSnapshot.generated_at.desc(), VariantIntelligenceSnapshot.id.desc())
    ).first()


def list_variant_intelligence_items(session: Session, *, snapshot_id: int, limit: int = 500) -> list[VariantIntelligenceItem]:
    return list(
        session.exec(
            select(VariantIntelligenceItem)
            .where(VariantIntelligenceItem.snapshot_id == snapshot_id)
            .order_by(VariantIntelligenceItem.variant_score.desc(), VariantIntelligenceItem.id.asc())
            .limit(limit)
        ).all()
    )


def _tier(score: float) -> str:
    if score >= 90:
        return TIER_S
    if score >= 78:
        return TIER_A
    if score >= 65:
        return TIER_B
    return TIER_C


def _score_variant(
    *,
    variant: ExternalCatalogVariant,
    issue: ExternalCatalogIssue,
    demand_boost: float,
) -> tuple[float, str, dict]:
    name = f"{variant.variant_name or ''} {variant.cover_label or ''}".lower()
    score = 50.0
    factors: dict = {}
    for token, pts in _COVER_TYPES:
        if token in name:
            score += pts
            factors[token] = pts
    ratio = variant.ratio_value
    if ratio is not None:
        if ratio >= 100:
            score += 4.0
            factors["ratio_scarcity"] = 4.0
        elif ratio >= 50:
            score += 8.0
            factors["ratio_scarcity"] = 8.0
        elif ratio >= 25:
            score += 15.0
            factors["ratio_scarcity"] = 15.0
    elif (variant.cover_label or "A").upper() == "A":
        score += 5.0
        factors["primary_cover"] = 5.0
    if variant.artist:
        score += 5.0
        factors["artist"] = 5.0
    if any(h in name for h in _CHARACTER_HINTS):
        score += 6.0
        factors["character_cover"] = 6.0
    pull = int(issue.pull_count or 0)
    want = int(issue.want_count or 0)
    demand_pts = min(15.0, pull * 0.02 + want * 0.015) + demand_boost
    score += demand_pts
    factors["collector_demand"] = round(demand_pts, 2)
    score = min(100.0, max(0.0, round(score, 2)))
    reasons: list[str] = []
    if factors.get("foil"):
        reasons.append("foil premium")
    if factors.get("ratio_scarcity"):
        reasons.append(f"ratio 1:{ratio}")
    if factors.get("artist"):
        reasons.append(f"artist {variant.artist}")
    if factors.get("character_cover"):
        reasons.append("character-driven cover")
    if demand_pts >= 8:
        reasons.append("strong collector demand")
    if not reasons:
        reasons.append("standard cover profile")
    return score, _tier(score), factors


def build_variant_intelligence(session: Session, *, owner_user_id: int) -> VariantIntelligenceSnapshot:
    snap = VariantIntelligenceSnapshot(owner_user_id=owner_user_id, total_items=0, metadata_json={})
    session.add(snap)
    session.flush()

    demand_by_issue: dict[int, float] = {}
    release_by_issue: dict[int, int] = {}
    bq_item_by_issue: dict[int, int] = {}
    title_by_issue: dict[int, str] = {}
    bq = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    if bq:
        items, _ = list_buy_queue_items(session, snapshot_id=int(bq.id or 0), limit=100)
        for row in items:
            if row.external_catalog_issue_id:
                eid = int(row.external_catalog_issue_id)
                demand_by_issue[eid] = max(demand_by_issue.get(eid, 0.0), float(row.demand_score or 0) * 0.08)
                bq_item_by_issue[eid] = int(row.id or 0)
                title_by_issue[eid] = row.title
                if row.release_issue_id:
                    release_by_issue[eid] = int(row.release_issue_id)

    total = 0
    for eid, boost in demand_by_issue.items():
        issue = session.get(ExternalCatalogIssue, eid)
        if issue is None:
            continue
        variants = list(
            session.exec(select(ExternalCatalogVariant).where(ExternalCatalogVariant.external_issue_id == eid)).all()
        )
        if not variants:
            variants = [
                ExternalCatalogVariant(
                    external_issue_id=eid,
                    cover_label="A",
                    variant_name="Standard",
                    price=issue.price,
                )
            ]
        for var in variants:
            score, tier, factors = _score_variant(variant=var, issue=issue, demand_boost=boost)
            label = (var.cover_label or "A").strip()
            vname = (var.variant_name or "Standard").strip()
            reason = f"Cover {label} ({vname}): " + ", ".join(
                k.replace("_", " ") for k in factors.keys()
            )
            session.add(
                VariantIntelligenceItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    external_catalog_issue_id=eid,
                    external_catalog_variant_id=int(var.id) if var.id else None,
                    release_issue_id=release_by_issue.get(eid),
                    cover_label=label,
                    variant_name=vname,
                    variant_score=score,
                    variant_tier=tier,
                    variant_reason=reason,
                    factors_json=factors,
                    provenance_json={
                        "buy_queue_demand_boost": boost,
                        "buy_queue_item_id": bq_item_by_issue.get(eid),
                        "title": title_by_issue.get(eid, ""),
                    },
                )
            )
            total += 1

    snap.total_items = total
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
