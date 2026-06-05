"""P67-02 Collection composition analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlmodel import Session, select

from app.models.portfolio_analytics_platform import P67CollectionAnalyticsSnapshot, utc_now
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context


def get_latest_collection_analytics_snapshot(session: Session, *, owner_user_id: int) -> P67CollectionAnalyticsSnapshot | None:
    return session.exec(
        select(P67CollectionAnalyticsSnapshot)
        .where(P67CollectionAnalyticsSnapshot.owner_user_id == owner_user_id)
        .order_by(P67CollectionAnalyticsSnapshot.generated_at.desc(), P67CollectionAnalyticsSnapshot.id.desc())
    ).first()


def build_collection_analytics_snapshot(session: Session, *, owner_user_id: int) -> P67CollectionAnalyticsSnapshot:
    today = date.today()
    rows = load_p67_inventory_context(session, owner_user_id=owner_user_id)
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)

    publisher_val: dict[str, float] = defaultdict(float)
    era_val: dict[str, float] = defaultdict(float)
    printing_val: dict[str, float] = defaultdict(float)
    variant_val: dict[str, float] = defaultdict(float)
    holdings: list[tuple[str, float]] = []

    total_value = 0.0
    for row in rows:
        est = enrich_row_value(row, fmv_map)
        total_value += est
        publisher_val[row.publisher or "Unknown"] += est
        era = "Modern"
        if row.issue_number.isdigit() and int(row.issue_number) <= 100:
            era = "Silver/Bronze candidate"
        era_val[era] += est
        printing_val[row.grade_status or "raw"] += est
        variant_val[row.identity_key.split("|")[-1] if "|" in row.identity_key else "standard"] += est
        holdings.append((f"{row.title} #{row.issue_number}", est))

    holdings.sort(key=lambda x: x[1], reverse=True)
    top_share = (holdings[0][1] / total_value * 100.0) if holdings and total_value > 0 else 0.0
    pub_shares = sorted(
        ((k, v / total_value * 100.0) for k, v in publisher_val.items() if total_value > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    concentration = min(100.0, top_share + (pub_shares[0][1] if pub_shares else 0.0))

    snap = P67CollectionAnalyticsSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        total_holdings=len(rows),
        concentration_score=round(concentration, 2),
        metadata_json={
            "publisher_allocation_pct": {k: round(v, 2) for k, v in pub_shares[:20]},
            "franchise_allocation_pct": {},
            "character_allocation_pct": {},
            "creator_allocation_pct": {},
            "era_allocation_pct": {k: round(v / total_value * 100.0, 2) for k, v in era_val.items()} if total_value else {},
            "printing_allocation_pct": {k: round(v / total_value * 100.0, 2) for k, v in printing_val.items()} if total_value else {},
            "variant_allocation_pct": {k: round(v / total_value * 100.0, 2) for k, v in list(variant_val.items())[:15]} if total_value else {},
            "top_holdings": [{"title": t, "value": round(v, 2)} for t, v in holdings[:15]],
            "diversification_score": round(max(0.0, 100.0 - concentration), 2),
        },
    )
    session.add(snap)
    session.flush()
    return snap
