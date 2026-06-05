"""P66-04 Variant Decision Engine — cover ranking and buy plan."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.variant_market_intelligence import VariantDecisionItem, VariantDecisionSnapshot
from app.services.market_pricing_service import get_latest_market_price_snapshot, list_market_observations
from app.services.quantity_intelligence_service import get_latest_quantity_snapshot, list_quantity_items
from app.services.variant_intelligence_service import get_latest_variant_intelligence_snapshot, list_variant_intelligence_items


def get_latest_variant_decision_snapshot(session: Session, *, owner_user_id: int) -> VariantDecisionSnapshot | None:
    return session.exec(
        select(VariantDecisionSnapshot)
        .where(VariantDecisionSnapshot.owner_user_id == owner_user_id)
        .order_by(VariantDecisionSnapshot.generated_at.desc(), VariantDecisionSnapshot.id.desc())
    ).first()


def list_variant_decision_items(session: Session, *, snapshot_id: int, limit: int = 100) -> list[VariantDecisionItem]:
    return list(
        session.exec(
            select(VariantDecisionItem)
            .where(VariantDecisionItem.snapshot_id == snapshot_id)
            .order_by(VariantDecisionItem.id.asc())
            .limit(limit)
        ).all()
    )


def _price_by_variant(price_obs: list) -> dict[int, float]:
    out: dict[int, float] = {}
    for o in price_obs:
        if o.external_catalog_variant_id:
            out[int(o.external_catalog_variant_id)] = float(o.fmv)
    return out


def build_variant_decisions(session: Session, *, owner_user_id: int) -> VariantDecisionSnapshot:
    vi_snap = get_latest_variant_intelligence_snapshot(session, owner_user_id=owner_user_id)
    qty_snap = get_latest_quantity_snapshot(session, owner_user_id=owner_user_id)
    mp_snap = get_latest_market_price_snapshot(session, owner_user_id=owner_user_id)

    snap = VariantDecisionSnapshot(owner_user_id=owner_user_id, total_issues=0, metadata_json={})
    session.add(snap)
    session.flush()

    if vi_snap is None:
        session.commit()
        session.refresh(snap)
        return snap

    variants = list_variant_intelligence_items(session, snapshot_id=int(vi_snap.id or 0))
    qty_by_bq: dict[int, object] = {}
    if qty_snap:
        for q in list_quantity_items(session, snapshot_id=int(qty_snap.id or 0)):
            if q.buy_queue_item_id:
                qty_by_bq[int(q.buy_queue_item_id)] = q

    price_obs = list_market_observations(session, snapshot_id=int(mp_snap.id or 0)) if mp_snap else []
    fmv_map = _price_by_variant(price_obs)

    by_issue: dict[int, list] = {}
    for v in variants:
        eid = int(v.external_catalog_issue_id or 0)
        if eid:
            by_issue.setdefault(eid, []).append(v)

    issue_count = 0
    for eid, covers in by_issue.items():
        covers_sorted = sorted(covers, key=lambda c: (-c.variant_score, c.cover_label))
        ranking = [
            {
                "cover_label": c.cover_label,
                "variant_name": c.variant_name,
                "variant_score": c.variant_score,
                "variant_tier": c.variant_tier,
                "variant_reason": c.variant_reason,
            }
            for c in covers_sorted
        ]
        buy_plan: list[dict] = []
        skip: list[dict] = []
        top = covers_sorted[0] if covers_sorted else None
        title = ""
        issue_number = ""
        bq_id = None
        qty_row = None
        for c in covers_sorted:
            if c.provenance_json.get("buy_queue_item_id"):
                bq_id = int(c.provenance_json["buy_queue_item_id"])
            if not title and c.provenance_json.get("title"):
                title = str(c.provenance_json["title"])
        if not title and top:
            title = top.variant_name
        if bq_id and bq_id in qty_by_bq:
            qty_row = qty_by_bq[bq_id]
            if qty_row.title:
                title = qty_row.title
                issue_number = str(getattr(qty_row, "issue_number", "") or "")

        for c in covers_sorted:
            entry = {
                "cover_label": c.cover_label,
                "variant_name": c.variant_name,
                "variant_score": c.variant_score,
            }
            if c.variant_tier in ("S", "A") or (c.variant_tier == "B" and c.cover_label.upper() == "A"):
                buy_plan.append(entry)
            elif c.variant_score < 70:
                skip.append(entry)

        if not buy_plan and top:
            buy_plan.append(
                {
                    "cover_label": top.cover_label,
                    "variant_name": top.variant_name,
                    "variant_score": top.variant_score,
                }
            )

        coll = int(getattr(qty_row, "collection_quantity", 1) or 1) if qty_row else 1
        spec_q = int(getattr(qty_row, "spec_quantity", 0) or 0) if qty_row else 0
        allocated: list[dict] = []
        for entry in buy_plan[:3]:
            label = entry["cover_label"].upper()
            qty = coll if label == "A" or len(buy_plan) == 1 else (spec_q if spec_q else 1)
            if "foil" in (entry.get("variant_name") or "").lower() and spec_q:
                qty = max(1, spec_q)
            allocated.append({**entry, "quantity": qty})

        foil = next((c for c in covers_sorted if "foil" in (c.variant_name or "").lower()), None)
        standard = next((c for c in covers_sorted if (c.cover_label or "A").upper() == "A"), None)
        premium_note = ""
        if foil and standard and foil.external_catalog_variant_id and standard.external_catalog_variant_id:
            f_fmv = fmv_map.get(int(foil.external_catalog_variant_id), 0)
            s_fmv = fmv_map.get(int(standard.external_catalog_variant_id), 0)
            delta = round(f_fmv - s_fmv, 2)
            if delta >= 0:
                premium_note = f"Foil premium is only ${delta:.2f} and historical performance is stronger."

        summary_lines = [f"{title} — ranked {len(covers_sorted)} covers."]
        for a in allocated:
            summary_lines.append(f"Buy: Cover {a['cover_label']} x{a['quantity']}")
        for s in skip[:2]:
            summary_lines.append(f"Do not buy: Cover {s['cover_label']}")
        if premium_note:
            summary_lines.append(f"Reason: {premium_note}")

        session.add(
            VariantDecisionItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                external_catalog_issue_id=eid,
                buy_queue_item_id=bq_id,
                title=str(title),
                issue_number=issue_number,
                recommendation_summary="\n".join(summary_lines),
                cover_ranking_json=ranking,
                buy_plan_json=allocated,
                skip_covers_json=skip,
                quantity_plan_json={
                    "collection_quantity": coll,
                    "spec_quantity": spec_q,
                    "flip_quantity": int(getattr(qty_row, "flip_quantity", 0) or 0) if qty_row else 0,
                    "total_quantity": int(getattr(qty_row, "total_quantity", coll) or coll) if qty_row else coll,
                },
            )
        )
        issue_count += 1

    snap.total_issues = issue_count
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
